# Claude Project

A multi-module Python repository demonstrating Claude API integration patterns,
agent architectures, and production-grade application design — culminating in a
capstone project that integrates all 8 domains into a unified support assistant.

## Project Structure

```
claude_project/
├── 1_agents_and_workflows/              ← Support ticket triage: workflow vs. agent comparison
├── 2_applications_and_integration/      ← DocuQuery: document Q&A with streaming, caching, sessions
├── 3_claude_code/                       ← Claude Code CLI: CLAUDE.md hierarchy, settings, commands
├── 4_eval_testing_and_debugging/        ← Diagnose & fix a deliberately broken Claude application
├── 5_model_selection_and_optimization/  ← Right-size model, cost, and latency across three workloads
├── 6_prompt_and_context_engineering/    ← Multi-turn assistant with context compaction and drift testing
├── 7_security_and_safety/              ← Prompt injection attack/defense + secrets audit
├── 8_tools_and_MCPs/                   ← Same capability three ways: custom tool, skill, MCP server
├── capstone/                            ← CAPSTONE: Production support assistant integrating all 8 domains
├── main.py                              ← Run all 8 modules sequentially
├── .env                                 ← API key and model configuration
├── .gitignore                           ← Clean ignore rules for git
└── pyproject.toml                       ← Unified uv project dependencies
```

## Quick Start

```bash
# 1. Install all dependencies (using uv)
uv sync

# 2. Run ALL 8 modules sequentially
uv run python main.py

# Or run individual modules:

# Module 1 — Agents & Workflows comparison
uv run python .\1_agents_and_workflows\run_comparison.py

# Module 2 — DocuQuery FastAPI Server
uv run python -m uvicorn app.main:app --app-dir 2_applications_and_integration
# Swagger UI available at: http://localhost:8000/docs

# Module 3 — Claude Code Setup Validation
uv run python .\3_claude_code\validate_setup.py

# Module 4 — Eval, Testing & Debugging
uv run python .\4_eval_testing_and_debugging\run_comparison.py

# Module 5 — Model Selection & Optimization
uv run python .\5_model_selection_and_optimization\run_all.py

# Module 6 — Prompt & Context Engineering
uv run python .\6_prompt_and_context_engineering\run_session.py
uv run python .\6_prompt_and_context_engineering\run_parser_test.py

# Module 7 — Security & Safety
uv run python .\7_security_and_safety\run_comparison.py

# Module 8 — Tools and MCPs
uv run python .\8_tools_and_MCPs\run_all.py

# ── CAPSTONE PROJECT ──

# Run the capstone self-test (demonstrates all 8 domains)
uv run python capstone/run_capstone.py

# Run the capstone eval suite (10 cases + seeded bug verification)
uv run python capstone/eval/run_evals.py

# Run the capstone secrets audit
uv run python capstone/security/secrets_audit.py

# Start the capstone web UI
uv run python capstone/run_capstone.py --server
# Chat UI available at: http://localhost:8000
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
| **7** | Defend a Claude Application Against Prompt Injection | Layered defenses (code hooks, content policy, input isolation), secrets audit, identity validation |
| **8** | Build the Same Capability Three Ways — Tool, Skill, MCP | Custom tool vs. Skill vs. MCP server tradeoffs, structured errors, equivalence testing |
| **Capstone** | Production Support Assistant | Integrates all 8 domains: agentic orchestrator, FastAPI app, CLAUDE.md, eval suite, model routing, context management, security guardrails, custom tools + MCP |

## Running All Modules

```bash
# Run all 8 individual modules
uv run python main.py

# Run the capstone integration project
uv run python capstone/run_capstone.py
```

`main.py` executes every module sequentially, prints a pass/fail summary with per-module timing, and saves a markdown report to `output/run_report.md`.

The capstone project (`capstone/`) integrates all 8 domains into a single production-grade support assistant. See [`capstone/README.md`](capstone/README.md) for full documentation.
