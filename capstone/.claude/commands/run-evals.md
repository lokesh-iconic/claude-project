---
description: Run the capstone eval suite and seeded-bug verification
argument-hint: "[adversarial | core | edge | regression]"
---

Run the capstone eval suite and report the results.

1. Pick the command from `$ARGUMENTS`:
   - empty: `uv run python capstone/eval/run_evals.py`
   - `adversarial`: `uv run python capstone/eval/run_evals.py --adversarial-only`
   - `core`, `edge` or `regression`: `uv run python capstone/eval/run_evals.py --category $ARGUMENTS`
2. Run it from the repository root and show the result table.
3. For any failing case, quote the failed assertion and name the file most likely responsible.
4. Report the seeded-bug verification: Bug 1 must be fixed and Bug 2 must be detected (it is left in the code on purpose).
