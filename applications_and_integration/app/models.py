"""
app/models.py -- Pydantic models and JSON schemas.

Defines the request/response schemas for the REST API and the structured
answer format with citations and confidence scores.

Design decision: All response schemas use Pydantic V2 so they:
  1. Self-document the API (FastAPI auto-generates OpenAPI docs from these)
  2. Validate responses before sending to the client
  3. Can be exported as JSON Schema for external consumers
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ConfidenceLevel(str, Enum):
    """How confident the model is that the answer is in the document."""
    HIGH = "high"           # Answer directly stated in document
    MEDIUM = "medium"       # Answer inferred from document content
    LOW = "low"             # Answer partially supported
    NOT_FOUND = "not_found" # Answer not in document


# ---------------------------------------------------------------------------
# Citation Schema
# ---------------------------------------------------------------------------

class Citation(BaseModel):
    """
    A reference to a specific part of the uploaded document.

    JSON Schema requirement: structured citations with section references
    and confidence scores, validated against schema.
    """
    section: str = Field(
        description="Section name or number (e.g., 'Section 2.3', 'Article 5')",
    )
    quote: str = Field(
        description="Relevant quote from the document (direct text)",
    )
    relevance: float = Field(
        ge=0.0, le=1.0,
        description="How relevant this citation is to the answer (0-1)",
    )


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------

class DocumentUploadResponse(BaseModel):
    """Response after uploading a document."""
    session_id: str = Field(description="Unique session identifier (UUID)")
    document_name: str = Field(description="Name of the uploaded document")
    document_sections: int = Field(description="Number of sections detected")
    document_chars: int = Field(description="Total character count")
    message: str = Field(default="Document uploaded successfully")


class QuestionRequest(BaseModel):
    """Request to ask a question against the uploaded document."""
    question: str = Field(
        min_length=1,
        max_length=2000,
        description="The question to ask about the document",
    )


# ---------------------------------------------------------------------------
# Response Schemas
# ---------------------------------------------------------------------------

class StructuredAnswer(BaseModel):
    """
    The structured response to a document question.

    This schema is validated on every response to guarantee consistency.
    Citations reference specific document sections so the user can verify.
    """
    answer: str = Field(
        description="The natural-language answer to the question",
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="Source citations from the document",
    )
    confidence: ConfidenceLevel = Field(
        description="Overall confidence that the answer is supported by the document",
    )
    follow_up_suggestions: list[str] = Field(
        default_factory=list,
        description="Suggested follow-up questions the user might ask",
    )


class QuestionResponse(BaseModel):
    """Full response to a question, including metadata."""
    session_id: str
    question: str
    answer: StructuredAnswer
    cached: bool = Field(
        default=False,
        description="Whether the document content was served from prompt cache",
    )
    usage: Optional[dict] = Field(
        default=None,
        description="Token usage breakdown (input, output, cache_read, cache_creation)",
    )
    timestamp: datetime = Field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# Session Schemas
# ---------------------------------------------------------------------------

class SessionInfo(BaseModel):
    """Public view of a session's state."""
    session_id: str
    document_name: str
    document_chars: int
    conversation_turns: int
    created_at: datetime
    last_activity: datetime
    is_summarized: bool = Field(
        default=False,
        description="Whether older conversation turns have been summarized",
    )


class SessionResetResponse(BaseModel):
    """Response after resetting a session."""
    session_id: str
    message: str = "Session conversation reset. Document retained."
    conversation_turns: int = 0


# ---------------------------------------------------------------------------
# Error Schemas
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None


# ---------------------------------------------------------------------------
# JSON Schema Export (for documentation / external validation)
# ---------------------------------------------------------------------------

def export_schemas() -> dict:
    """
    Export all response schemas as JSON Schema.

    This can be used by:
      - External consumers who want to validate our responses
      - Documentation generators
      - Contract testing
    """
    return {
        "StructuredAnswer": StructuredAnswer.model_json_schema(),
        "Citation": Citation.model_json_schema(),
        "QuestionResponse": QuestionResponse.model_json_schema(),
        "DocumentUploadResponse": DocumentUploadResponse.model_json_schema(),
        "SessionInfo": SessionInfo.model_json_schema(),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(export_schemas(), indent=2))
