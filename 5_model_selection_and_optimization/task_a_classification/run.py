"""
run.py -- Task A runner: high-volume classification benchmark.

Runs the email classifier with Haiku (fast/cheap) and Sonnet (capable/expensive),
compares accuracy and throughput, and proves whether the cheaper model suffices.

Usage:
    uv run python .\\5_model_selection_and_optimization\\task_a_classification\\run.py
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
from task_a_classification.dataset import SAMPLES, ACCURACY_BAR
from task_a_classification.classifier import run_classification_batch


def compute_accuracy(results: list[dict]) -> dict:
    """Compute overall and per-category accuracy."""
    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    overall = correct / total if total else 0

    categories = sorted(set(r["actual"] for r in results))
    per_cat = {}
    for cat in categories:
        cat_results = [r for r in results if r["actual"] == cat]
        cat_correct = sum(1 for r in cat_results if r["correct"])
        per_cat[cat] = cat_correct / len(cat_results) if cat_results else 0

    return {"overall": overall, "correct": correct, "total": total, "per_category": per_cat}


def main():
    print("\n" + "=" * 70)
    print("  TASK A: High-Volume Classification -- Haiku vs Sonnet")
    print("=" * 70)
    print(f"\n  Accuracy bar: {ACCURACY_BAR:.0%} (defined upfront)")
    print(f"  Dataset: {len(SAMPLES)} labeled emails, 5 categories\n")

    tracker = MetricsTracker()

    # --- Run Haiku (the candidate fast/cheap model) ---
    print(f"  [1/2] Running {MODELS[ModelId.HAIKU].display_name}...")
    haiku_results = run_classification_batch(
        SAMPLES, ModelId.HAIKU, tracker, "TaskA-Haiku"
    )
    haiku_acc = compute_accuracy(haiku_results)

    # --- Run Sonnet (the expensive baseline) ---
    print(f"  [2/2] Running {MODELS[ModelId.SONNET].display_name}...")
    sonnet_results = run_classification_batch(
        SAMPLES, ModelId.SONNET, tracker, "TaskA-Sonnet"
    )
    sonnet_acc = compute_accuracy(sonnet_results)

    # --- Results ---
    print(f"\n  {'='*66}")
    print(f"  ACCURACY COMPARISON")
    print(f"  {'='*66}\n")

    print(f"  {'Model':<25} {'Accuracy':>10} {'Correct':>10} {'Meets Bar':>12}")
    print(f"  {'-'*57}")

    haiku_pass = haiku_acc["overall"] >= ACCURACY_BAR
    sonnet_pass = sonnet_acc["overall"] >= ACCURACY_BAR

    print(f"  {MODELS[ModelId.HAIKU].display_name:<25} "
          f"{haiku_acc['overall']:>9.1%} "
          f"{haiku_acc['correct']:>5}/{haiku_acc['total']:<4} "
          f"{'YES' if haiku_pass else 'NO':>12}")
    print(f"  {MODELS[ModelId.SONNET].display_name:<25} "
          f"{sonnet_acc['overall']:>9.1%} "
          f"{sonnet_acc['correct']:>5}/{sonnet_acc['total']:<4} "
          f"{'YES' if sonnet_pass else 'NO':>12}")

    # Per-category breakdown
    print(f"\n  Per-Category Accuracy:")
    print(f"  {'Category':<15} {'Haiku':>10} {'Sonnet':>10}")
    print(f"  {'-'*35}")
    for cat in sorted(haiku_acc["per_category"].keys()):
        h = haiku_acc["per_category"].get(cat, 0)
        s = sonnet_acc["per_category"].get(cat, 0)
        print(f"  {cat:<15} {h:>9.0%} {s:>9.0%}")

    # --- Cost & Throughput ---
    print(f"\n  {'='*66}")
    print(f"  COST & THROUGHPUT COMPARISON")
    print(f"  {'='*66}\n")

    haiku_summary = tracker.get_task_summary("TaskA-Haiku")
    sonnet_summary = tracker.get_task_summary("TaskA-Sonnet")

    print(f"  {'Metric':<30} {'Haiku':>15} {'Sonnet':>15} {'Ratio':>10}")
    print(f"  {'-'*70}")

    if haiku_summary and sonnet_summary:
        cost_ratio = sonnet_summary.total_cost_usd / haiku_summary.total_cost_usd if haiku_summary.total_cost_usd > 0 else 0
        latency_ratio = sonnet_summary.avg_latency_seconds / haiku_summary.avg_latency_seconds if haiku_summary.avg_latency_seconds > 0 else 0

        print(f"  {'Total cost (50 emails)':<30} "
              f"{format_cost(haiku_summary.total_cost_usd):>15} "
              f"{format_cost(sonnet_summary.total_cost_usd):>15} "
              f"{cost_ratio:>9.1f}x")
        print(f"  {'Avg cost per call':<30} "
              f"{format_cost(haiku_summary.avg_cost_per_call):>15} "
              f"{format_cost(sonnet_summary.avg_cost_per_call):>15}")
        print(f"  {'Avg latency':<30} "
              f"{haiku_summary.avg_latency_seconds:>14.3f}s "
              f"{sonnet_summary.avg_latency_seconds:>14.3f}s "
              f"{latency_ratio:>9.1f}x")
        print(f"  {'Throughput':<30} "
              f"{haiku_summary.throughput_calls_per_sec:>13.1f}/s "
              f"{sonnet_summary.throughput_calls_per_sec:>13.1f}/s")
        print(f"  {'Total tokens':<30} "
              f"{haiku_summary.total_input_tokens + haiku_summary.total_output_tokens:>15,} "
              f"{sonnet_summary.total_input_tokens + sonnet_summary.total_output_tokens:>15,}")

    # --- Self-Check ---
    print(f"\n  {'='*66}")
    print(f"  SELF-CHECK: Would Sonnet improve outcomes?")
    print(f"  {'='*66}\n")

    if haiku_pass:
        acc_diff = sonnet_acc["overall"] - haiku_acc["overall"]
        print(f"  Haiku accuracy:  {haiku_acc['overall']:.1%} (meets {ACCURACY_BAR:.0%} bar)")
        print(f"  Sonnet accuracy: {sonnet_acc['overall']:.1%}")
        print(f"  Accuracy delta:  {acc_diff:+.1%}")
        print(f"\n  VERDICT: Haiku MEETS the accuracy bar. Switching to Sonnet would")
        print(f"  cost {cost_ratio:.1f}x more for {'+' if acc_diff >= 0 else ''}{acc_diff:.1%} accuracy change.")
        print(f"  For high-volume classification, Haiku is the right choice.")
    else:
        print(f"  Haiku accuracy:  {haiku_acc['overall']:.1%} (BELOW {ACCURACY_BAR:.0%} bar)")
        print(f"  Sonnet accuracy: {sonnet_acc['overall']:.1%}")
        print(f"\n  VERDICT: Haiku does NOT meet the accuracy bar.")
        if sonnet_pass:
            print(f"  Sonnet meets it -- use Sonnet despite the higher cost.")
        else:
            print(f"  Neither model meets the bar -- revisit the prompt or task design.")

    print(f"\n{'='*70}\n")

    return tracker, haiku_acc, sonnet_acc


if __name__ == "__main__":
    main()
