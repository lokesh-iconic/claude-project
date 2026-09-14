# Eval, Testing & Debugging — Diagnose and Fix a Deliberately Broken Claude Application

Take a working Claude integration, deliberately break it in two different layers, diagnose both bugs using trace analysis, then fix each one using the layer-appropriate strategy.

## Problem Statement

This project demonstrates the ability to correctly **isolate integration-layer bugs from model-output problems** in a Claude application. Two bugs were introduced into the working Domain 1 Agent (support ticket triage system):

1. **Bug 1 (Integration Layer)**: A dropped field in the data flow between tools
2. **Bug 2 (Model Output)**: A vague prompt causing inconsistent classification

Both bugs produce similar symptoms ("routing doesn't work right") but require completely different diagnostic approaches and completely different fixes.

## Project Structure

```
4_eval_testing_and_debugging/
├── README.md                           ← You are here
├── __init__.py
├── shared.py                           ← Shared types (unchanged from Domain 1)
├── tickets.py                          ← 20 sample tickets (unchanged from Domain 1)
├── tracer.py                           ← Trace instrumentation + anomaly detection
│
├── broken_app/                         ← Deliberately broken version
│   ├── __init__.py
│   ├── tools.py                        ← ⬅ BUG 1: is_ambiguous hardcoded to False
│   ├── runner.py                       ← ⬅ BUG 2: vague prompt, no priority rubric
│   ├── hooks.py                        ← Unchanged
│   └── subagent.py                     ← Unchanged
│
├── fixed_app/                          ← Both bugs fixed
│   ├── __init__.py
│   ├── tools.py                        ← ✅ FIX 1: is_ambiguous read from args
│   ├── runner.py                       ← ✅ FIX 2: explicit priority rubric in prompt
│   ├── hooks.py                        ← Unchanged
│   └── subagent.py                     ← Unchanged
│
├── diagnosis/
│   ├── hypothesis.md                   ← Pre-analysis hypotheses (symptom → guess)
│   └── trace_analysis.md              ← Post-trace analysis (confirm/reject)
│
├── run_broken.py                       ← Run broken system + capture traces
├── run_fixed.py                        ← Run fixed system + verify fixes
├── run_comparison.py                   ← Side-by-side diff (broken vs fixed)
└── output/                             ← Generated trace files and reports
    ├── broken_traces.json
    ├── fixed_traces.json
    └── comparison.md
```

## Setup

```bash
# From the claude_project root directory:
uv sync
```

## Running

```bash
# Run the broken version (shows both bugs in action)
uv run python .\4_eval_testing_and_debugging\run_broken.py

# Run the fixed version (verifies both bugs are resolved)
uv run python .\4_eval_testing_and_debugging\run_fixed.py

# Run side-by-side comparison (recommended — shows the full diagnostic picture)
uv run python .\4_eval_testing_and_debugging\run_comparison.py
```

## The Two Bugs

### Bug 1: Integration-Layer Bug (Dropped Field)

| Attribute | Detail |
|-----------|--------|
| **File** | `broken_app/tools.py` → `execute_route_ticket()` |
| **What** | `is_ambiguous` hardcoded to `False` instead of reading from `args` |
| **Effect** | Ambiguous tickets never trigger escalation during routing |
| **Symptom** | Classifier says ambiguous, specialist fires, but routing says `escalate: false` |
| **Why it's non-obvious** | Classification is correct. Subagent works. The bug is in the **integration glue** between tools. |
| **Fix** | Code change: `is_ambiguous = args.get("is_ambiguous", False)` |

### Bug 2: Model-Output Problem (Vague Prompt)

| Attribute | Detail |
|-----------|--------|
| **File** | `broken_app/runner.py` → `AGENT_SYSTEM_PROMPT` |
| **What** | Priority guidance removed; replaced with "determine how important it seems" |
| **Effect** | Priorities inconsistently assigned (urgent/high → medium) |
| **Symptom** | Double-charge tickets get `medium` priority instead of `high` |
| **Why it's non-obvious** | Code is correct. Tool schemas accept all values. The prompt just doesn't constrain enough. |
| **Fix** | Prompt change: explicit URGENT/HIGH/MEDIUM/LOW rubric |

## Diagnostic Process

### Step 1: Observe Symptoms

Run the broken system and note the output:
- Ambiguous tickets aren't being escalated
- Priority levels seem too low for urgent/high-severity tickets

### Step 2: Write Hypotheses (Before Looking at Code)

See [`diagnosis/hypothesis.md`](diagnosis/hypothesis.md):
- **Bug 1 hypothesis**: Field lost between classification and routing
- **Bug 2 hypothesis**: Vague prompt causes model to default to "medium"

### Step 3: Instrument and Trace

The `tracer.py` module instruments every tool call:
- Captures inputs and outputs at each step
- Compares outputs of step N with inputs of step N+1 (detects dropped fields)
- Compares classifier output with ground truth (detects wrong priorities)
- Flags anomalies automatically

