# Requirements Specification — Capstone Support Assistant

## What the Assistant Must Do

1. **Answer product questions** by searching a knowledge base of FAQs
2. **Look up order/account information** using customer-provided IDs
3. **Escalate unresolvable issues** by creating structured escalation tickets
4. **Handle ambiguous queries** via a specialist subagent for deeper analysis
5. **Maintain conversation context** across a multi-turn session without degradation

## What Systems It Touches

- **Anthropic Claude API** — for language understanding and generation (Haiku + Sonnet)
- **Mock Order Database** — 10 sample orders with status, items, tracking
- **Mock Account Database** — 5 customer accounts with plan, billing info
- **Knowledge Base** — 15 product FAQ entries served via MCP server
- **FastAPI Web Server** — HTTP endpoints for the chat interface

## What "Done" Means

1. A user can open the web UI, type a support question, and get a helpful answer
2. The assistant uses the right tool for each query type (verified by eval suite)
3. Prompt injection via customer messages is blocked (10/10 attack payloads)
4. Long conversations (15+ turns) don't degrade response quality (context compaction)
5. Cost is defensible: simple lookups use Haiku ($0.80/MTok), complex reasoning uses Sonnet ($3/MTok)
6. The eval suite passes all 10 cases including adversarial
7. Another engineer can deploy from `capstone/CLAUDE.md` without a walkthrough
8. The ship note is a real handoff document a team lead would approve
