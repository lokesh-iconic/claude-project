# Claude Project

A multi-module Python repository demonstrating Claude API integration patterns,
agent architectures, and production-grade application design — culminating in a
capstone project that integrates all 8 domains into a unified support assistant.

## What This Project Is About

This repository is a hands-on learning portfolio for building applications on top of
Claude. Each numbered folder is a self-contained exercise on one skill an AI application
developer needs, and the capstone combines all of them into one working product.

| Skill | Where | The question it answers |
|-------|-------|-------------------------|
| Workflows vs. agents | `1_` | When should a fixed pipeline be used, and when should Claude decide the steps? |
| Application building | `2_` | How do you build a real API around Claude (streaming, caching, sessions, config)? |
| Claude Code | `3_` | How do you configure Claude Code for a repository (CLAUDE.md, commands, headless mode)? |
| Evals and debugging | `4_` | When something breaks, is it a code bug or a model-output problem? |
| Model selection | `5_` | Which model, and which cost/latency trade-offs, fit which workload? |
| Prompt and context engineering | `6_` | How do you keep a long conversation reliable and well-formatted? |
| Security | `7_` | How do you defend against prompt injection and protect secrets? |
| Tools and MCP | `8_` | When should a capability be a custom tool, a Skill, or an MCP server? |
| Capstone | `capstone/` | Can all of the above work together in one customer-support assistant? |

Most modules use the same running example (a customer-support assistant that triages
tickets, looks up orders, and answers questions) so the techniques can be compared
directly. Every module is designed to run without an API key in **mock mode**, which uses
deterministic canned responses, and to switch to **live mode** automatically when
`ANTHROPIC_API_KEY` is set (copy `.env.example` to `.env` and fill it in). See each
module's own README for details, including which parts of a module have a live mode.

## Intentionally Flawed Code

Some parts of the repository are flawed on purpose because the exercise is to find, trace,
or defend against the flaw:

| Where | What is deliberate |
|-------|--------------------|
| `4_eval_testing_and_debugging/broken_app/` | An integration bug (`is_ambiguous` ignored when routing) and a vague system prompt without a priority rubric. `fixed_app/` differs from it only in those two places. |
| `7_security_and_safety/vulnerable_app/` | Untrusted text pasted into the prompt, no-op hooks, two hardcoded fake secrets, and actions with no access control. |
| `capstone/eval/seeded_bugs.py` | Bug 1 (model-routing override) is fixed and guarded by an eval; Bug 2 (uppercase priority not normalized) is left in the code so the verification can detect it. |

## What Is the Anthropic SDK, and Why Is It Used?

The **Anthropic SDK** is Anthropic's official Python library (the `anthropic` package,
listed in `pyproject.toml`) for calling Claude from code. Without it, every call would be
a hand-built HTTP request to the Claude API: you would write the headers, authentication,
JSON bodies, retries, and response parsing yourself.

The SDK wraps that in a typed Python interface, for example:

```python
import anthropic

client = anthropic.Anthropic()          # reads ANTHROPIC_API_KEY from the environment
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Summarize this ticket..."}],
)
```

This project uses it because it provides, out of the box, the things every module needs:

- **The Messages API**: sending a conversation and reading Claude's reply.
- **Streaming**: receiving a response token by token (used by the DocuQuery app in module 2).
- **Tool use**: letting Claude request that your code run a function, which is the basis of
  the agents in modules 1, 4, 8 and the capstone.
- **Prompt caching and extended thinking**: the cost and quality features used in
  modules 2 and 5.
- **Authentication, automatic retries, and typed errors**: for example
  `anthropic.AuthenticationError` and `anthropic.NotFoundError`, which the modules use to
  detect a bad key or an unknown model and fall back to mock mode.
- **Usage data**: every response reports its input and output tokens, which the cost
  trackers use.

Two clarifications:

- The agents here are built as a plain loop over the SDK's Messages API (call Claude, run
  the requested tool, send the result back, repeat). They do not use the separate
  *Claude Agent SDK* product.
- The SDK is the library for building applications **with** Claude. *Claude Code* (module
  3) is a different thing: Anthropic's command-line coding assistant that you use
  interactively or from scripts.

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
├── .env.example                         ← Template for .env (API key and optional model settings)
├── .gitignore                           ← Ignore rules for git
└── pyproject.toml                       ← Unified uv project dependencies
```

## Quick Start

```bash
# 1. Install all dependencies (using uv)
uv sync

# 2. (Optional) enable live mode: copy .env.example to .env and set ANTHROPIC_API_KEY
copy .env.example .env        # PowerShell / cmd; use cp on macOS/Linux

# 3. Run ALL 8 modules sequentially (mock mode needs no key)
uv run python main.py

# Or run individual modules:

# Module 1 — Agents & Workflows comparison
uv run python .\1_agents_and_workflows\run_comparison.py

# Module 2 — DocuQuery FastAPI Server (validation runner, then the server)
uv run python ._applications_and_integrationun_validation.py
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
| **1** | Build a Ticket Triage System — Twice | Workflow vs. agent decision criteria, a tool-calling agent loop, hooks, subagents, PydanticAI |
| **2** | Build and Ship a Claude-Powered Document Q&A Application | Claude API mechanics (streaming, caching, batches), REST API design, session hygiene, config management |
| **3** | Operate Claude Code Across a Real Repository | CLAUDE.md hierarchy, custom commands, headless mode, memory verification (config files are templates to copy into the repo root) |
| **4** | Diagnose and Fix a Deliberately Broken Claude Application | Error classification, trace analysis, separating integration bugs from model-output problems (mock mode simulates the model) |
| **5** | Right-Size Model, Cost, and Latency Across Three Workloads | Model selection (Haiku vs Sonnet), extended thinking, prompt caching, token/cost tracking |
| **6** | Engineer a Prompt and Context Pipeline That Survives a Long Session | Context compaction, instruction anchoring, subagent isolation, defensive structured output parsing |
| **7** | Defend a Claude Application Against Prompt Injection | Layered defenses (code hooks, content policy, input isolation), per-layer checks, secrets audit, identity validation |
| **8** | Build the Same Capability Three Ways — Tool, Skill, MCP | Custom tool vs. Skill vs. MCP server tradeoffs, structured errors, equivalence testing |
| **Capstone** | Production Support Assistant | Integrates all 8 domains: agentic orchestrator, FastAPI app, CLAUDE.md, eval suite, model routing, context management, security guardrails, custom tools + MCP |

## Running All Modules

```bash
# Run all 8 individual modules
uv run python main.py

# Run the capstone integration project
uv run python capstone/run_capstone.py
```

`main.py` executes every module sequentially, prints a pass/fail summary with per-module timing, saves a markdown report to `output/run_report.md`, and exits non-zero if any module fails. The capstone is run separately (see above).

The capstone project (`capstone/`) integrates all 8 domains into a single production-grade support assistant. See [`capstone/README.md`](capstone/README.md) for full documentation.
