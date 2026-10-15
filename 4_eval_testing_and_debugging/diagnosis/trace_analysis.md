# Trace Analysis — Confirming/Rejecting Hypotheses

Traces captured by `tracer.py` after running `run_broken.py`.

---

## Bug 1: Dropped `is_ambiguous` Field

### Trace Evidence

For ticket TKT-019 (Spanish, multi-intent), the broken system's trace shows:

```
Step 1: classify_ticket
  → category=general, priority=medium, is_ambiguous=True, confidence=0.45

Step 2: escalate_to_specialist
  → category=account, priority=medium, is_ambiguous=True, confidence=0.75
    (Specialist fires because the first classification was ambiguous)

Step 3: route_ticket
  inputs: category=account, priority=medium, is_ambiguous=True   ← PASSED IN
  → team=account_mgmt, escalate=False                            ← WRONG: ambiguous ticket not escalated
```

TKT-016 and TKT-018 also reach the router with `is_ambiguous=True` but are escalated anyway, because the
specialist rates them `urgent` and the router escalates on high or urgent priority. TKT-017 and TKT-020
are not escalated either, but there the first classification already said `is_ambiguous=False` and
`priority=medium`, so those two come from Bug 2, not Bug 1.

The tracer flags the TKT-019 pattern as `IGNORED FIELD`: `is_ambiguous=True` in the route inputs and
`escalate=False` in its output.

**The `is_ambiguous` field IS passed in the route_args dict** (the runner correctly
builds `route_args` with `is_ambiguous=True`). But inside `execute_route_ticket()`,
the function **ignores the field** by hardcoding `is_ambiguous = False`.

### Hypothesis Verdict: PARTIALLY CONFIRMED

My hypothesis was correct that the `is_ambiguous` signal is lost between
classification and routing. However, the mechanism is slightly different than
expected:

- ❌ Hypothesis (a) — field dropped in data passing: REJECTED. The runner
  correctly includes `is_ambiguous` in `route_args`.
- ✅ Hypothesis (b) — routing function ignores the field: CONFIRMED. The
  function reads `is_ambiguous = False` instead of `args.get("is_ambiguous", False)`.

### Layer Classification: INTEGRATION LAYER

This is an integration-layer bug. The routing function's code has a hardcoded
value that ignores its own input. The model/prompt is not involved — this is
pure Python code.

### Fix Applied

```python
# broken_app/tools.py line ~188:
is_ambiguous = False                          # ← BUG: hardcoded

# fixed_app/tools.py line ~188:
is_ambiguous = args.get("is_ambiguous", False)  # ← FIX: read from args
```

**Fix type**: Code fix (correct layer for an integration bug).

---

## Bug 2: Inconsistent Priority Assignment

### Trace Evidence

For ticket TKT-001 ("Double charged for my subscription"):

```
Ground truth:  priority = high
Broken output: priority = medium    ← WRONG
Fixed output:  priority = high      ← CORRECT
```

For ticket TKT-005 ("Can't log in — password reset email never arrives"):

```
Ground truth:  priority = urgent
Broken output: priority = medium    ← WRONG
Fixed output:  priority = urgent    ← CORRECT (hard deadline stated in the ticket)
```

The pattern is systematic: the broken system assigns "medium" to almost all
tickets except feature requests (which correctly get "low"). This is because
the broken system prompt says:

```
"Determine how important each ticket seems and categorize it appropriately."
```

This is too vague — the model has no calibration for what "important" means.

### Hypothesis Verdict: CONFIRMED

My hypothesis was exactly right. Without explicit priority criteria, the model
defaults to "medium" for anything that isn't obviously a feature request.

### Layer Classification: MODEL OUTPUT

This is a model-output problem. The integration code correctly passes whatever
priority the classifier returns. The classifier returns the wrong priority
because the prompt doesn't constrain it.

### Fix Applied

Added explicit priority rubric to `AGENT_SYSTEM_PROMPT`:

```
## Priority Rubric (ALWAYS follow this):
- URGENT: System outage, data loss, security breach, or customer has a hard deadline
- HIGH:   Money involved (charges, refunds), blocking issue, compliance request (GDPR)
- MEDIUM: Inconvenience with a workaround, informational request, plan changes
- LOW:    Feature suggestion, product feedback, non-blocking question
```

**Fix type**: Prompt fix (correct layer for a model-output problem).

---

## Summary

| Bug | Hypothesis | Verdict | Layer | Fix Type |
|-----|-----------|---------|-------|----------|
| Bug 1: Dropped `is_ambiguous` | Field lost between classify → route | ✅ Confirmed (hardcoded False) | Integration | Code fix |
| Bug 2: Wrong priorities | Vague prompt → inconsistent output | ✅ Confirmed | Model Output | Prompt fix |

Both hypotheses were confirmed by trace analysis. The key insight is that
trace analysis correctly identified:

1. **WHERE** the data was lost (Bug 1: inside `execute_route_ticket`, not in the runner)
2. **WHICH LAYER** caused the problem (Bug 2: prompt, not code)

Without traces, both bugs would appear to be "routing doesn't work right" —
the same symptom with two completely different root causes requiring two
completely different types of fixes.
