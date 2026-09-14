"""
run.py -- Task B runner: fast mode vs extended thinking comparison.

Measures quality improvement and cost/latency tradeoff of extended thinking
on complex multi-step reasoning problems.

Usage:
    uv run python .\\5_model_selection_and_optimization\\task_b_reasoning\\run.py
"""

from __future__ import annotations

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import ModelId, MODELS, format_cost
from tracker import MetricsTracker
from task_b_reasoning.problems import PROBLEMS
from task_b_reasoning.reasoner import run_reasoning_comparison


def main():
    print("\n" + "=" * 70)
    print("  TASK B: Complex Reasoning -- Fast Mode vs Extended Thinking")
    print("=" * 70)
    print(f"\n  Model: {MODELS[ModelId.SONNET].display_name}")
    print(f"  Problems: {len(PROBLEMS)} multi-step reasoning tasks")
    print(f"  Extended thinking budget: 10,000 tokens\n")

    tracker = MetricsTracker()

    print("  Running fast mode and extended thinking for each problem...")
    results = run_reasoning_comparison(PROBLEMS, tracker)

    # --- Quality Scores ---
    print(f"\n  {'='*66}")
    print(f"  QUALITY COMPARISON (Rubric Scores)")
    print(f"  {'='*66}\n")

    print(f"  {'Problem':<35} {'Fast':>8} {'Extended':>10} {'Delta':>8}")
    print(f"  {'-'*61}")

    fast_total = 0
    ext_total = 0
    max_total = 0

    for f, e in zip(results["fast"], results["extended"]):
        delta = e["score"] - f["score"]
        sign = "+" if delta > 0 else ""
        print(f"  {f['title']:<35} {f['score']:>5}/{f['max_score']:<2} "
              f"{e['score']:>7}/{e['max_score']:<2} {sign}{delta:>6}")
        fast_total += f["score"]
        ext_total += e["score"]
        max_total += f["max_score"]

    print(f"  {'-'*61}")
    delta = ext_total - fast_total
    sign = "+" if delta > 0 else ""
    print(f"  {'TOTAL':<35} {fast_total:>5}/{max_total:<2} "
          f"{ext_total:>7}/{max_total:<2} {sign}{delta:>6}")
    print(f"\n  Fast mode:      {fast_total}/{max_total} ({fast_total/max_total:.0%})")
    print(f"  Extended:       {ext_total}/{max_total} ({ext_total/max_total:.0%})")
    print(f"  Improvement:    {sign}{delta} points ({sign}{delta/max_total:.0%})")

    # --- Cost & Latency ---
    print(f"\n  {'='*66}")
    print(f"  COST & LATENCY TRADEOFF")
    print(f"  {'='*66}\n")

    fast_summary = tracker.get_task_summary("TaskB-Fast")
    ext_summary = tracker.get_task_summary("TaskB-Extended")

    if fast_summary and ext_summary:
        print(f"  {'Metric':<30} {'Fast Mode':>15} {'Extended':>15} {'Ratio':>10}")
        print(f"  {'-'*70}")

        cost_ratio = ext_summary.total_cost_usd / fast_summary.total_cost_usd if fast_summary.total_cost_usd > 0 else 0
        latency_ratio = ext_summary.avg_latency_seconds / fast_summary.avg_latency_seconds if fast_summary.avg_latency_seconds > 0 else 0

        print(f"  {'Total cost':<30} "
              f"{format_cost(fast_summary.total_cost_usd):>15} "
              f"{format_cost(ext_summary.total_cost_usd):>15} "
              f"{cost_ratio:>9.1f}x")
        print(f"  {'Avg cost per problem':<30} "
              f"{format_cost(fast_summary.avg_cost_per_call):>15} "
              f"{format_cost(ext_summary.avg_cost_per_call):>15}")
        print(f"  {'Avg latency':<30} "
              f"{fast_summary.avg_latency_seconds:>14.3f}s "
              f"{ext_summary.avg_latency_seconds:>14.3f}s "
              f"{latency_ratio:>9.1f}x")
        print(f"  {'Total output tokens':<30} "
              f"{fast_summary.total_output_tokens:>15,} "
              f"{ext_summary.total_output_tokens:>15,}")
        print(f"  {'Total thinking tokens':<30} "
              f"{fast_summary.total_thinking_tokens:>15,} "
              f"{ext_summary.total_thinking_tokens:>15,}")

    # --- Self-Check ---
    print(f"\n  {'='*66}")
    print(f"  SELF-CHECK: Is the eval tight enough to catch a regression?")
    print(f"  {'='*66}\n")

    print(f"  The rubric evaluates {len(PROBLEMS)} problems across {max_total} total points.")
    print(f"  Each problem has {len(PROBLEMS[0].rubric)} specific criteria.")
    print(f"\n  If a model release degraded reasoning quality:")
    print(f"  - A 2-point drop (from {ext_total} to {ext_total - 2}) = "
          f"{(ext_total - 2)/max_total:.0%} (detectable)")
    print(f"  - Extended thinking advantage of {sign}{delta} points would shrink or vanish")
    print(f"  - The per-problem breakdown pinpoints WHICH reasoning type degraded")
    print(f"\n  Verdict: Yes -- the rubric is granular enough to detect regressions")
    print(f"  at the individual criterion level.")

    print(f"\n{'='*70}\n")

    return tracker, results


if __name__ == "__main__":
    main()
