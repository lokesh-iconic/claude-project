# Claude Project

A multi-module Python repository demonstrating Claude API integration patterns,
agent architectures, and production-grade application design.

## Build & Run

```bash
# Install all dependencies (uses uv, not pip)
uv sync

# Run any module
uv run python .\1_agents_and_workflows\run_comparison.py
uv run python -m uvicorn app.main:app --app-dir 2_applications_and_integration
uv run python .\3_claude_code\validate_setup.py
```

## Test

```bash
uv run pytest 2_applications_and_integration/tests/
```

## Project Structure

- `1_agents_and_workflows/` — Support ticket triage: workflow vs. agent comparison
- `2_applications_and_integration/` — DocuQuery: document Q&A with streaming, caching, sessions
- `3_claude_code/` — Claude Code CLI: deliberate CLAUDE.md hierarchy and tools

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
