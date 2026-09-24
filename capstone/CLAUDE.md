# Capstone Support Assistant — Project CLAUDE.md

## Architecture

This is a production-grade support assistant integrating all 8 CCDV-F domains
into a single deployable system. Customer messages flow through:

1. **Security guardrails** → regex-based injection detection (pre-processing)
2. **Context manager** → prunes/compacts conversation history to prevent bloat
3. **Model router** → selects Haiku ($0.80/MTok) or Sonnet ($3.00/MTok) per task
4. **Agentic loop** → model decides which tool to invoke
5. **Formatting hook** → deterministic greeting/sign-off enforcement
6. **Content policy** → post-processing output sanitization
7. **Cost tracker** → logs token usage and caching effectiveness

## File Structure

```
capstone/
├── CLAUDE.md              ← you are here
├── config.yaml            ← model pinning, prompt versioning
├── requirements_spec.md   ← what "done" means
├── app.py                 ← FastAPI web app
├── run_capstone.py        ← entry point (--test, --server, --interactive)
├── agent/
│   ├── orchestrator.py    ← main agentic loop
│   ├── tools.py           ← custom tool definitions (order/account lookup)
│   ├── hooks.py           ← PostToolUse formatting hook
│   └── subagent.py        ← specialist for complex/ambiguous queries
├── context/
│   └── manager.py         ← conversation pruning/compaction
├── models/
│   ├── router.py          ← per-task model selection
│   └── cost_tracker.py    ← token/cost tracking
├── security/
│   ├── guardrails.py      ← dual-layer injection defense
│   └── secrets_audit.py   ← secret storage verification
├── data/
│   ├── orders.py          ← mock order/account database
│   ├── knowledge_base.py  ← product FAQ (15 articles)
│   └── mcp_server.py      ← MCP server for knowledge base
├── eval/
│   ├── eval_suite.py      ← 10 eval cases
│   ├── seeded_bugs.py     ← 2 deliberately seeded bugs
│   └── run_evals.py       ← eval runner
└── ship_note.md           ← one-page handoff document
```

## Conventions

- **Model routing**: Never use a single model for everything. Haiku handles
  lookups/classification, Sonnet handles reasoning/drafting.
- **Security**: Customer messages are UNTRUSTED INPUT. All input passes through
  pre-processing guardrails. All output passes through content policy.
- **Config**: Model versions are pinned in `config.yaml`. Never use aliases
  like "claude-3-sonnet" that could silently change.
- **Tools vs MCP**: Order/account lookup = custom tool (tight integration).
  Knowledge base = MCP server (decoupled, reusable).
- **Mock mode**: All features work without an API key. Set `ANTHROPIC_API_KEY`
  in `.env` for live mode.

## Running

```bash
# Self-test (default) — demonstrates all 8 domains
uv run python capstone/run_capstone.py

# Interactive CLI chat
uv run python capstone/run_capstone.py --interactive

# FastAPI web server
uv run python capstone/run_capstone.py --server

# Eval suite
uv run python capstone/eval/run_evals.py

# Adversarial tests only
uv run python capstone/eval/run_evals.py --adversarial-only

# Secrets audit
uv run python capstone/security/secrets_audit.py
```

## Custom Slash Command: /run-evals

The team's most repeated task is running the eval suite after changes.
Instead of remembering the command path, use:

```
/run-evals              → runs all 10 eval cases + seeded bug verification
/run-evals adversarial  → runs only the 2 adversarial cases
/run-evals core         → runs only the 4 core scenario cases
```

Implementation: `uv run python capstone/eval/run_evals.py [--adversarial-only | --category <cat>]`
