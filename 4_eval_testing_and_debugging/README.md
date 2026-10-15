# Eval, Testing & Debugging — Diagnose and Fix a Deliberately Broken Claude Application

Take a working Claude integration, deliberately break it in two different layers, diagnose both bugs using trace analysis, then fix each one using the layer-appropriate strategy.

## Problem Statement

This project demonstrates the ability to correctly **isolate integration-layer bugs from model-output problems** in a Claude application. Two bugs were introduced into the working Domain 1 Agent (support ticket triage system):

1. **Bug 1 (Integration Layer)**: A tool that ignores a field it is given (`is_ambiguous` in the router)
2. **Bug 2 (Model Output)**: A vague prompt causing inconsistent classification

Both bugs produce similar symptoms ("routing doesn't work right") but require completely different diagnostic approaches and completely different fixes.

## Project Structure

```
4_eval_testing_and_debugging/
├── README.md                           ← You are here
├── __init__.py
├── shared.py                           ← Shared types (copy of the module 1 file)
├── tickets.py                          ← 20 sample tickets (copy of the module 1 file)
├── mock_model.py                       ← Simulated model: its priority behaviour depends on the system prompt
├── tracer.py                           ← Trace instrumentation + anomaly detection
│
├── broken_app/                         ← Deliberately broken version
│   ├── __init__.py
│   ├── tools.py                        ← ⬅ BUG 1: is_ambiguous hardcoded to False
│   ├── runner.py                       ← ⬅ BUG 2: vague prompt, no priority rubric
│   ├── hooks.py                        ← Same code as fixed_app
│   └── subagent.py                     ← Same code as fixed_app
│
├── fixed_app/                          ← Both bugs fixed
│   ├── __init__.py
│   ├── tools.py                        ← is_ambiguous read from args (only code difference from broken_app)
│   ├── runner.py                       ← explicit priority rubric in the prompt (only difference from broken_app)
│   ├── hooks.py                        ← Same code as broken_app
│   └── subagent.py                     ← Same code as broken_app
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
| **What** | Priority guidance removed; replaced with "determine how important each ticket seems and use your best judgment" |
| **Effect** | Priorities inconsistently assigned (urgent/high → medium) |
| **Symptom** | Double-charge tickets get `medium` priority instead of `high` |
| **Why it's non-obvious** | Code is correct. Tool schemas accept all values. The prompt just doesn't constrain enough. |
| **How mock mode shows it** | `mock_model.py` reads the system prompt. Without the `Priority Rubric` section the simulated model rates everything except feature requests as `medium`; with it, priorities follow the rubric. Swapping the prompt is the only change between the two apps. |
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
- Compares outputs of step N with inputs of step N+1 (detects dropped fields) and flags a router that receives `is_ambiguous=True` yet does not escalate (ignored field)
- Compares classifier output with ground truth (detects wrong priorities)
- Flags anomalies automatically

### Step 4: Analyze Traces

See [`diagnosis/trace_analysis.md`](diagnosis/trace_analysis.md):
- **Bug 1**: Trace shows `is_ambiguous=True` in the route step's inputs but `escalate=False` in its output → the function ignores its own input, confirmed as an integration bug
- **Bug 2**: Trace shows systematic priority downgrades against ground truth, with no dropped or altered data between steps → confirmed as a prompt problem

### Step 5: Fix (Layer-Appropriate)

- **Bug 1**: Code fix in `tools.py` (integration layer → code change)
- **Bug 2**: Prompt fix in `runner.py` (model output layer → prompt change)

## Assignment Requirements Mapping

### What This Proves

| Requirement | Where It's Demonstrated |
|-------------|------------------------|
| Identify and classify error types in a Claude application | Bug 1 classified as integration-layer, Bug 2 classified as model-output — see [The Two Bugs](#the-two-bugs) |
| Select an appropriate recovery strategy per error type | Code fix for Bug 1 (integration), prompt fix for Bug 2 (model output) — see [`fixed_app/`](fixed_app/) |
| Use trace analysis to identify the actual failure mode | [`tracer.py`](tracer.py) instruments every tool call, detects dropped/ignored fields and priority mismatches |
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
| Did your initial hypothesis for each bug turn out to be right, or did the trace reveal something different? | **Both were right about the layer; hypothesis 1 was wrong about the mechanism.** Hypothesis 1 guessed the field was dropped in the data passing (option a) or ignored by the router (option b). The trace shows the runner passes `is_ambiguous=True` into `route_ticket`, so it was option b: `execute_route_ticket` ignores it. Hypothesis 2 (vague prompt → downgraded priorities) was confirmed: 10 tickets differ from ground truth with the vague prompt and 0 with the rubric. See [`diagnosis/trace_analysis.md`](diagnosis/trace_analysis.md). |
| Could you explain, to someone who didn't see the bugs, which layer each one lived in and how you knew? | **Bug 1** lived in the **integration layer** — the classifier correctly set `is_ambiguous=True` and the runner passed it to the route tool, but the route tool's code ignored it and used `False`. The trace shows the correct input and an `escalate=False` output, and `tools.py` shows why. **Bug 2** lived in the **model output layer** (prompt quality) — the system prompt asked the model to judge importance instead of giving URGENT/HIGH/MEDIUM/LOW criteria. The trace shows billing, technical and account tickets all rated `medium` while the code passed the values through unchanged. |

## Mock vs. Live Mode

This module runs in **mock mode only**; there is no live-API path.

- `mock_model.py` simulates the model. It reads the agent's system prompt: if the prompt contains the `Priority Rubric` section it assigns priorities from the rubric, otherwise it rates anything that is not clearly a feature request as `medium`. The classification logic and tool code are otherwise identical in both apps.
- Because the behaviour is driven by the prompt text, the prompt edit is the only difference that changes the outcome, which is what the exercise needs to show.
- The simulation encodes the *expected* effect of a vague prompt. Whether a real Claude model shows the same drift has to be checked against the live API, which this module does not call.
