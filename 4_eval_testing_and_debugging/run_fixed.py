"""
run_fixed.py — Run the FIXED agent system with tracing.

Executes the fixed pipeline against all 20 tickets to verify both bugs
are resolved. Should show zero anomalies compared to ground truth.

Usage:
    uv run python .\4_eval_testing_and_debugging\run_fixed.py
"""

from __future__ import annotations

import os
import sys

# Force UTF-8 output on Windows to avoid cp1252 encoding errors
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tickets import TICKETS
from tracer import trace_pipeline_run, format_trace_report, save_trace


def main():
    print("\n" + "#" * 70)
    print("#  RUNNING FIXED AGENT SYSTEM WITH TRACE INSTRUMENTATION")
    print("#" * 70)

    # Run the fixed pipeline with tracing
    trace = trace_pipeline_run(
        system_name="fixed",
        run_func=None,
        tickets=TICKETS,
    )

    # Print the trace report
    report = format_trace_report(trace)
    print(report)

    # Save trace to output
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    trace_path = os.path.join(output_dir, "fixed_traces.json")
    save_trace(trace, trace_path)
    print(f"  Traces saved to: {trace_path}")

    # Verify fixes
    s = trace.summary
    print(f"\n{'─'*70}")
    print("  VERIFICATION:")
    print(f"{'─'*70}")

    all_good = True
    if s["dropped_fields"] > 0:
        print(f"\n  ❌ Bug 1 NOT FIXED: {s['dropped_fields']} dropped field(s) remain.")
        all_good = False
    else:
        print(f"\n  ✅ Bug 1 FIXED: No dropped fields. is_ambiguous flows correctly")
        print(f"     from classification through routing.")

    if s["priority_mismatches"] > 0:
        print(f"\n  ❌ Bug 2 NOT FIXED: {s['priority_mismatches']} priority mismatch(es) remain.")
        all_good = False
    else:
        print(f"\n  ✅ Bug 2 FIXED: All priorities match ground truth. The explicit")
        print(f"     priority rubric in the system prompt produces consistent results.")

    if s["escalation_failures"] > 0:
        print(f"\n  ⚠  {s['escalation_failures']} escalation issue(s) remain.")
        all_good = False
    else:
        print(f"\n  ✅ Escalation WORKING: All ambiguous tickets are properly escalated.")

    if all_good:
        print(f"\n  {'='*66}")
        print(f"  ✅ ALL BUGS FIXED — SYSTEM OPERATING CORRECTLY")
        print(f"  {'='*66}")

    print(f"\n{'='*70}\n")

    return trace


if __name__ == "__main__":
    main()
