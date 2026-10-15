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
| **Primary Model** | Claude Haiku 4.5 ($1.00/$5.00 per MTok) |
| **Comparison** | Claude Sonnet 4.6 ($3.00/$15.00 per MTok) |
| **Accuracy Bar** | ≥85% (defined upfront before running tests) |
| **Key Metric** | Accuracy + throughput (items/second) |
| **Verdict (mock)** | Both models use the same keyword classifier, so accuracy is equal by construction; Haiku clears the bar and costs less. Confirming that Sonnet adds nothing needs a live run on real data |

### Task B: Complex Reasoning (Extended Thinking)

| Attribute | Detail |
|-----------|--------|
| **Workload** | 5 multi-step problems (contracts, logic, pricing, system design, compliance) |
| **Fast Mode** | Claude Sonnet 4.6 with `max_tokens=4096`, no thinking |
| **Extended** | Claude Sonnet 4.6 with `thinking: {budget_tokens: 10000}` |
| **Key Metric** | Quality score (0-10 rubric per problem) vs. cost/latency |
| **Verdict (mock)** | Simulated rubric scores favour extended thinking at higher cost; treat them as illustrating the trade-off, not as measured quality |

### Task C: Long-Document Summarization (Prompt Caching)

| Attribute | Detail |
|-----------|--------|
| **Workload** | Summarize 3 long documents + follow-up questions |
| **Model** | Claude Sonnet 4.6 with `cache_control: {"type": "ephemeral"}` |
| **Baseline** | Same calls without caching |
| **Key Metric** | Cost per call (first vs. subsequent), total savings |
| **Verdict (mock)** | At real prices and simulated token counts, cache reads cost ~10% of full input, so repeat queries against the same document are much cheaper |

## Cost Tracking

Every API call (mock or live) is tracked by `tracker.py`:

| Metric | How It's Measured |
|--------|-------------------|
| **Input tokens** | From API response `usage.input_tokens` (live helpers) or simulated from text length (mock) |
| **Output tokens** | From API response `usage.output_tokens` |
| **Cache write tokens** | From `usage.cache_creation_input_tokens` |
| **Cache read tokens** | From `usage.cache_read_input_tokens` |
| **Thinking tokens** | From `usage.thinking_tokens` when the API reports it, otherwise estimated from the thinking text (live helper); simulated in mock mode |
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
| Would switching Task A to the most capable model improve outcomes? | **Not shown by the mock** — it gives both models identical accuracy by design, so the benchmark demonstrates the comparison harness and the 85% bar, not a real model difference. Run the live helpers in `task_a_classification/classifier.py` on your own labelled emails to decide. | Task A runner compares both models against the same 50-email dataset |
| Does caching on Task C show real, measured cost reduction? | **Computed, not measured** — cache reads are priced at ~10% of full input tokens, and the runner compares cached vs uncached cost per document using simulated token counts. A live run reports real `cache_creation_input_tokens` / `cache_read_input_tokens`. | Task C runner compares cached vs uncached costs per document |
| If a model release changed behavior on Task B, would you notice? | **Only with live scoring** — the 10-point rubric across 5 problems is granular enough to catch a 2-point regression, but the mock scores are simulated. | Each rubric criterion is independently scored |

## Mock vs. Live Mode

The runners (`run_all.py` and each `task_*/run.py`) always execute in **mock mode**; no API key is needed and none is used:
- **Mock responses** use keyword matching and templates
- **Token counts** are simulated from text length
- **Cost calculations** use real Anthropic pricing, so the formulas are the same ones a live run would use
- The mock classifier gives Haiku and Sonnet the same accuracy by design; the benchmark shows how to compare them, not which is better

The classifier, reasoner and summarizer modules also contain live helper functions (`classify_email_live`, `solve_extended_thinking_live`, `summarize_live_cached`, ...) that take an Anthropic client. Pass a client to those functions from your own script to measure real accuracy, latency and cache tokens; the bundled runners do not do this.
