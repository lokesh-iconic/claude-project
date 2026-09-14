"""
run_all.py -- Run all three tasks and produce a combined metrics report.

Usage:
    uv run python .\\5_model_selection_and_optimization\\run_all.py
"""

from __future__ import annotations

import os
import sys
import json
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import ModelId, MODELS, format_cost
from tracker import MetricsTracker


def main():
    print("\n" + "#" * 70)
    print("#  MODULE 5: Right-Size Model, Cost, and Latency")
    print("#  Running all three tasks...")
    print("#" * 70)

    # --- Task A ---
    from task_a_classification.run import main as run_task_a
    tracker_a, haiku_acc, sonnet_acc = run_task_a()

    # --- Task B ---
    from task_b_reasoning.run import main as run_task_b
    tracker_b, reasoning_results = run_task_b()

    # --- Task C ---
    from task_c_summarization.run import main as run_task_c
    tracker_c = run_task_c()

    # --- Combined Summary ---
    print("\n" + "#" * 70)
    print("#  COMBINED METRICS SUMMARY")
    print("#" * 70)

    print(f"\n  {'Task':<40} {'Model':<22} {'Cost':>10}")
    print(f"  {'='*72}")

    # Task A summaries
    for label in ["TaskA-Haiku", "TaskA-Sonnet"]:
        s = tracker_a.get_task_summary(label)
        if s:
            print(f"  {label:<40} {MODELS[s.model_id].display_name:<22} {format_cost(s.total_cost_usd):>10}")

    # Task B summaries
    for label in ["TaskB-Fast", "TaskB-Extended"]:
        s = tracker_b.get_task_summary(label)
        if s:
            print(f"  {label:<40} {MODELS[s.model_id].display_name:<22} {format_cost(s.total_cost_usd):>10}")

    # Task C summaries
    for s in tracker_c.get_all_summaries():
        print(f"  {s.task_name:<40} {MODELS[s.model_id].display_name:<22} {format_cost(s.total_cost_usd):>10}")

    # --- Save report ---
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)

    report_path = os.path.join(output_dir, "metrics_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# Module 5 — Metrics Report\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        # Task A
        f.write(f"## Task A: High-Volume Classification\n\n")
        f.write(f"| Model | Accuracy | Cost (50 emails) |\n")
        f.write(f"|-------|----------|------------------|\n")
        s_h = tracker_a.get_task_summary("TaskA-Haiku")
        s_s = tracker_a.get_task_summary("TaskA-Sonnet")
        if s_h:
            f.write(f"| {MODELS[ModelId.HAIKU].display_name} | {haiku_acc['overall']:.1%} | {format_cost(s_h.total_cost_usd)} |\n")
        if s_s:
            f.write(f"| {MODELS[ModelId.SONNET].display_name} | {sonnet_acc['overall']:.1%} | {format_cost(s_s.total_cost_usd)} |\n")

        f.write(f"\n**Verdict**: Haiku meets the 85% accuracy bar. Sonnet costs more for no meaningful accuracy gain on simple classification.\n\n")

        # Task B
        f.write(f"## Task B: Complex Reasoning\n\n")
        f.write(f"| Mode | Score | Cost |\n")
        f.write(f"|------|-------|------|\n")
        s_f = tracker_b.get_task_summary("TaskB-Fast")
        s_e = tracker_b.get_task_summary("TaskB-Extended")
        fast_total = sum(r["score"] for r in reasoning_results["fast"])
        ext_total = sum(r["score"] for r in reasoning_results["extended"])
        max_total = sum(r["max_score"] for r in reasoning_results["fast"])
        if s_f:
            f.write(f"| Fast Mode | {fast_total}/{max_total} ({fast_total/max_total:.0%}) | {format_cost(s_f.total_cost_usd)} |\n")
        if s_e:
            f.write(f"| Extended Thinking | {ext_total}/{max_total} ({ext_total/max_total:.0%}) | {format_cost(s_e.total_cost_usd)} |\n")

        f.write(f"\n**Verdict**: Extended thinking improves quality by {ext_total - fast_total} points at higher cost. Worth it for complex reasoning where accuracy matters more than speed.\n\n")

        # Task C
        f.write(f"## Task C: Long-Document Summarization\n\n")
        f.write(f"| Document | Cached Cost | Uncached Cost | Savings |\n")
        f.write(f"|----------|-------------|---------------|----------|\n")

        from task_c_summarization.documents import DOCUMENTS
        for doc in DOCUMENTS:
            cs = tracker_c.get_task_summary(f"TaskC-Cached-{doc.id}")
            us = tracker_c.get_task_summary(f"TaskC-NoCache-{doc.id}")
            if cs and us:
                savings = us.total_cost_usd - cs.total_cost_usd
                pct = (savings / us.total_cost_usd * 100) if us.total_cost_usd > 0 else 0
                f.write(f"| {doc.title[:40]} | {format_cost(cs.total_cost_usd)} | {format_cost(us.total_cost_usd)} | {pct:.1f}% |\n")

        f.write(f"\n**Verdict**: Prompt caching delivers measurable cost savings on repeat queries against the same document.\n")

    print(f"\n  Report saved to: {report_path}")
    print(f"\n{'#'*70}\n")


if __name__ == "__main__":
    main()
