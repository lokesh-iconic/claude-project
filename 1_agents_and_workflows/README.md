# Agents & Workflows — Support Ticket Triage System

A support ticket auto-triage system built **two ways** to demonstrate when to use a deterministic workflow vs. an autonomous agent, and to prove competence with the Claude Agent SDK patterns, hooks, subagents, and the PydanticAI framework.

## Problem Statement

Incoming support tickets need to be automatically classified, routed to the right team, and have a first-response drafted. This project implements the system as:

1. **Workflow** — A fixed 3-step prompt chain (classify → route → draft) with no model-driven branching
2. **Agent** — A tool-calling loop where Claude decides the sequence, can loop back, and escalates ambiguous cases to a specialist subagent

## Project Structure

```
1_agents_and_workflows/
├── README.md                          ← You are here
├── requirements.txt                   ← Dependencies
├── .env.example                       ← API key template
├── tickets.py                         ← 20 sample support tickets
├── shared.py                          ← Shared types, enums, formatting rules
│
├── workflow/
│   └── pipeline.py                    ← Deterministic 3-step pipeline
│
├── agent/
│   ├── tools.py                       ← Tool definitions (JSON schema + executors)
│   ├── hooks.py                       ← PostToolUse hook for draft formatting
│   ├── subagent.py                    ← Specialist classifier for ambiguous tickets
│   └── runner.py                      ← Agentic loop with tool calling
│
├── pydantic_ai_component/
│   └── classifier.py                  ← Classification rebuilt with PydanticAI
│
├── run_comparison.py                  ← Runs both systems and generates comparison
└── output/                            ← Generated comparison results
    ├── comparison.md
    └── results.json
```

## Setup

```bash
# From the repository root:
uv sync

# (Optional) Configure API key for live mode in .env
# Without an API key, everything runs in mock mode with deterministic responses
```

## Running

```bash
# Run the full comparison (recommended)
uv run python .\1_agents_and_workflows\run_comparison.py

# Or run individual modules:
uv run python .\1_agents_and_workflows\workflow\pipeline.py
uv run python .\1_agents_and_workflows\agent\runner.py
uv run python .\1_agents_and_workflows\pydantic_ai_component\classifier.py
```

## Architectural Decisions

### Workflow vs. Agent: When to Use Which

| Criterion | Workflow | Agent |
|-----------|----------|-------|
| **Input predictability** | ✅ Best when inputs are well-structured | Best when inputs are messy/ambiguous |
| **Execution cost** | ✅ Exactly 3 API calls per ticket | 4-6+ calls (classify + escalate? + route + draft) |
| **Latency** | ✅ Predictable, parallelizable | Variable, depends on model decisions |
| **Auditability** | ✅ Each step is a single prompt→response | Emergent reasoning, harder to trace |
| **Self-correction** | ❌ Cannot re-route or re-classify | ✅ Can loop back on conflicts |
| **Ambiguity handling** | Basic (uses keyword heuristics) | ✅ Escalates to specialist subagent |
| **Testing** | ✅ Unit-test each step independently | Integration tests needed |
| **Development speed** | ✅ Simpler, less code | More complex architecture |

**Rule of thumb**: Start with a workflow. Upgrade to an agent only when you observe that the workflow fails on ambiguous/variable inputs and the cost of those failures exceeds the cost of agent complexity.

### Why a Hook for Formatting (Not a Prompt)

The `hooks.py` module implements a `PostToolUse` hook that enforces formatting rules on every draft response. This is a hook rather than a prompt instruction because:

- **Deterministic guarantee**: Prompts are probabilistic. "Always include a greeting" works 95% of the time but fails unpredictably. The hook guarantees 100% compliance.
- **Separation of concerns**: The model focuses on writing good content. The hook handles structural formatting. Neither has to think about the other's job.
- **Testability**: The hook's `enforce_formatting()` function is a pure function — unit-testable with no API calls.

### Why a Subagent for Ambiguous Tickets (Not Inline Logic)

The `subagent.py` module handles tickets that don't clearly fit one category. It's a subagent (not inline logic in the main agent) because:

- **Richer prompt**: The specialist gets few-shot examples of tricky tickets and chain-of-thought instructions. Inlining this would bloat the main agent's context window.
- **Independent optimization**: The specialist's prompt can be tuned and evaluated separately. Its accuracy on ambiguous tickets doesn't interfere with the main agent's performance on clear-cut ones.
- **Conditional invocation**: The subagent is only called when needed (confidence < 0.7 or `is_ambiguous=True`). Clear-cut tickets skip it entirely, saving tokens and latency.
- **SDK alignment**: Maps directly to `AgentDefinition` in the Claude Agent SDK.

