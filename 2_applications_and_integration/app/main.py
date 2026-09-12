"""
app/main.py -- FastAPI application entry point.

Starts the DocuQuery server. Includes:
  - CORS middleware (for internal tool usage)
  - Router mounting
  - Startup banner with mode and config info
"""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import is_mock_mode, get_model_name
from app.routes import router


# ---------------------------------------------------------------------------
# Application Setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="DocuQuery",
    description=(
        "Internal document Q&A tool. Upload a document and ask questions "
        "against it with streamed, citation-backed answers."
    ),
    version="1.0.0",
    docs_url="/docs",       # Swagger UI
    redoc_url="/redoc",     # ReDoc
)

# CORS for internal tool access (browser-based clients)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Internal tool -- restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Root Endpoint
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    """Welcome endpoint with API info."""
    return {
        "name": "DocuQuery",
        "version": "1.0.0",
        "mode": "mock" if is_mock_mode() else "live",
        "model": get_model_name(),
        "docs": "/docs",
        "api_prefix": "/api/v1",
        "endpoints": {
            "upload_document": "POST /api/v1/documents/upload",
            "upload_sample": "POST /api/v1/documents/upload-sample/{filename}",
            "list_samples": "GET /api/v1/documents/samples",
            "ask_question": "POST /api/v1/sessions/{id}/ask",
            "ask_stream": "POST /api/v1/sessions/{id}/ask/stream",
            "get_session": "GET /api/v1/sessions/{id}",
            "reset_session": "POST /api/v1/sessions/{id}/reset",
            "delete_session": "DELETE /api/v1/sessions/{id}",
            "health": "GET /api/v1/health",
        },
    }


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mode = "MOCK (no API key)" if is_mock_mode() else "LIVE (Anthropic API)"
    print()
    print("=" * 60)
    print("  DocuQuery - Document Q&A Tool")
    print("=" * 60)
    print(f"  Mode:  {mode}")
    print(f"  Model: {get_model_name()}")
    print(f"  Docs:  http://localhost:8000/docs")
    print(f"  API:   http://localhost:8000/api/v1")
    print("=" * 60)
    print()

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
