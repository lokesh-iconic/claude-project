"""
run_broken.py — Run the BROKEN agent system with tracing.

Executes the broken pipeline against all 20 tickets, captures traces,
and outputs a diagnostic report highlighting the anomalies caused by
Bug 1 (dropped is_ambiguous field) and Bug 2 (inconsistent priorities).

Usage:
    uv run python .\4_eval_testing_and_debugging\run_broken.py
"""

from __future__ import annotations

import os
import sys

# Force UTF-8 output on Windows to avoid cp1252 encoding errors
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Ensure the 4_eval_testing_and_debugging directory is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tickets import TICKETS
from tracer import trace_pipeline_run, format_trace_report, save_trace


def main():
    print("\n" + "#" * 70)
    print("#  RUNNING BROKEN AGENT SYSTEM WITH TRACE INSTRUMENTATION")
    print("#" * 70)

    # Run the broken pipeline with tracing
    trace = trace_pipeline_run(
        system_name="broken",
        run_func=None,  # tracer handles import internally
        tickets=TICKETS,
    )

    # Print the trace report
    report = format_trace_report(trace)
    print(report)

    # Save trace to output
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    trace_path = os.path.join(output_dir, "broken_traces.json")
    save_trace(trace, trace_path)
    print(f"  Traces saved to: {trace_path}")

    # Print quick diagnosis pointers
    s = trace.summary
    print(f"\n{'─'*70}")
    print("  DIAGNOSIS POINTERS:")
    print(f"{'─'*70}")

    if s["dropped_fields"] > 0:
        print(f"\n  🔴 BUG 1 SIGNAL: {s['dropped_fields']} ticket(s) had fields dropped")
        print(f"     between classification and routing. The is_ambiguous flag was")
        print(f"     present in classifier output but missing in routing input.")
        print(f"     → This is an INTEGRATION-LAYER bug (data passing between tools).")

    if s["priority_mismatches"] > 0:
        print(f"\n  🔴 BUG 2 SIGNAL: {s['priority_mismatches']} ticket(s) had wrong priority")
        print(f"     assignments compared to ground truth. Priorities are being")
        print(f"     systematically downgraded (high/urgent → medium).")
        print(f"     → This is a MODEL-OUTPUT problem (vague prompt → inconsistent output).")

    if s["escalation_failures"] > 0:
        print(f"\n  🟡 SECONDARY: {s['escalation_failures']} ambiguous ticket(s) were not")
        print(f"     escalated during routing. This is a CONSEQUENCE of Bug 1.")

    print(f"\n{'='*70}\n")

    return trace


if __name__ == "__main__":
    main()
