# Capstone: Production Support Assistant

A production-grade customer support assistant that integrates all 8 CCDV-F domain
assignments into a single deployable system.

## What It Does

- **Answers product questions** by searching a 15-article knowledge base
- **Looks up orders and accounts** using customer-provided IDs
- **Escalates unresolvable issues** via structured tickets with priority routing
- **Defends against prompt injection** with dual-layer deterministic guardrails
- **Manages costs** by routing simple tasks to Haiku and complex ones to Sonnet
- **Maintains conversation context** across long sessions without degradation

## Quick Start

```bash
# Self-test — demonstrates all 8 domains in one run
uv run python capstone/run_capstone.py

# Interactive CLI chat
uv run python capstone/run_capstone.py --interactive

# Web UI (FastAPI server)
uv run python capstone/run_capstone.py --server
# Open http://localhost:8000

# Run the eval suite (10 cases + seeded bug verification)
uv run python capstone/eval/run_evals.py

# Run only adversarial tests
uv run python capstone/eval/run_evals.py --adversarial-only

# Run secrets audit
uv run python capstone/security/secrets_audit.py
```

> **Note:** All features work in mock mode without an API key. Set `ANTHROPIC_API_KEY`
> in the root `.env` file for live Claude API calls.

## Domain Integration Matrix

| Domain | What It Contributes | Key Files |
|--------|---------------------|-----------|
| **1 — Agents & Workflows** | Agentic orchestrator, PostToolUse formatting hook, specialist subagent | `agent/orchestrator.py`, `agent/hooks.py`, `agent/subagent.py` |
| **2 — Applications** | FastAPI web app, session handling, config management, requirements spec | `app.py`, `config.yaml`, `requirements_spec.md` |
| **3 — Claude Code** | Project CLAUDE.md with architecture docs and `/run-evals` slash command | `CLAUDE.md` |
| **4 — Eval & Debugging** | 10 eval cases (4 core, 3 edge, 2 adversarial, 1 regression) + 2 seeded bugs | `eval/eval_suite.py`, `eval/seeded_bugs.py` |
| **5 — Model Selection** | Per-task model routing (Haiku vs Sonnet) with cost tracking and caching | `models/router.py`, `models/cost_tracker.py` |
| **6 — Prompt & Context** | 3-stage context pruning/compaction + defensive JSON parsing | `context/manager.py` |
| **7 — Security** | Dual-layer guardrails (pre + post processing) + secrets audit | `security/guardrails.py`, `security/secrets_audit.py` |
| **8 — Tools & MCP** | Custom tool (order/account lookup) + MCP server (knowledge base) | `agent/tools.py`, `data/mcp_server.py` |

## Architecture

```
Customer Message
       │
       ▼
┌─────────────────────┐
│  Pre-Processing     │ ◄── Domain 7: Regex injection detection
│  Security Guardrails │    (deterministic, code-based)
└──────────┬──────────┘
           │ allowed?
           ▼
┌─────────────────────┐
│  Context Manager    │ ◄── Domain 6: Prune/compact history
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Model Router       │ ◄── Domain 5: Haiku for lookups,
│  (classify intent)  │     Sonnet for reasoning
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Agentic Loop       │ ◄── Domain 1: Tool calling + escalation
│  (tool selection)   │     Domain 8: Custom tools + MCP
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Formatting Hook    │ ◄── Domain 1: Greeting, sign-off, tone
│  (deterministic)    │     (brand rules, not probabilistic)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Content Policy     │ ◄── Domain 7: Output sanitization
│  (post-processing)  │     (credential leak, prompt leak detection)
└──────────┬──────────┘
           │
           ▼
       Response
```

## Project Structure

```
capstone/
├── README.md              ← you are here
├── CLAUDE.md              ← architecture docs + /run-evals command (Domain 3)
├── config.yaml            ← model pinning, prompt versioning (Domain 2)
├── requirements_spec.md   ← what "done" means (Domain 2)
├── ship_note.md           ← one-page handoff document
├── app.py                 ← FastAPI web app with chat UI (Domain 2)
├── run_capstone.py        ← entry point (--test, --server, --interactive)
├── agent/
│   ├── orchestrator.py    ← main agentic loop (all domains)
│   ├── tools.py           ← custom tool definitions (Domain 8)
│   ├── hooks.py           ← PostToolUse formatting hook (Domain 1)
│   └── subagent.py        ← specialist for complex queries (Domain 1)
├── context/
│   └── manager.py         ← conversation pruning/compaction (Domain 6)
├── models/
│   ├── router.py          ← per-task model selection (Domain 5)
│   └── cost_tracker.py    ← token/cost tracking (Domain 5)
├── security/
│   ├── guardrails.py      ← dual-layer injection defense (Domain 7)
│   └── secrets_audit.py   ← secret storage verification (Domain 7)
├── data/
│   ├── orders.py          ← mock order/account database (10 orders, 5 accounts)
│   ├── knowledge_base.py  ← product FAQ (15 articles, 5 categories)
│   └── mcp_server.py      ← MCP server for knowledge base (Domain 8)
└── eval/
    ├── eval_suite.py      ← 10 eval cases (Domain 4)
    ├── seeded_bugs.py     ← 2 deliberately seeded bugs (Domain 4)
    └── run_evals.py       ← eval runner with pass/fail reporting
```

## Key Design Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| **Security model** | Code-based (regex), not prompt-based | Deterministic guardrails can't be talked out of firing |
| **Model strategy** | Haiku for lookups, Sonnet for reasoning | 3.75x cost savings on simple tasks with no quality loss |
| **Tool approach** | Custom tool for orders, MCP for knowledge base | Different coupling needs — per-user vs shared reference data |
| **Formatting** | PostToolUse hook, not prompt instructions | Brand rules must be deterministic, not probabilistic |
| **Context management** | Three-stage pruning/compaction | Prevents cost bloat in long support conversations |

## Seeded Bugs (Domain 4)

Two deliberately seeded bugs are documented with full trace analysis in `eval/seeded_bugs.py`:

1. **Bug 1 — Router Fallback**: Environment variable `CLAUDE_MODEL` overrides per-task model routing, sending all requests to Sonnet (3.75x cost increase)
2. **Bug 2 — Priority Case**: Escalation ticket parser doesn't normalize uppercase priority values from model output (e.g., `"URGENT"` → should be `"urgent"`)

Both include reproduction steps, trace analysis, and documented fixes.

## Eval Results

```
EVAL-001  core         Order lookup              ✓ PASS
EVAL-002  core         Account lookup            ✓ PASS
EVAL-003  core         FAQ answer                ✓ PASS
EVAL-004  core         Escalation                ✓ PASS
EVAL-005  edge         Missing data              ✓ PASS
EVAL-006  edge         Multi-intent              ✓ PASS
EVAL-007  edge         Non-English input          ✓ PASS
EVAL-008  adversarial  Prompt injection           ✓ PASS
EVAL-009  adversarial  Role hijack                ✓ PASS
EVAL-010  regression   Long conversation          ✓ PASS

Result: 10/10 cases passed
```
