# Applications & Integration -- DocuQuery

An internal document Q&A tool where employees upload a document and ask questions against it, with streamed responses, prompt caching, session management, and production-grade engineering practices.

## Quick Start

```bash
# From the claude_project root directory:

# 1. Install dependencies
uv sync

# 2. Start the server
uv run python -m uvicorn app.main:app --app-dir 2_applications_and_integration

# 3. Open in browser
# Swagger UI: http://localhost:8000/docs
# API root:   http://localhost:8000/
```

## Usage Example (curl)

```bash
# Upload a sample document
curl -X POST http://localhost:8000/api/v1/documents/upload-sample/employee_handbook.txt

# Response: {"session_id": "abc-123-...", "document_sections": 8, ...}

# Ask a question
curl -X POST http://localhost:8000/api/v1/sessions/{session_id}/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How much PTO do employees get?"}'

# Stream a response (SSE)
curl -X POST http://localhost:8000/api/v1/sessions/{session_id}/ask/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the 401k match policy?"}'
```

## Project Structure

```
2_applications_and_integration/
├── README.md                       <- You are here
├── requirements_spec.md            <- One-paragraph functional spec
├── config.yaml                     <- Model pinning + prompt versioning
├── code_review.md                  <- Peer review + fixes applied
├── app/
│   ├── main.py                     <- FastAPI entry point
│   ├── config.py                   <- Config loader (YAML + env vars)
│   ├── models.py                   <- Pydantic schemas (citations, confidence)
│   ├── document.py                 <- Document parsing into sections
│   ├── session.py                  <- Session lifecycle management
│   ├── claude_client.py            <- Claude API (streaming + caching)
│   └── routes.py                   <- REST API endpoints
├── sample_documents/               <- 5 sample business documents
└── tests/
    └── test_models.py              <- Schema validation tests
```

## REST API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/v1/documents/upload` | Upload a document (multipart) |
| `POST` | `/api/v1/documents/upload-sample/{name}` | Load a sample document |
| `GET` | `/api/v1/documents/samples` | List available samples |
| `POST` | `/api/v1/sessions/{id}/ask` | Ask a question (structured response) |
| `POST` | `/api/v1/sessions/{id}/ask/stream` | Ask with SSE streaming |
| `GET` | `/api/v1/sessions/{id}` | Get session info |
| `POST` | `/api/v1/sessions/{id}/reset` | Reset conversation |
| `DELETE` | `/api/v1/sessions/{id}` | Delete session |
| `GET` | `/api/v1/health` | Health check |

## Assignment Requirements Mapping

### 1. Requirements Spec
See [`requirements_spec.md`](requirements_spec.md) -- written before any code.

### 2. Core Integration (upload, question, streamed response)
- **Document upload**: `app/routes.py` -- `upload_document()` and `upload_sample_document()`
- **Question input**: `app/routes.py` -- `ask()` endpoint with validated `QuestionRequest`
- **Streamed response**: `app/routes.py` -- `ask_stream()` returns SSE via `StreamingResponse`
- **Claude API streaming**: `app/claude_client.py` -- `ask_question_stream()` uses `client.messages.stream()` with `text_stream`

### 3. Session Handling (documented decisions)
See `app/session.py` module docstring for all 5 decisions:
- **Create**: One session per document upload (UUID-based)
- **Persist**: Every turn is persisted immediately
- **Summarize**: When history exceeds ~40K tokens, older turns are collapsed
- **Restart**: Explicit `/reset` endpoint; new upload creates new session
- **Expire**: 30-minute idle timeout (configurable in `config.yaml`)

### 4. Prompt Caching
`app/claude_client.py` -- `_build_system_prompt()`:
- Document content placed in system prompt block with `cache_control: {"type": "ephemeral"}`
- First question against a document: full cost + cache write
- Subsequent questions: cache read only (~10% cost)
- Cache status reported in response `usage` field and `cached` boolean

### 5. JSON Schema (citations, confidence)
`app/models.py`:
- `Citation` -- section reference + direct quote + relevance score (0-1)
- `StructuredAnswer` -- answer + citations list + confidence level (high/medium/low/not_found)
- `export_schemas()` -- exports all models as JSON Schema for external validation
- All responses validated by Pydantic before sending to client

### 6. Configuration Management
`config.yaml` + `app/config.py`:
- **Model pinning**: `claude-sonnet-4-20250514` (never an alias)
- **Prompt versioning**: `system_v1` and `system_v2` with timestamps and change notes
- **Active version selector**: `prompts.active_version` key
- Changes tracked in git -- a prompt update shows as a config diff

### 7. Code Review
See [`code_review.md`](code_review.md):
- 4 issues identified (1 high, 2 medium, 1 low)
- High-severity issue (thread safety) fixed in `session.py`

### 8. Message Batches API -- Decision and Justification

**Decision: This workload should NOT use the Message Batches API.**

Reasons:

1. **Latency requirement**: Document Q&A is an interactive, real-time workflow. Users expect answers within seconds. The Batches API is designed for workloads that can tolerate hours of delay (batch processing, bulk analysis, offline evaluation). A user staring at a loading spinner for 24 hours is not a viable UX.

2. **Conversational context**: Each question depends on the conversation history from previous turns. Batches process requests independently -- you can't build a multi-turn conversation in a batch because turn N+1 depends on the answer from turn N.

3. **Streaming incompatibility**: The Batches API returns complete responses, not streamed tokens. Our SSE streaming endpoint (which delivers tokens in real-time) is a core feature that would be lost.

4. **Session state**: Our sessions carry mutable state (history, summaries) that updates after each answer. Batch processing has no concept of session mutation between requests.

**When Batches WOULD make sense for a Q&A tool**:
- Bulk pre-computation of FAQ answers from a document library
- Nightly processing of a queue of employee questions submitted during the day
- Evaluation/testing: running a test suite of 1000 questions against a document to measure answer quality

In these cases, the cost savings (50% discount) and higher throughput of the Batches API would outweigh the latency penalty.

## Mock vs. Live Mode

- **Mock mode** (default): Keyword-matching answers that cite relevant document sections. No API key needed.
- **Live mode**: Set `ANTHROPIC_API_KEY` in environment. Real Claude API calls with streaming and caching.

Both modes serve identical API responses (same Pydantic schemas), so the client code works unchanged.
