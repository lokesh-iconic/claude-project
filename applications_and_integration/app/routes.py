"""
app/routes.py -- REST API endpoints.

Endpoint design follows RESTful conventions:
  - Resources: /documents, /sessions
  - Actions: POST (create), GET (read), DELETE (remove)
  - Streaming: SSE (Server-Sent Events) for question answers

All endpoints return Pydantic-validated responses, ensuring schema compliance.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse

from app.config import is_mock_mode, get_model_name
from app.document import parse_document
from app.models import (
    DocumentUploadResponse, QuestionRequest, QuestionResponse,
    StructuredAnswer, SessionInfo, SessionResetResponse, ErrorResponse,
)
from app.session import SessionManager
from app.claude_client import ask_question, ask_question_stream

# ---------------------------------------------------------------------------
# Router & State
# ---------------------------------------------------------------------------

router = APIRouter()
session_manager = SessionManager()

# Path to sample documents
SAMPLE_DOCS_DIR = Path(__file__).parent.parent / "sample_documents"


# ---------------------------------------------------------------------------
# Document Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/documents/upload",
    response_model=DocumentUploadResponse,
    summary="Upload a document and create a Q&A session",
    responses={400: {"model": ErrorResponse}},
)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a text document to create a new Q&A session.

    The document is parsed into sections for citation referencing.
    A session_id is returned for subsequent question requests.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    # Read content
    content_bytes = await file.read()
    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="File must be UTF-8 encoded text. PDF support coming soon.",
        )

    if len(content.strip()) == 0:
        raise HTTPException(status_code=400, detail="Document is empty")

    # Parse document into sections
    document = parse_document(file.filename, content)

    # Create session
    session = session_manager.create_session(document)

    return DocumentUploadResponse(
        session_id=session.session_id,
        document_name=document.filename,
        document_sections=document.section_count,
        document_chars=document.char_count,
    )


@router.post(
    "/documents/upload-sample/{filename}",
    response_model=DocumentUploadResponse,
    summary="Load a sample document by filename",
)
async def upload_sample_document(filename: str):
    """
    Load one of the built-in sample documents.

    Available: employee_handbook.txt, quarterly_report.txt,
    service_agreement.txt, technical_spec.txt, company_policy.txt
    """
    filepath = SAMPLE_DOCS_DIR / filename
    if not filepath.exists():
        available = [f.name for f in SAMPLE_DOCS_DIR.iterdir() if f.suffix == ".txt"]
        raise HTTPException(
            status_code=404,
            detail=f"Sample '{filename}' not found. Available: {available}",
        )

    content = filepath.read_text(encoding="utf-8")
    document = parse_document(filename, content)
    session = session_manager.create_session(document)

    return DocumentUploadResponse(
        session_id=session.session_id,
        document_name=document.filename,
        document_sections=document.section_count,
        document_chars=document.char_count,
    )


# ---------------------------------------------------------------------------
# Session Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/sessions/{session_id}",
    response_model=SessionInfo,
    summary="Get session information",
    responses={404: {"model": ErrorResponse}},
)
async def get_session(session_id: str):
    """Get the current state of a session (document info, turn count, etc.)."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    return SessionInfo(
        session_id=session.session_id,
        document_name=session.document.filename,
        document_chars=session.document.char_count,
        conversation_turns=len(session.history),
        created_at=session.created_at,
        last_activity=session.last_activity,
        is_summarized=session.is_summarized,
    )


@router.post(
    "/sessions/{session_id}/ask",
    response_model=QuestionResponse,
    summary="Ask a question about the document",
    responses={404: {"model": ErrorResponse}},
)
async def ask(session_id: str, request: QuestionRequest):
    """
    Ask a question against the uploaded document.

    Returns a structured answer with citations and confidence score.
    Prompt caching reduces cost for repeated questions against the same document.
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    # Get structured answer
    answer, usage = ask_question(session, request.question)

    # Determine if cache was hit
    cached = usage.get("cache_read_input_tokens", 0) > 0

    return QuestionResponse(
        session_id=session_id,
        question=request.question,
        answer=answer,
        cached=cached,
        usage=usage,
    )


@router.post(
    "/sessions/{session_id}/ask/stream",
    summary="Ask a question with streaming response (SSE)",
    responses={404: {"model": ErrorResponse}},
)
async def ask_stream(session_id: str, request: QuestionRequest):
    """
    Ask a question and receive the answer as a Server-Sent Events stream.

    Each event contains a text chunk. The stream ends with a [DONE] event.
    This provides real-time token delivery to the client.
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    def event_generator():
        gen = ask_question_stream(session, request.question)
        try:
            while True:
                chunk = next(gen)
                yield f"data: {chunk}\n\n"
        except StopIteration:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post(
    "/sessions/{session_id}/reset",
    response_model=SessionResetResponse,
    summary="Reset conversation, keep document",
    responses={404: {"model": ErrorResponse}},
)
async def reset_session(session_id: str):
    """
    Reset the conversation history but keep the document loaded.

    Use this when the user wants to start a fresh line of questioning
    without re-uploading the document.
    """
    session = session_manager.reset_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    return SessionResetResponse(session_id=session_id)


@router.delete(
    "/sessions/{session_id}",
    summary="Delete a session entirely",
    responses={404: {"model": ErrorResponse}},
)
async def delete_session(session_id: str):
    """Delete a session and all associated data."""
    deleted = session_manager.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session deleted"}


# ---------------------------------------------------------------------------
# Utility Endpoints
# ---------------------------------------------------------------------------

@router.get("/health", summary="Health check")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "mode": "mock" if is_mock_mode() else "live",
        "model": get_model_name(),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/documents/samples", summary="List available sample documents")
async def list_samples():
    """List the built-in sample documents."""
    samples = []
    if SAMPLE_DOCS_DIR.exists():
        for f in sorted(SAMPLE_DOCS_DIR.iterdir()):
            if f.suffix == ".txt":
                content = f.read_text(encoding="utf-8")
                samples.append({
                    "filename": f.name,
                    "size_chars": len(content),
                    "preview": content[:200].strip() + "...",
                })
    return {"samples": samples}
