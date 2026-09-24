"""
eval/run_evals.py — Eval runner for the capstone support assistant.

Executes all eval cases and produces a pass/fail report.
Supports filtering by category (--adversarial-only, --core-only, etc.)

Usage:
    uv run python capstone/eval/run_evals.py
    uv run python capstone/eval/run_evals.py --adversarial-only
    uv run python capstone/eval/run_evals.py --category core
"""

from __future__ import annotations

import sys
import os
import time

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from capstone.eval.eval_suite import get_all_cases, get_adversarial_cases, get_cases_by_category, EvalCase
from capstone.eval.seeded_bugs import run_bug_verification
from capstone.agent.orchestrator import SupportSession, process_message


def run_single_eval(case: EvalCase, session: SupportSession) -> dict:
    """Run a single eval case and check all assertions."""
    result = process_message(session, case.user_message)

    assertion_results = []
    all_passed = True

    for assertion_fn in case.assertions:
        try:
            passed, detail = assertion_fn(result)
            assertion_results.append({"passed": passed, "detail": detail})
            if not passed:
                all_passed = False
        except Exception as e:
            assertion_results.append({"passed": False, "detail": f"Exception: {e}"})
            all_passed = False

    return {
        "case_id": case.case_id,
        "category": case.category,
        "description": case.description,
        "passed": all_passed,
        "assertions": assertion_results,
        "response_preview": result.get("response", "")[:100],
        "tool_used": result.get("tool_used"),
        "model_used": result.get("model_used"),
        "blocked": result.get("blocked"),
    }


def run_regression_eval(case: EvalCase) -> dict:
    """Run the regression eval with a long conversation history."""
    session = SupportSession(session_id="eval-regression")

    # Simulate 14 prior turns to test context management
    prior_messages = [
        "What's the status of order ORD-1001?",
        "What about order ORD-1002?",
        "What's your return policy?",
        "What shipping methods do you offer?",
        "Can you look up my account? sarah.chen@email.com",
        "What's the warranty on electronics?",
        "How do I track my order?",
        "What payment methods do you accept?",
        "I want to know about bulk ordering",
        "Tell me about account security",
        "What are your subscription plans?",
        "How long do refunds take?",
        "Can I ship to a PO box?",
        "What about data privacy?",
    ]

    for msg in prior_messages:
        process_message(session, msg)

    # Now run the actual eval case on turn 15+
    return run_single_eval(case, session)


def run_all_evals(cases: list[EvalCase] | None = None):
    """Run all eval cases and print results."""
    cases = cases or get_all_cases()

    print("\n" + "=" * 70)
    print("  CAPSTONE EVAL SUITE")
    print("=" * 70 + "\n")

    results = []
    start_time = time.time()

    for case in cases:
        print(f"  Running {case.case_id}: {case.description[:50]}...")

        if case.category == "regression":
            result = run_regression_eval(case)
        else:
            session = SupportSession(session_id=f"eval-{case.case_id}")
            result = run_single_eval(case, session)

        results.append(result)

        status = "✓ PASS" if result["passed"] else "✗ FAIL"
        print(f"    {status}")

        if not result["passed"]:
            for assertion in result["assertions"]:
                if not assertion["passed"]:
                    print(f"      |- {assertion['detail']}")

    elapsed = time.time() - start_time

    # Summary
    passed = sum(1 for r in results if r["passed"])
    total = len(results)

    print(f"\n{'-' * 70}")
    print(f"\n  {'#':<10} {'Category':<15} {'Description':<35} {'Result':<8}")
    print(f"  {'-'*10} {'-'*15} {'-'*35} {'-'*8}")

    for r in results:
        status = "✓ PASS" if r["passed"] else "✗ FAIL"
        print(f"  {r['case_id']:<10} {r['category']:<15} {r['description'][:35]:<35} {status:<8}")

    print(f"\n  {'-' * 70}")
    print(f"  Result: {passed}/{total} cases passed in {elapsed:.1f}s")

    if passed == total:
        print(f"  ✓ ALL EVAL CASES PASSED")
    else:
        print(f"  ✗ {total - passed} CASE(S) FAILED")

    print(f"  {'=' * 70}\n")

    return passed == total


def main():
    """Entry point with argument parsing."""
    args = sys.argv[1:]

    if "--adversarial-only" in args:
        cases = get_adversarial_cases()
        print("  [Running adversarial cases only]")
    elif "--category" in args:
        idx = args.index("--category")
        if idx + 1 < len(args):
            category = args[idx + 1]
            cases = get_cases_by_category(category)
            print(f"  [Running {category} cases only]")
        else:
            print("Error: --category requires a value")
            sys.exit(1)
    else:
        cases = None  # All cases

    all_passed = run_all_evals(cases)

    # Also run seeded bug verification
    print()
    run_bug_verification()

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
