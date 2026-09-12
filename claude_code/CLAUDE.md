# Claude Project

A multi-module Python repository demonstrating Claude API integration patterns,
agent architectures, and production-grade application design.

## Build & Run

```bash
# Install all dependencies (uses uv, not pip)
uv sync

# Run any module
uv run python -m agents_and_workflows.workflow.pipeline
uv run python -m agents_and_workflows.agent.runner
uv run python -m agents_and_workflows.run_comparison
uv run python -m applications_and_integration.app.main
```

## Test

```bash
uv run pytest
uv run pytest applications_and_integration/tests/
```

## Project Structure

- `agents_and_workflows/` — Support ticket triage: workflow vs. agent comparison
- `applications_and_integration/` — DocuQuery: document Q&A with streaming, caching, sessions

## Coding Standards

- Python 3.13+ required
- Use Pydantic models for all structured data (inputs, outputs, API schemas)
- Type hints on every function signature — no untyped public functions
- Use `from __future__ import annotations` for forward references
- Prefer `str` enums (`class Foo(str, Enum)`) for JSON-serializable constants
- Imports: stdlib → third-party → local, separated by blank lines
- Mock mode must be the default for all modules — never require an API key to run

## Environment

- Package manager: `uv` (not pip, not poetry)
- Virtual environment: `.venv/` (managed by uv)
- Config files: `pyproject.toml` (no setup.py, no requirements.txt for root)
- API keys go in `.env` files, loaded via `python-dotenv`, never hardcoded
