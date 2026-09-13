# Pre-Analysis Hypotheses

Written BEFORE examining any code or traces. Based only on observed symptoms.

---

## Bug 1 — Observed Symptom

**Symptom**: Ambiguous tickets (TKT-016 through TKT-020) are correctly classified as
ambiguous and the specialist subagent fires, but the routing step shows
`escalate: false` for ALL of them. Non-ambiguous high-priority tickets
still show `escalate: true`.

**Hypothesis**: The routing function is not receiving the `is_ambiguous` flag from
the classification step. Either:
- (a) The field is being dropped when classification results are passed to the
  router (integration glue bug — a field is present in the output of one step
  but absent in the input of the next), OR
- (b) The routing function is ignoring the `is_ambiguous` field even when it
  receives it (logic bug inside the routing function).

**Predicted Layer**: Integration layer (data flow between tools), not model output.
The classifier is working correctly. The routing logic itself works for
non-ambiguous tickets. The bug is in the gap between them.

**Predicted Fix Type**: Code fix — either restore the field in the data passing
logic, or fix the routing function to actually read `is_ambiguous` from its inputs.

---

## Bug 2 — Observed Symptom

**Symptom**: Priority levels are inconsistently assigned. Tickets that should
clearly be "high" (e.g., double billing charges, app crashes) are being
classified as "medium". Feature requests are correctly "low". The pattern
is that tickets requiring JUDGMENT about urgency are downgraded, while
clear-cut low-priority tickets are fine.

**Hypothesis**: The system prompt does not provide clear criteria for distinguishing
priority levels. Without a rubric, the model (or mock classifier simulating
the model's behavior) defaults to "medium" for anything that isn't obviously
low or obviously catastrophic. This is a prompt engineering problem — the model
needs explicit guidance like:
- URGENT = system down, data loss
- HIGH = money involved, blocking issue
- MEDIUM = inconvenience, workaround exists
- LOW = suggestion, feedback

**Predicted Layer**: Model output layer (prompt quality), not integration code.
The code correctly passes whatever priority the model returns. The issue is
that the model returns the WRONG priority because the prompt doesn't constrain it.

**Predicted Fix Type**: Prompt fix — add an explicit priority rubric to the system
prompt. Do NOT change the code (e.g., don't add a hardcoded priority override).
