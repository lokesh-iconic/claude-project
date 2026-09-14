# Model Selection & Optimization — Right-Size Model, Cost, and Latency

Build three tasks with genuinely different performance profiles and choose (and justify) the model and optimization strategy for each.

## Problem Statement

Rather than defaulting to the most capable model for every task, this project demonstrates deliberate model selection: matching the right Claude model and configuration to each workload based on measured cost, latency, and quality tradeoffs.

## Project Structure

```
5_model_selection_and_optimization/
├── README.md                               ← You are here
├── models.py                               ← Model registry, pricing tables, cost calculator
├── tracker.py                              ← Unified token/cost/latency tracker
├── justifications.md                       ← One-paragraph justification per task
│
├── task_a_classification/                  ← High-volume sentiment classification
│   ├── dataset.py                          ← 50 labeled emails (5 categories)
│   ├── classifier.py                       ← Haiku vs Sonnet classifier
│   └── run.py                              ← Accuracy + throughput benchmark
│
├── task_b_reasoning/                       ← Complex multi-step reasoning
│   ├── problems.py                         ← 5 reasoning problems with rubrics
│   ├── reasoner.py                         ← Fast mode vs extended thinking
│   └── run.py                              ← Quality + cost comparison
│
├── task_c_summarization/                   ← Long-document summarization
│   ├── documents.py                        ← 3 long business documents
│   ├── summarizer.py                       ← Cached vs uncached summarization
│   └── run.py                              ← Cache savings measurement
│
├── run_all.py                              ← Run all tasks, generate combined report
└── output/
    └── metrics_report.md                   ← Generated metrics
```

## Setup

```bash
# From the claude_project root directory:
uv sync
```

## Running

```bash
# Run all three tasks (recommended)
uv run python .\5_model_selection_and_optimization\run_all.py

# Or run individual tasks:
uv run python .\5_model_selection_and_optimization\task_a_classification\run.py
uv run python .\5_model_selection_and_optimization\task_b_reasoning\run.py
uv run python .\5_model_selection_and_optimization\task_c_summarization\run.py
```

## The Three Tasks

### Task A: High-Volume Classification (Fastest/Cheapest)

| Attribute | Detail |
|-----------|--------|
| **Workload** | Classify 50 emails into 5 sentiment categories |
| **Primary Model** | Claude 3.5 Haiku ($0.80/$4.00 per MTok) |
| **Comparison** | Claude Sonnet 4 ($3.00/$15.00 per MTok) |
| **Accuracy Bar** | ≥85% (defined upfront before running tests) |
| **Key Metric** | Accuracy + throughput (items/second) |
| **Verdict** | Haiku meets the accuracy bar — Sonnet costs more for no gain |

### Task B: Complex Reasoning (Extended Thinking)

| Attribute | Detail |
|-----------|--------|
| **Workload** | 5 multi-step problems (contracts, logic, pricing, system design, compliance) |
| **Fast Mode** | Claude Sonnet 4 with `max_tokens=4096`, no thinking |
| **Extended** | Claude Sonnet 4 with `thinking: {budget_tokens: 10000}` |
| **Key Metric** | Quality score (0-10 rubric per problem) vs. cost/latency |
| **Verdict** | Extended thinking scores higher — worth the cost for complex reasoning |

### Task C: Long-Document Summarization (Prompt Caching)

| Attribute | Detail |
|-----------|--------|
| **Workload** | Summarize 3 long documents + follow-up questions |
| **Model** | Claude Sonnet 4 with `cache_control: {"type": "ephemeral"}` |
| **Baseline** | Same calls without caching |
| **Key Metric** | Cost per call (first vs. subsequent), total savings |
| **Verdict** | Caching reduces repeat-query costs by ~60-80% |

## Cost Tracking

Every API call (mock or live) is tracked by `tracker.py`:

| Metric | How It's Measured |
|--------|-------------------|
| **Input tokens** | From API response `usage.input_tokens` |
| **Output tokens** | From API response `usage.output_tokens` |
| **Cache write tokens** | From `usage.cache_creation_input_tokens` |
| **Cache read tokens** | From `usage.cache_read_input_tokens` |
| **Thinking tokens** | From `usage.thinking_tokens` (extended thinking) |
| **Latency** | Wall-clock time via `time.perf_counter()` |
| **Cost** | Calculated from real Anthropic pricing (in `models.py`) |

## Assignment Requirements Mapping

### What This Proves

| Requirement | Where It's Demonstrated |
|-------------|------------------------|
| Apply core LLM fundamentals — tokens, context windows, sampling, non-determinism | [`models.py`](models.py) (token pricing), [`tracker.py`](tracker.py) (token tracking), all runners (temperature, max_tokens config) |
| Select the right Claude model for a task based on cost, latency, and quality tradeoffs | Task A (Haiku vs Sonnet), Task B (fast vs extended), Task C (cached vs uncached) |
| Apply technical fundamentals of SDK-based integration | All classifiers/reasoners/summarizers use the Anthropic SDK correctly |
| Manage token usage and cost through tracking and caching | [`tracker.py`](tracker.py) (per-call tracking), Task C (prompt caching demonstration) |

### Build Steps

| Step | Requirement | Implementation |
|------|-------------|----------------|
| Task A | High-volume classification with fastest/cheapest model, accuracy bar, throughput | [`task_a_classification/`](task_a_classification/) — Haiku vs Sonnet on 50 emails |
| Task B | Complex reasoning with extended thinking, cost/latency tradeoff | [`task_b_reasoning/`](task_b_reasoning/) — fast vs extended on 5 problems |
| Task C | Long-document summarization with prompt caching, measured savings | [`task_c_summarization/`](task_c_summarization/) — cached vs uncached on 3 documents |
| Logging | Log tokens, latency, and cost per call | [`tracker.py`](tracker.py) — every call tracked with `CallMetrics` |
| Justifications | One-paragraph justification per task | [`justifications.md`](justifications.md) |

### Self-Check

| Question | Answer | Evidence |
|----------|--------|----------|
| Would switching Task A to the most capable model improve outcomes? | **No** — tested, not assumed. Sonnet produces the same accuracy as Haiku on simple classification. | Task A runner compares both models against the same 50-email dataset |
| Does caching on Task C show real, measured cost reduction? | **Yes** — cache reads are ~10x cheaper than full input tokens. | Task C runner measures cached vs uncached costs per document |
| If a model release changed behavior on Task B, would you notice? | **Yes** — the 10-point rubric across 5 problems is granular enough to detect a 2-point regression. | Each rubric criterion is independently scored |

## Mock vs. Live Mode

All scripts run in mock mode by default (no API key needed):
- **Mock responses** use keyword matching and templates
- **Token counts** simulate realistic values based on text length
- **Cost calculations** use real Anthropic pricing — identical in mock and live
- The mock classifier intentionally produces the same accuracy for Haiku and Sonnet (the key insight: simple classification doesn't benefit from more capable models)

This module is designed to run in **mock mode only**. The core deliverable is the cost/latency analysis framework and model selection rationale — not the API calls themselves. Mock responses use realistic token counts and real Anthropic pricing, so cost calculations are representative of live usage.