### Step 4: Analyze Traces

See [`diagnosis/trace_analysis.md`](diagnosis/trace_analysis.md):
- **Bug 1**: Trace shows `is_ambiguous=True` in route_args but `False` inside the function → confirmed as integration bug
- **Bug 2**: Trace shows systematic priority downgrades → confirmed as prompt problem

### Step 5: Fix (Layer-Appropriate)

- **Bug 1**: Code fix in `tools.py` (integration layer → code change)
- **Bug 2**: Prompt fix in `runner.py` (model output layer → prompt change)

## Assignment Requirements Mapping

### What This Proves

| Requirement | Where It's Demonstrated |
|-------------|------------------------|
| Identify and classify error types in a Claude application | Bug 1 classified as integration-layer, Bug 2 classified as model-output — see [The Two Bugs](#the-two-bugs) |
| Select an appropriate recovery strategy per error type | Code fix for Bug 1 (integration), prompt fix for Bug 2 (model output) — see [`fixed_app/`](fixed_app/) |
| Use trace analysis to identify the actual failure mode | [`tracer.py`](tracer.py) instruments every tool call, detects dropped fields and priority mismatches |
| Correctly separate integration-layer bugs from model-output problems | [`diagnosis/trace_analysis.md`](diagnosis/trace_analysis.md) — trace evidence pinpoints the exact layer for each bug |

### Build Steps

| Step | Requirement | Implementation |
|------|-------------|----------------|
| 1 | Introduce one integration-layer bug without changing the prompt | [`broken_app/tools.py`](broken_app/tools.py) — `is_ambiguous` hardcoded to `False` in `execute_route_ticket()` |
| 2 | Introduce one separate model-output problem without touching the integration code | [`broken_app/runner.py`](broken_app/runner.py) — vague `AGENT_SYSTEM_PROMPT` without priority rubric |
| 3 | Write down your hypothesis for each failure based on the symptom alone | [`diagnosis/hypothesis.md`](diagnosis/hypothesis.md) — pre-analysis hypotheses before examining code |
| 4 | Use logging/trace output to confirm or reject each hypothesis | [`tracer.py`](tracer.py) + [`diagnosis/trace_analysis.md`](diagnosis/trace_analysis.md) — trace-confirmed analysis |
| 5 | Fix each issue using the fix appropriate to its layer | [`fixed_app/tools.py`](fixed_app/tools.py) (code fix), [`fixed_app/runner.py`](fixed_app/runner.py) (prompt fix) |

### Setup

| Requirement | Implementation |
|-------------|----------------|
| Take any working integration you've already built (Domain 1 or 2's assignment works well) | Based on Domain 1 Agent (ticket triage) — [`shared.py`](shared.py) and [`tickets.py`](tickets.py) copied from `1_agents_and_workflows/` |

## Self-Check

| Question | Answer |
|----------|--------|
| Did your initial hypothesis for each bug turn out to be right, or did the trace reveal something different? | **Both hypotheses were confirmed.** Hypothesis 1 (field dropped between classification and routing) was confirmed by the trace showing `is_ambiguous=True` in classify output but `False` in routing — the `execute_route_ticket` function hardcoded it. Hypothesis 2 (vague prompt → downgraded priorities) was confirmed by the trace showing systematic `high/urgent → medium` downgrades across 10 tickets. See [`diagnosis/trace_analysis.md`](diagnosis/trace_analysis.md). |
| Could you explain, to someone who didn't see the bugs, which layer each one lived in and how you knew? | **Bug 1** lived in the **integration layer** (data passing between tools) — the classify tool correctly set `is_ambiguous=True`, but the route tool's code ignored the value and hardcoded `False`. The trace proved this by showing the correct value entering the function but the wrong value being used internally. **Bug 2** lived in the **model output layer** (prompt quality) — the system prompt said "determine how important it seems" instead of providing explicit URGENT/HIGH/MEDIUM/LOW criteria. The trace proved this by showing every priority defaulting to `medium` regardless of ticket severity. |

## Mock vs. Live Mode

All scripts run in mock mode by default (no API key needed). The mock classifiers simulate what the model would produce:
- **Broken mock**: Simulates the effect of the vague prompt (downgraded priorities)
- **Fixed mock**: Simulates the effect of the explicit rubric (correct priorities)

Both modes demonstrate the same diagnostic principles — the bugs and fixes work identically regardless of whether the actual API is called.

To run in **live mode**:

1. Set a valid `ANTHROPIC_API_KEY` in the `.env` file at the project root
2. Run any script normally — live mode is auto-detected when the API key is present:

```bash
uv run python .\4_eval_testing_and_debugging\run_comparison.py
```

If the API key is missing or invalid, the scripts fall back to mock mode automatically with a warning.
