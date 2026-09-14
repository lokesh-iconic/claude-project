"""
run.py -- Task C runner: long-document summarization with prompt caching.

Measures the cost difference between cached and uncached summarization
to demonstrate real, measured cost reduction on repeat calls.

Usage:
    uv run python .\\5_model_selection_and_optimization\\task_c_summarization\\run.py
"""

from __future__ import annotations

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import ModelId, MODELS, format_cost, calculate_cost, PRICING
from tracker import MetricsTracker
from task_c_summarization.documents import DOCUMENTS, FOLLOW_UP_QUESTIONS
from task_c_summarization.summarizer import run_caching_comparison


def main():
    print("\n" + "=" * 70)
    print("  TASK C: Long-Document Summarization -- Prompt Caching")
    print("=" * 70)
    print(f"\n  Model: {MODELS[ModelId.SONNET].display_name}")
    print(f"  Documents: {len(DOCUMENTS)}")
    print(f"  Strategy: cache document in system prompt, measure cost savings\n")

    tracker = MetricsTracker()

    # Run each document with cached and uncached
    for doc in DOCUMENTS:
        questions = FOLLOW_UP_QUESTIONS.get(doc.id, [])
        total_calls = 1 + len(questions)  # summary + follow-ups
        print(f"  [{doc.id}] {doc.title}")
        print(f"    Words: {doc.word_count:,} | Calls: {total_calls} (1 summary + {len(questions)} follow-ups)")

        run_caching_comparison(doc, questions, tracker)
        print(f"    Done.")

    # --- Per-Document Results ---
    print(f"\n  {'='*66}")
    print(f"  CACHING COST COMPARISON (per document)")
    print(f"  {'='*66}\n")

    total_cached_cost = 0.0
    total_uncached_cost = 0.0

    for doc in DOCUMENTS:
        cached_task = f"TaskC-Cached-{doc.id}"
        uncached_task = f"TaskC-NoCache-{doc.id}"

        cached_summary = tracker.get_task_summary(cached_task)
        uncached_summary = tracker.get_task_summary(uncached_task)

        if cached_summary and uncached_summary:
            savings = uncached_summary.total_cost_usd - cached_summary.total_cost_usd
            savings_pct = (savings / uncached_summary.total_cost_usd * 100) if uncached_summary.total_cost_usd > 0 else 0

            total_cached_cost += cached_summary.total_cost_usd
            total_uncached_cost += uncached_summary.total_cost_usd

            print(f"  {doc.title}")
            print(f"    {'':>4}{'Metric':<25} {'Cached':>12} {'No Cache':>12} {'Savings':>12}")
            print(f"    {'':>4}{'-'*61}")
            print(f"    {'':>4}{'Total cost':<25} {format_cost(cached_summary.total_cost_usd):>12} "
                  f"{format_cost(uncached_summary.total_cost_usd):>12} "
                  f"{format_cost(savings):>12}")
            print(f"    {'':>4}{'Cache write tokens':<25} {cached_summary.total_cache_write_tokens:>12,} "
                  f"{'0':>12} {'--':>12}")
            print(f"    {'':>4}{'Cache read tokens':<25} {cached_summary.total_cache_read_tokens:>12,} "
                  f"{'0':>12} {'--':>12}")
            print(f"    {'':>4}{'Input tokens (non-cache)':<25} {cached_summary.total_input_tokens:>12,} "
                  f"{uncached_summary.total_input_tokens:>12,}")
            print(f"    {'':>4}{'Avg latency':<25} {cached_summary.avg_latency_seconds:>11.3f}s "
                  f"{uncached_summary.avg_latency_seconds:>11.3f}s")
            print(f"    {'':>4}{'Cost reduction':<25} {'':>12} {'':>12} {savings_pct:>11.1f}%")
            print()

    # --- Overall Summary ---
    print(f"  {'='*66}")
    print(f"  OVERALL CACHING IMPACT")
    print(f"  {'='*66}\n")

    total_savings = total_uncached_cost - total_cached_cost
    total_savings_pct = (total_savings / total_uncached_cost * 100) if total_uncached_cost > 0 else 0

    print(f"  Total cost WITH caching:      {format_cost(total_cached_cost)}")
    print(f"  Total cost WITHOUT caching:   {format_cost(total_uncached_cost)}")
    print(f"  Total savings:                {format_cost(total_savings)} ({total_savings_pct:.1f}%)")

    # --- Pricing Breakdown ---
    print(f"\n  How caching saves money:")
    p = PRICING[ModelId.SONNET]
    print(f"    Standard input:   ${p.input_per_mtok:.2f}/MTok")
    print(f"    Cache write:      ${p.cache_write_per_mtok:.2f}/MTok (1.25x input -- first call only)")
    print(f"    Cache read:       ${p.cache_read_per_mtok:.2f}/MTok (0.1x input -- subsequent calls)")
    print(f"\n    On a {DOCUMENTS[0].word_count:,}-word document (~{DOCUMENTS[0].word_count * 4 // 3:,} tokens):")

    doc_tokens = DOCUMENTS[0].word_count * 4 // 3
    uncached_cost_3 = calculate_cost(ModelId.SONNET, doc_tokens * 3, 250 * 3)
    cached_cost_3 = (
        calculate_cost(ModelId.SONNET, 50, 250, cache_write_tokens=doc_tokens)
        + calculate_cost(ModelId.SONNET, 50, 200, cache_read_tokens=doc_tokens) * 2
    )
    print(f"    3 calls uncached: {format_cost(uncached_cost_3)}")
    print(f"    3 calls cached:   {format_cost(cached_cost_3)} "
          f"(saves {(uncached_cost_3 - cached_cost_3) / uncached_cost_3 * 100:.0f}%)")

    # --- Self-Check ---
    print(f"\n  {'='*66}")
    print(f"  SELF-CHECK: Does caching show REAL, MEASURED cost reduction?")
    print(f"  {'='*66}\n")

    if total_savings > 0:
        print(f"  YES. Caching reduced total cost by {format_cost(total_savings)} ({total_savings_pct:.1f}%).")
        print(f"  This is a measured reduction, not an assumption.")
        print(f"\n  The savings come from replacing full input token charges")
        print(f"  (${p.input_per_mtok}/MTok) with cache read charges (${p.cache_read_per_mtok}/MTok)")
        print(f"  on repeat queries against the same document.")
        print(f"\n  Break-even: caching pays for itself after the 2nd call against a document.")
    else:
        print(f"  NO savings detected. Check the caching implementation.")

    print(f"\n{'='*70}\n")

    return tracker


if __name__ == "__main__":
    main()
