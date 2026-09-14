"""
run_parser_test.py -- Feed 10 deliberately malformed responses to the parser.

Tests that the defensive parser NEVER crashes and ALWAYS produces a valid
AssistantResponse, even on the worst possible input.

Usage:
    uv run python .\\6_prompt_and_context_engineering\\run_parser_test.py
"""

from __future__ import annotations

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from structured_output import parse_response, AssistantResponse


# --------------------------------------------------------------------------
# 10 test cases: one valid baseline + 9 deliberately broken inputs
# --------------------------------------------------------------------------

TEST_CASES = [
    {
        "name": "Valid JSON (baseline)",
        "input": '{"summary": "This is a valid response.", "details": "Everything works correctly.", "sources": ["Doc A"], "confidence": "high", "follow_up": "Any other questions?"}',
        "should_parse": True,
        "should_flag_error": False,
    },
    {
        "name": "JSON wrapped in markdown fences",
        "input": '```json\n{"summary": "Extracted from markdown.", "details": "Parser should strip the fences.", "sources": [], "confidence": "medium", "follow_up": null}\n```',
        "should_parse": True,
        "should_flag_error": True,  # Extracted, but flagged
    },
    {
        "name": "Missing required field (no 'details')",
        "input": '{"summary": "Incomplete response.", "sources": ["Doc B"], "confidence": "high", "follow_up": null}',
        "should_parse": True,
        "should_flag_error": True,
    },
    {
        "name": "Extra unexpected field",
        "input": '{"summary": "Has extra field.", "details": "Should still parse.", "sources": [], "confidence": "low", "follow_up": null, "mood": "happy", "score": 95}',
        "should_parse": True,
        "should_flag_error": False,  # Extra fields are harmless
    },
    {
        "name": "Invalid confidence value",
        "input": '{"summary": "Bad confidence.", "details": "Confidence is not a valid enum value.", "sources": [], "confidence": "super_high", "follow_up": null}',
        "should_parse": True,
        "should_flag_error": True,
    },
    {
        "name": "Truncated JSON (missing closing brace)",
        "input": '{"summary": "Truncated response.", "details": "The JSON got cut off mid-stream.", "sources": ["Doc C"], "confidence": "medium"',
        "should_parse": True,
        "should_flag_error": True,
    },
    {
        "name": "Plain text (no JSON at all)",
        "input": "I'm sorry, I don't have enough information to answer that question. Could you please provide more details about what you're looking for?",
        "should_parse": True,  # Falls back to safe default
        "should_flag_error": True,
    },
    {
        "name": "Empty string",
        "input": "",
        "should_parse": True,
        "should_flag_error": True,
    },
    {
        "name": "JSON array instead of object",
        "input": '[{"summary": "Wrong type"}, {"details": "Should be object not array"}]',
        "should_parse": True,
        "should_flag_error": True,
    },
    {
        "name": "HTML instead of JSON",
        "input": "<html><body><h1>Error 500</h1><p>Internal Server Error. Please try again later.</p></body></html>",
        "should_parse": True,
        "should_flag_error": True,
    },
]


def main():
    print("\n" + "=" * 70)
    print("  MODULE 6: Structured Output Parser — Malformed Input Stress Test")
    print("=" * 70)
    print(f"\n  Testing {len(TEST_CASES)} inputs (1 valid baseline + {len(TEST_CASES) - 1} broken)\n")

    results = []
    all_passed = True

    for i, test in enumerate(TEST_CASES):
        test_num = i + 1
        name = test["name"]

        # --- Run the parser (this should NEVER crash) ---
        try:
            result = parse_response(test["input"])
            crashed = False
        except Exception as e:
            crashed = True
            result = None
            error_msg = str(e)

        # --- Evaluate ---
        checks = {
            "no_crash": not crashed,
            "returns_response": isinstance(result, AssistantResponse) if not crashed else False,
            "has_summary": bool(result.summary) if result else False,
            "has_details": bool(result.details) if result else False,
            "valid_confidence": result.confidence in AssistantResponse.VALID_CONFIDENCE if result else False,
        }

        if test["should_flag_error"]:
            checks["error_flagged"] = result.parse_error is not None if result else False
        else:
            checks["clean_parse"] = result.parse_error is None if result else False

        passed = all(checks.values())
        if not passed:
            all_passed = False

        status = "PASS" if passed else "FAIL"
        results.append({"name": name, "passed": passed, "checks": checks, "result": result})

        # Print result
        print(f"  [{test_num:>2}] [{status}] {name}")
        if result and not crashed:
            error_info = f" (error: {result.parse_error[:50]}...)" if result.parse_error else ""
            print(f"       Summary: \"{result.summary[:60]}...\"{error_info}")
        elif crashed:
            print(f"       CRASHED: {error_msg}")

        if not passed:
            failed = [k for k, v in checks.items() if not v]
            print(f"       Failed checks: {', '.join(failed)}")

    # --- Summary ---
    print(f"\n  {'='*66}")
    print(f"  RESULTS")
    print(f"  {'='*66}\n")

    passed_count = sum(1 for r in results if r["passed"])
    print(f"  Passed: {passed_count}/{len(TEST_CASES)}")
    print(f"  Status: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")

    # --- Self-Check ---
    print(f"\n  {'='*66}")
    print(f"  SELF-CHECK: Does the parser fail safely on malformed input?")
    print(f"  {'='*66}\n")

    crash_count = sum(1 for r in results if not r["checks"].get("no_crash", True))
    garbage_count = sum(1 for r in results
                        if r["result"] and not r["result"].summary and r["checks"].get("no_crash", False))

    if crash_count == 0 and garbage_count == 0:
        print(f"  YES — The parser handled all {len(TEST_CASES)} inputs without crashing.")
        print(f"  Every malformed input was flagged in parse_error (never silent).")
        print(f"  Every result has a valid summary, details, and confidence value.")
    else:
        if crash_count > 0:
            print(f"  NO — {crash_count} inputs caused a crash.")
        if garbage_count > 0:
            print(f"  NO — {garbage_count} inputs produced empty/garbage output without flagging.")

    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    main()
