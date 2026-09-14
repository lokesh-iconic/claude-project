# Claude Project

A multi-module Python repository demonstrating Claude API integration patterns,
agent architectures, and production-grade application design.

## Project Structure

```
claude_project/
├── 1_agents_and_workflows/              ← Support ticket triage: workflow vs. agent comparison
├── 2_applications_and_integration/      ← DocuQuery: document Q&A with streaming, caching, sessions
├── 3_claude_code/                       ← Claude Code CLI: CLAUDE.md hierarchy, settings, commands
├── 4_eval_testing_and_debugging/        ← Diagnose & fix a deliberately broken Claude application
├── 5_model_selection_and_optimization/  ← Right-size model, cost, and latency across three workloads
├── 6_prompt_and_context_engineering/    ← Multi-turn assistant with context compaction and drift testing
├── .env                                 ← API key and model configuration
├── .gitignore                           ← Clean ignore rules for git
└── pyproject.toml                       ← Unified uv project dependencies
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

# 5. Run Module 4 (Eval, Testing & Debugging — side-by-side comparison)
uv run python .\4_eval_testing_and_debugging\run_comparison.py

# 6. Run Module 5 (Model Selection & Optimization — all tasks)
uv run python .\5_model_selection_and_optimization\run_all.py

# 7. Run Module 6 (Prompt & Context Engineering — session + parser test)
uv run python .\6_prompt_and_context_engineering\run_session.py
uv run python .\6_prompt_and_context_engineering\run_parser_test.py
```

## Module Overview

| Module | Title | What It Proves |
|--------|-------|---------------|
| **1** | Build a Ticket Triage System — Twice | Workflow vs. agent decision criteria, Claude Agent SDK, hooks, subagents, PydanticAI |
| **2** | Build and Ship a Claude-Powered Document Q&A Application | Claude API mechanics (streaming, caching, batches), REST API design, session hygiene, config management |
| **3** | Operate Claude Code Across a Real Repository | CLAUDE.md hierarchy, custom commands, headless mode, memory verification |
| **4** | Diagnose and Fix a Deliberately Broken Claude Application | Error classification, trace analysis, separating integration bugs from model-output problems |
| **5** | Right-Size Model, Cost, and Latency Across Three Workloads | Model selection (Haiku vs Sonnet), extended thinking, prompt caching, token/cost tracking |
| **6** | Engineer a Prompt and Context Pipeline That Survives a Long Session | Context compaction, instruction anchoring, subagent isolation, defensive structured output parsing |

## Tests

```bash
# Run all test suites
uv run pytest 2_applications_and_integration/
```
