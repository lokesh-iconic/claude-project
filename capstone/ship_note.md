# Ship Note — Capstone Support Assistant

**Date:** 2025-09-21
**Author:** CCDV-F Capstone Project
**Status:** Ready for Review

---

## What It Does

A production-grade customer support assistant that:
- Answers product questions from a 15-article knowledge base
- Looks up orders and accounts using real (mock) data
- Escalates unresolvable issues via structured tickets
- Defends against prompt injection attacks deterministically
- Manages costs by routing simple tasks to Haiku and complex ones to Sonnet

## Architecture Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Security model | Code-based (regex), not prompt-based | Deterministic guardrails can't be talked out of firing |
| Model strategy | Haiku for lookups, Sonnet for reasoning | 3.75x cost savings on simple tasks with no quality loss |
| Tool approach | Custom tool for orders, MCP for knowledge base | Different coupling needs — per-user vs shared reference data |
| Formatting | PostToolUse hook, not prompt instructions | Brand rules must be deterministic, not probabilistic |
| Context management | Three-stage pruning/compaction | Prevents cost bloat in long support conversations |

## What's Tested

- **10 eval cases**: 4 core, 3 edge, 2 adversarial, 1 regression
- **2 seeded bugs**: integration-layer (router fallback) + model-output (case normalization)
- **Secrets audit**: verifies no hardcoded API keys in source

## Known Limitations

1. **Mock-only data**: Order/account data is hardcoded, not backed by a real database
2. **No authentication**: Web UI has no user authentication (demo scope)
3. **Single-server sessions**: In-memory session store doesn't survive restarts
4. **MCP server not auto-started**: Knowledge base MCP server must be started separately for full MCP integration

## Next Improvement

**Priority: Add persistent session storage** — Replace the in-memory dict with SQLite or Redis so sessions survive server restarts. This is the most impactful change for production readiness (estimated: 2-3 hours).

---

*Reviewed by:* ______________________ *Date:* __________