### PydanticAI: What It Made Easier and Harder

See the detailed analysis in [`pydantic_ai_component/classifier.py`](pydantic_ai_component/classifier.py) docstring.

**TL;DR**: PydanticAI excels at structured output validation and reduces boilerplate for tool registration. It's less ideal when you need fine-grained control over the prompt or want full visibility into the message flow.

## Assignment Requirements Mapping

> Reference: [`1_agents_and_workflows.txt`](../1_agents_and_workflows.txt)

### What This Proves

| Requirement | Where It's Demonstrated |
|-------------|------------------------|
| Apply the decision criteria for choosing a workflow versus an agent | [Workflow vs. Agent table](#workflow-vs-agent-when-to-use-which) above — documents when each is the right choice |
| Construct an agent with the Claude Agent SDK, including a custom loop and at least one hook | [`agent/runner.py`](agent/runner.py) (agentic loop), [`agent/hooks.py`](agent/hooks.py) (`PostToolUse` hook) |
| Use an agentic abstraction framework (e.g. LangGraph or PydanticAI) for at least one component | [`pydantic_ai_component/classifier.py`](pydantic_ai_component/classifier.py) — classification rebuilt with PydanticAI |
| Delegate a narrow subtask to a subagent and justify why it's a subagent and not inline logic | [`agent/subagent.py`](agent/subagent.py) — see [justification above](#why-a-subagent-for-ambiguous-tickets-not-inline-logic) |

### Build Steps

| Step | Requirement | Implementation |
|------|-------------|----------------|
| 1 | Build the workflow version first: a fixed classify → route → draft sequence | [`workflow/pipeline.py`](workflow/pipeline.py) — deterministic 3-step pipeline |
| 2 | Build the agent version: give it classify/route/draft as tools, let it decide the sequence | [`agent/runner.py`](agent/runner.py) + [`agent/tools.py`](agent/tools.py) — tool-calling loop |
| 3 | Add a hook that intercepts the draft-response step to enforce formatting deterministically | [`agent/hooks.py`](agent/hooks.py) — `DraftFormattingHook` as `PostToolUse` |
| 4 | Delegate ambiguous-ticket classification to a subagent with a specialized prompt | [`agent/subagent.py`](agent/subagent.py) — specialist classifier with few-shot examples |
| 5 | Rebuild one component using an agentic framework and note what it made easier/harder | [`pydantic_ai_component/classifier.py`](pydantic_ai_component/classifier.py) — see module docstring |
| 6 | Run both systems against your full ticket set and log where their outputs diverge | [`run_comparison.py`](run_comparison.py) → `output/comparison.md` |

### Setup

| Requirement | Implementation |
|-------------|----------------|
| Set up API access and the Claude Agent SDK | Root `.env` file + `uv sync` installs `anthropic` and `pydantic-ai` |
| Assemble 15-20 sample support tickets covering clear-cut and ambiguous cases | [`tickets.py`](tickets.py) — 20 tickets (15 clear-cut + 5 ambiguous) |

## Sample Tickets

The project includes 20 sample tickets across 5 categories:

| Category | Count | Ambiguous? | Examples |
|----------|-------|------------|----------|
| Billing | 4 | No | Double charge, promo code, invoice, refund |
| Technical | 5 | No | Login failure, API timeout, crash, webhook |
| Account | 3 | No | GDPR deletion, plan upgrade, ownership transfer |
| Feature Request | 3 | No | Dark mode, bulk export, mobile app |
| Ambiguous | 5 | Yes | Vague complaints, multi-topic, non-English |

The ambiguous tickets are designed to test edge cases:
- `TKT-016`: Vague complaint with no actionable detail
- `TKT-017`: Billing vs. technical discrepancy
- `TKT-018`: Escalated complaint bounced between teams
- `TKT-019`: Spanish-language multi-intent ticket
- `TKT-020`: Three issues in one message (billing + technical + feature request)

## Mock vs. Live Mode

- **Mock mode** (default, no API key): Uses keyword matching and templates for deterministic, reproducible results. Good for development and testing.
- **Live mode** (with `ANTHROPIC_API_KEY` in `.env`): Makes real API calls to Claude. Results will vary between runs but demonstrate true model capabilities.

Both modes produce identical output formats, so the comparison runner works with either.
