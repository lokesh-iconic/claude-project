# Agents & Workflows — Local Conventions

This directory implements a support ticket triage system in two patterns.
These conventions supplement the project-level CLAUDE.md and apply **only**
inside this subdirectory.

## Architecture Rules

- **Workflow** (`workflow/pipeline.py`): fixed 3-step prompt chain
  (classify → route → draft). No model-driven branching. Each step is one
  prompt → one response.
- **Agent** (`agent/runner.py`): tool-calling loop. The model picks the
  sequence and can loop back. Uses tools defined in `agent/tools.py`.
- Never mix the two patterns in the same file.

## Hooks & Subagents

- Formatting enforcement belongs in `agent/hooks.py` as a PostToolUse hook,
  **not** in the prompt. The hook calls `shared.enforce_formatting()`.
- Ambiguous-ticket classification belongs in `agent/subagent.py`.
  The subagent is invoked only when `confidence < 0.7` or `is_ambiguous=True`.
- Do not inline subagent logic into the main agent loop.

## Naming Conventions (this directory only)

- Tool definition files: `tools.py` (JSON schema + executor in one file)
- Hook files: `hooks.py` (one hook per lifecycle event)
- Pydantic models: defined in `shared.py`, imported everywhere else
- Sample data: defined in `tickets.py` as a list of dicts

## Running (from repo root)

```bash
uv run python .\1_agents_and_workflows\workflow\pipeline.py
uv run python .\1_agents_and_workflows\agent\runner.py
uv run python .\1_agents_and_workflows\run_comparison.py
```

## Output

All generated output goes to `output/`. This directory is gitignored.
