"""
run_comparison.py — Side-by-side comparison of broken vs. fixed agent systems.

Runs both systems, diffs the results, and generates a comparison report
showing exactly what each bug caused and how each fix resolved it.

Usage:
    uv run python .\4_eval_testing_and_debugging\run_comparison.py
"""

from __future__ import annotations

import json
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
    print("\n" + "=" * 70)
    print("  BROKEN vs FIXED -- SIDE-BY-SIDE COMPARISON")
    print("=" * 70)

    # Run both systems
    print("\n  [1/2] Running broken system...")
    broken_trace = trace_pipeline_run("broken", None, TICKETS)

    print("  [2/2] Running fixed system...")
    fixed_trace = trace_pipeline_run("fixed", None, TICKETS)

    # Save traces
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    save_trace(broken_trace, os.path.join(output_dir, "broken_traces.json"))
    save_trace(fixed_trace, os.path.join(output_dir, "fixed_traces.json"))

    # Build comparison
    lines = []
    lines.append(f"\n{'='*70}")
    lines.append(f"  COMPARISON: BROKEN vs FIXED")
    lines.append(f"{'='*70}\n")

    # Summary table
    bs = broken_trace.summary
    fs = fixed_trace.summary

    lines.append(f"  {'Metric':<30} {'Broken':>12} {'Fixed':>12} {'Delta':>12}")
    lines.append(f"  {'─'*66}")
    lines.append(f"  {'Tickets with anomalies':<30} {bs['tickets_with_anomalies']:>12} {fs['tickets_with_anomalies']:>12} {fs['tickets_with_anomalies'] - bs['tickets_with_anomalies']:>+12}")
    lines.append(f"  {'Priority mismatches':<30} {bs['priority_mismatches']:>12} {fs['priority_mismatches']:>12} {fs['priority_mismatches'] - bs['priority_mismatches']:>+12}")
    lines.append(f"  {'Escalation failures':<30} {bs['escalation_failures']:>12} {fs['escalation_failures']:>12} {fs['escalation_failures'] - bs['escalation_failures']:>+12}")
    lines.append(f"  {'Dropped fields':<30} {bs['dropped_fields']:>12} {fs['dropped_fields']:>12} {fs['dropped_fields'] - bs['dropped_fields']:>+12}")
    lines.append("")

    # Per-ticket comparison (only tickets that differ)
    lines.append(f"  {'─'*66}")
    lines.append(f"  PER-TICKET DIFFS:")
    lines.append(f"  {'─'*66}\n")

    diff_count = 0
    for bt, ft in zip(broken_trace.ticket_traces, fixed_trace.ticket_traces):
        b_cls = bt.final_result.get("classification", {})
        f_cls = ft.final_result.get("classification", {})
        b_rt = bt.final_result.get("routing", {})
        f_rt = ft.final_result.get("routing", {})

        diffs = []

        # Check priority
        if b_cls.get("priority") != f_cls.get("priority"):
            diffs.append(
                f"    Priority:   {b_cls.get('priority', '?'):>8}  →  {f_cls.get('priority', '?'):<8}"
                f"  [Bug 2: prompt fix restored correct priority]"
            )

        # Check escalation
        if b_rt.get("escalate") != f_rt.get("escalate"):
            diffs.append(
                f"    Escalate:   {str(b_rt.get('escalate', '?')):>8}  →  {str(f_rt.get('escalate', '?')):<8}"
                f"  [Bug 1: is_ambiguous field restored → escalation works]"
            )

        if diffs:
            diff_count += 1
            gt = bt.ground_truth
            lines.append(f"  [{bt.ticket_id}] {bt.ticket_subject}")
            lines.append(f"    Ground truth: priority={gt.get('priority')}, ambiguous={gt.get('is_ambiguous')}")
            for d in diffs:
                lines.append(d)
            lines.append("")

    if diff_count == 0:
        lines.append("  No differences found (both systems produce identical results).\n")
    else:
        lines.append(f"  Total tickets with differences: {diff_count}\n")

    # Bug fix summary
    lines.append(f"  {'═'*66}")
    lines.append(f"  FIX SUMMARY:")
    lines.append(f"  {'═'*66}\n")

    lines.append(f"  Bug 1 (Integration Layer):")
    lines.append(f"    Problem:  is_ambiguous hardcoded to False in execute_route_ticket()")
    lines.append(f"    Layer:    Integration (data passing between tools)")
    lines.append(f"    Fix:      Code change — is_ambiguous = args.get('is_ambiguous', False)")
    lines.append(f"    Impact:   {bs['dropped_fields']} → {fs['dropped_fields']} dropped fields")
    lines.append(f"              {bs['escalation_failures']} → {fs['escalation_failures']} escalation failures\n")

    lines.append(f"  Bug 2 (Model Output):")
    lines.append(f"    Problem:  Vague system prompt without priority rubric")
    lines.append(f"    Layer:    Model output (prompt quality)")
    lines.append(f"    Fix:      Prompt change — added explicit URGENT/HIGH/MEDIUM/LOW rubric")
    lines.append(f"    Impact:   {bs['priority_mismatches']} → {fs['priority_mismatches']} priority mismatches\n")

    report = "\n".join(lines)
    print(report)

    # Save comparison report
    comparison_path = os.path.join(output_dir, "comparison.md")
    os.makedirs(output_dir, exist_ok=True)
    with open(comparison_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  Comparison report saved to: {comparison_path}")
    print(f"  Traces saved to: {output_dir}/\n")

    return broken_trace, fixed_trace


if __name__ == "__main__":
    main()
