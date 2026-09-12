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
```
