"""
eval/seeded_bugs.py — Two deliberately seeded bugs for Domain 4.

Each bug includes:
  1. The bug description
  2. Where it lives (file + function)
  3. How to reproduce it
  4. Trace analysis showing how to isolate it
  5. The fix

Bug 1 (Integration-layer): an env var overrides the router's per-task model choice
Bug 2 (Model-output): uppercase priority values from the model are not normalized

State of the repo:
  - Bug 1 is fixed. Reintroducing it makes EVAL-001 fail and makes verify_bug_1_is_fixed() fail.
  - Bug 2 is deliberately left in place. verify_bug_2_is_fixed() detects it, and the runner
    reports it as DETECTED (expected) without failing the run.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# ──────────────────────────────────────────────────────────────────────
# Bug 1: Integration-Layer Bug — Model Router Fallback
# ──────────────────────────────────────────────────────────────────────

BUG_1_DESCRIPTION = """
BUG 1: Model Router Ignores Task-Based Routing When CLAUDE_MODEL Is Set

FILE: capstone/agent/orchestrator.py → process_message()

SYMPTOM:
  When the environment variable CLAUDE_MODEL is set (e.g., to "claude-sonnet-4-6"),
  ALL requests use Sonnet regardless of task type. Simple order lookups that should
  use Haiku ($1.00/MTok) instead use Sonnet ($3.00/MTok), inflating costs 3x.

REPRODUCTION:
  1. Set CLAUDE_MODEL=claude-sonnet-4-6 in .env
  2. Send a simple order lookup: "What's the status of ORD-1001?"
  3. Observe model_used in response — should be Haiku but shows Sonnet

TRACE ANALYSIS:
  The bug is in how the orchestrator constructs the model name:
  
  orchestrator.py process_message():
    model_name = os.getenv("CLAUDE_MODEL", model_config.model_id.value)
    # BUG: If CLAUDE_MODEL is set, it OVERRIDES the router's per-task selection
    # FIX: Remove the os.getenv fallback — trust the router's task-based selection
  
  Correct code:
    model_name = model_config.model_id.value
    # The router already made the deliberate per-task choice

IMPACT:
  - 3x cost increase on simple lookups ($1.00 → $3.00 per MTok input)
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
  (lowercase), the escalation ticket's priority field passes through unchecked, and
  the "urgent" response-time branch ("2-4 hours") is not taken.

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
  - Urgent tickets get the standard 24-hour estimate instead of 2-4 hours
  - Downstream systems that compare against lowercase values misread the ticket
  - Only surfaces in live mode when the model outputs uppercase
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
    """Send a simple lookup through the real orchestrator with CLAUDE_MODEL set.

    The seeded bug lives in the orchestrator, so the check has to go through it:
    with the override in place the lookup is served by Sonnet instead of Haiku.
    """
    from capstone.agent.orchestrator import SupportSession, process_message

    previous = os.environ.get("CLAUDE_MODEL")
    os.environ["CLAUDE_MODEL"] = "claude-sonnet-4-6"
    try:
        result = process_message(SupportSession(session_id="bug-1-check"), "What's the status of order ORD-1001?")
    finally:
        if previous is None:
            os.environ.pop("CLAUDE_MODEL", None)
        else:
            os.environ["CLAUDE_MODEL"] = previous

    model = result.get("model_used", "")
    if "haiku" in model.lower():
        return True, f"Bug 1 fixed: simple lookup routed to {model} even with CLAUDE_MODEL set"
    return False, f"Bug 1 present: simple lookup used {model}, expected Haiku"


def verify_bug_2_is_fixed() -> tuple[bool, str]:
    """Check that an uppercase priority from the model is normalized."""
    from capstone.agent.tools import execute_escalate_to_human

    result = execute_escalate_to_human({
        "reason": "Test",
        "priority": "URGENT",  # Uppercase, simulates model output
        "customer_summary": "Test case",
    })

    ticket = result.get("escalation_ticket", {})
    priority = ticket.get("priority", "")
    if priority == "urgent":
        return True, "Bug 2 fixed: uppercase 'URGENT' normalized to 'urgent'"
    return False, f"Bug 2 present: priority is '{priority}', expected 'urgent'"


# Bugs that are intentionally left in the code base. A failing check for these is expected.
EXPECTED_UNFIXED = {"Bug 2 (Priority Case)"}


def run_bug_verification() -> bool:
    """Run both verifications and print results.

    Returns True when the outcome is as intended: Bug 1 fixed, Bug 2 detected.
    """
    print()
    print("=" * 60)
    print("  SEEDED BUG VERIFICATION")
    print("=" * 60)
    print()

    as_intended = True
    for name, verifier in [("Bug 1 (Router Fallback)", verify_bug_1_is_fixed),
                           ("Bug 2 (Priority Case)", verify_bug_2_is_fixed)]:
        expected_unfixed = name in EXPECTED_UNFIXED
        try:
            passed, detail = verifier()
        except Exception as e:
            print(f"  [ERROR] {name}")
            print(f"    Exception: {e}")
            print()
            as_intended = False
            continue

        if passed:
            status = "FIXED"
        elif expected_unfixed:
            status = "DETECTED (expected)"
        else:
            status = "FAIL"
            as_intended = False
        print(f"  [{status}] {name}")
        print(f"    {detail}")
        print()

    return as_intended


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(0 if run_bug_verification() else 1)
