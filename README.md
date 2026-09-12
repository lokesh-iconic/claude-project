# Claude Project

A multi-module Python repository demonstrating Claude API integration patterns,
agent architectures, and production-grade application design.

## Project Structure

```
claude_project/
├── 1_agents_and_workflows/          <- Support ticket triage: workflow vs. agent comparison
├── 2_applications_and_integration/  <- DocuQuery: document Q&A with streaming, caching, sessions
├── 3_claude_code/                   <- Claude Code CLI: CLAUDE.md hierarchy, settings, commands
├── .env                             <- API key and model configuration
├── .gitignore                       <- Clean ignore rules for git
└── pyproject.toml                   <- Unified uv project dependencies
```

## Quick Start

```bash
# 1. Install all dependencies (using uv)
uv sync

# 2. Run Module 1 (Agents & Workflows comparison)
uv run python .\1_agents_and_workflows\run_comparison.py

# 3. Run Module 2 (DocuQuery FastAPI Server)
uv run python -m uvicorn app.main:app --app-dir 2_applications_and_integration
# Swagger UI available at: http://localhost:8000/docs

# 4. Run Module 3 (Claude Code Setup Validation)
uv run python .\3_claude_code\validate_setup.py
```

## Tests

```bash
# Run all test suites
uv run pytest 2_applications_and_integration/
```
