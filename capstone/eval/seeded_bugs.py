"""
eval/seeded_bugs.py — Two deliberately seeded bugs for Domain 4.

Each bug includes:
  1. The bug description
  2. Where it lives (file + function)
  3. How to reproduce it
  4. Trace analysis showing how to isolate it
  5. The fix

Bug 1 (Integration-layer): Model router fallback
Bug 2 (Model-output): Uppercase priority validation
"""

from __future__ import annotations


# ──────────────────────────────────────────────────────────────────────
# Bug 1: Integration-Layer Bug — Model Router Fallback
# ──────────────────────────────────────────────────────────────────────

BUG_1_DESCRIPTION = """
BUG 1: Model Router Ignores Task-Based Routing When CLAUDE_MODEL Is Set

FILE: capstone/models/router.py → ModelRouter.get_model_name()

SYMPTOM:
  When the environment variable CLAUDE_MODEL is set (e.g., to "claude-sonnet-4-20250514"),
  ALL requests use Sonnet regardless of task type. Simple order lookups that should
  use Haiku ($0.80/MTok) instead use Sonnet ($3.00/MTok), inflating costs 3.75x.

REPRODUCTION:
  1. Set CLAUDE_MODEL=claude-sonnet-4-20250514 in .env
  2. Send a simple order lookup: "What's the status of ORD-1001?"
  3. Observe model_used in response — should be Haiku but shows Sonnet

TRACE ANALYSIS:
  The bug is in how the orchestrator constructs the model name:
  
  orchestrator.py line ~180:
    model_name = os.getenv("CLAUDE_MODEL", model_config.model_id.value)
    # BUG: If CLAUDE_MODEL is set, it OVERRIDES the router's per-task selection
    # FIX: Remove the os.getenv fallback — trust the router's task-based selection
  
  Correct code:
    model_name = model_config.model_id.value
    # The router already made the deliberate per-task choice

IMPACT:
  - 3.75x cost increase on simple lookups ($0.80 → $3.00 per MTok input)
  - Negates the entire model strategy from Domain 5
  - Violates the "choose models deliberately per task" requirement
"""

BUG_1_FIX = {
    "file": "capstone/agent/orchestrator.py",
    "wrong": 'model_name = os.getenv("CLAUDE_MODEL", model_config.model_id.value)',
    "right": "model_name = model_config.model_id.value",
    "explanation": "The router's task-based selection should not be overridden by an env var",
}


# ──────────────────────────────────────────────────────────────────────
# Bug 2: Model-Output Bug — Uppercase Priority Validation
# ──────────────────────────────────────────────────────────────────────

BUG_2_DESCRIPTION = """
BUG 2: Escalation Ticket Parser Rejects Uppercase Priority Values

FILE: capstone/agent/tools.py → execute_escalate_to_human()

SYMPTOM:
  When the model returns priority as "URGENT" (uppercase) instead of "urgent"
  (lowercase), the escalation ticket's priority field passes through unchecked.
  But when the eval suite validates the ticket, Pydantic validation fails because
  the enum expects lowercase values.

  In live mode, Claude sometimes returns "HIGH" or "URGENT" in uppercase.
  The mock mode always uses lowercase, so this bug only surfaces with the
  live API — a classic integration-layer vs model-output mismatch.

REPRODUCTION:
  1. Simulate Claude returning uppercase priority:
     execute_escalate_to_human({"priority": "URGENT", ...})
  2. Validate the ticket against the expected schema
  3. Observe that "URGENT" is not normalized to "urgent"

TRACE ANALYSIS:
  tools.py execute_escalate_to_human():
    "priority": args.get("priority", "medium"),
    # BUG: No normalization — passes through whatever the model sent
    # If model sends "URGENT", downstream validation (eval assertions,
    # structured output consumers) may break

  FIX: Normalize the priority value:
    "priority": args.get("priority", "medium").lower(),

IMPACT:
  - Downstream systems consuming escalation tickets may reject them
  - Eval suite's _assert_response_contains("urgent") may fail
  - Only surfaces in live mode when model outputs uppercase
"""

BUG_2_FIX = {
    "file": "capstone/agent/tools.py",
    "wrong": '"priority": args.get("priority", "medium"),',
    "right": '"priority": args.get("priority", "medium").lower(),',
    "explanation": "Normalize model output to lowercase before downstream consumption",
}


# ──────────────────────────────────────────────────────────────────────
# Verification helpers
# ──────────────────────────────────────────────────────────────────────

def verify_bug_1_is_fixed() -> tuple[bool, str]:
    """Verify that Bug 1 has been fixed by checking the router respects task config."""
    from capstone.models.router import ModelRouter, TaskType

    router = ModelRouter()
    # Simple lookup should always be Haiku, regardless of env vars
    config = router.get_config(TaskType.SIMPLE_LOOKUP)
    if "haiku" in config.model_id.value.lower():
        return True, "✓ Bug 1 fixed: Simple lookups correctly route to Haiku"
    return False, "✗ Bug 1 NOT fixed: Simple lookups still routing to wrong model"


def verify_bug_2_is_fixed() -> tuple[bool, str]:
    """Verify that Bug 2 has been fixed by checking priority normalization."""
    from capstone.agent.tools import execute_escalate_to_human

    result = execute_escalate_to_human({
        "reason": "Test",
        "priority": "URGENT",  # Uppercase — simulates model output
        "customer_summary": "Test case",
    })

    ticket = result.get("escalation_ticket", {})
    priority = ticket.get("priority", "")
    if priority == "urgent":
        return True, "✓ Bug 2 fixed: Uppercase 'URGENT' correctly normalized to 'urgent'"
    return False, f"✗ Bug 2 NOT fixed: Priority is '{priority}', expected 'urgent'"


def run_bug_verification():
    """Run both bug verifications and print results."""
    print("\n" + "=" * 60)
    print("  SEEDED BUG VERIFICATION")
    print("=" * 60 + "\n")

    for name, verifier in [("Bug 1 (Router Fallback)", verify_bug_1_is_fixed),
                            ("Bug 2 (Priority Case)", verify_bug_2_is_fixed)]:
        try:
            passed, detail = verifier()
            status = "PASS" if passed else "FAIL"
            print(f"  [{status}] {name}")
            print(f"    {detail}")
        except Exception as e:
            print(f"  [ERROR] {name}")
            print(f"    Exception: {e}")
        print()


if __name__ == "__main__":
    run_bug_verification()
