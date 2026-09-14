"""
run_session.py -- Run a 25-turn conversation and measure instruction-following drift.

Simulates a realistic long session with:
  - Topic exploration (authentication, database, deployment, API, caching)
  - Follow-up questions
  - Vague/ambiguous queries
  - Topic changes

At each turn, measures format compliance and checks for degradation.

Usage:
    uv run python .\\6_prompt_and_context_engineering\\run_session.py
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from assistant import TechSupportAssistant


# --------------------------------------------------------------------------
# 25-turn conversation script -- realistic sequence of user queries
# --------------------------------------------------------------------------

CONVERSATION_SCRIPT = [
    # Turns 1-5: Clear technical questions (baseline)
    "How does authentication work in our system?",
    "What OAuth grant types are supported?",
    "How do I rotate an API key?",
    "What's the session timeout configuration?",
    "Tell me about the rate limiting on login attempts",

    # Turns 6-10: Switch to database topic + follow-ups
    "Explain the database architecture",
    "What connection pool settings should I use?",
    "How do database migrations work?",
    "What's the backup and recovery strategy?",
    "How often are backups taken?",

    # Turns 11-15: Vague/ambiguous queries (stress test for format compliance)
    "My thing isn't working",
    "How do I make it faster?",
    "Something about the API is wrong",
    "Can you help with that deployment issue?",
    "What about caching?",

    # Turns 16-20: Topic switch to deployment + specific follow-ups
    "How does the CI/CD pipeline work?",
    "What happens during a canary deployment?",
    "How does automatic rollback work?",
    "What monitoring do we have in production?",
    "Explain the SLO targets",

    # Turns 21-25: Mix of topics and complexity levels
    "How do I set up a new REST API endpoint following our standards?",
    "What's the cache invalidation strategy?",
    "Compare the authentication methods available",
    "What are the error response formats for the API?",
    "Give me a summary of everything we discussed about security",
]


def main():
    print("\n" + "=" * 70)
    print("  MODULE 6: Prompt & Context Engineering — 25-Turn Session Test")
    print("=" * 70)

    assistant = TechSupportAssistant(live_mode=False)

    print(f"\n  Running {len(CONVERSATION_SCRIPT)} turns...\n")

    # Track compliance per turn
    compliance_log = []

    for i, query in enumerate(CONVERSATION_SCRIPT):
        turn = i + 1
        response = assistant.ask(query)

        compliance = response.format_compliance()
        all_pass = all(compliance.values())
        compliance_log.append(all_pass)

        # Print turn summary
        status = "PASS" if all_pass else "FAIL"
        query_preview = query[:50] + "..." if len(query) > 50 else query
        print(f"  Turn {turn:>2}: [{status}] {query_preview}")
        if not all_pass:
            failed = [k for k, v in compliance.items() if not v]
            print(f"          Failed: {', '.join(failed)}")

    # --- Drift Analysis ---
    print(f"\n  {'='*66}")
    print(f"  DRIFT ANALYSIS: Early vs. Late Turns")
    print(f"  {'='*66}\n")

    early_turns = compliance_log[:5]
    mid_turns = compliance_log[10:15]
    late_turns = compliance_log[20:25]

    early_rate = sum(early_turns) / len(early_turns)
    mid_rate = sum(mid_turns) / len(mid_turns)
    late_rate = sum(late_turns) / len(late_turns)
    overall_rate = sum(compliance_log) / len(compliance_log)

    print(f"  {'Phase':<25} {'Turns':<15} {'Compliance':>12}")
    print(f"  {'-'*52}")
    print(f"  {'Early (baseline)':<25} {'1-5':<15} {early_rate:>11.0%}")
    print(f"  {'Mid (vague queries)':<25} {'11-15':<15} {mid_rate:>11.0%}")
    print(f"  {'Late (mixed topics)':<25} {'21-25':<15} {late_rate:>11.0%}")
    print(f"  {'Overall':<25} {'1-25':<15} {overall_rate:>11.0%}")

    drift = early_rate - late_rate
    if drift > 0.1:
        print(f"\n  WARNING: Format compliance degraded by {drift:.0%} from early to late turns.")
    else:
        print(f"\n  No significant drift detected. Late-turn compliance matches early turns.")

    # --- Context Growth ---
    print(f"\n  {'='*66}")
    print(f"  CONTEXT GROWTH & TOKEN USAGE")
    print(f"  {'='*66}\n")

    print(assistant.get_context_report())

    # --- Token Savings ---
    print(f"\n  {'='*66}")
    print(f"  TOKEN SAVINGS FROM PRUNING & COMPACTION")
    print(f"  {'='*66}\n")

    savings = assistant.get_savings_report()
    print(f"  Total turns:                {savings['total_turns']}")
    print(f"  Turns with compaction:      {savings['compacted_turns']}")
    print(f"  Tokens saved by pruning:    {savings['total_pruned_tokens']:,}")
    print(f"  Est. compaction savings:    {savings['estimated_compaction_savings']:,} tokens")

    # --- Self-Check ---
    print(f"\n  {'='*66}")
    print(f"  SELF-CHECK")
    print(f"  {'='*66}\n")

    print(f"  1. After 25 turns, is the system prompt still followed?")
    if late_rate >= early_rate - 0.1:
        print(f"     YES — Late-turn compliance ({late_rate:.0%}) matches early ({early_rate:.0%}).")
    else:
        print(f"     NO — Compliance degraded from {early_rate:.0%} to {late_rate:.0%}.")

    print(f"\n  2. Did pruning/compaction reduce token usage?")
    if savings['total_pruned_tokens'] > 0 or savings['compacted_turns'] > 0:
        print(f"     YES — {savings['total_pruned_tokens']:,} tokens pruned, "
              f"{savings['compacted_turns']} turns compacted.")
        # Compare context size at turn 8 vs turn 25
        metrics = assistant.get_metrics()
        if len(metrics) >= 25:
            turn_8_ctx = metrics[7].context_tokens
            turn_25_ctx = metrics[24].context_tokens
            growth = turn_25_ctx / turn_8_ctx if turn_8_ctx > 0 else 0
            print(f"     Context at turn 8: {turn_8_ctx:,} tokens")
            print(f"     Context at turn 25: {turn_25_ctx:,} tokens (would be ~{int(turn_8_ctx * 25/8):,} without compaction)")
    else:
        print(f"     NO savings detected.")

    print(f"\n{'='*70}\n")

    # --- Save report ---
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)

    report_path = os.path.join(output_dir, "session_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# Module 6 — Session Report\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write(f"## Drift Analysis\n\n")
        f.write(f"| Phase | Turns | Compliance |\n")
        f.write(f"|-------|-------|------------|\n")
        f.write(f"| Early (baseline) | 1-5 | {early_rate:.0%} |\n")
        f.write(f"| Mid (vague queries) | 11-15 | {mid_rate:.0%} |\n")
        f.write(f"| Late (mixed topics) | 21-25 | {late_rate:.0%} |\n")
        f.write(f"| Overall | 1-25 | {overall_rate:.0%} |\n\n")
        f.write(f"## Token Savings\n\n")
        f.write(f"- Tokens pruned: {savings['total_pruned_tokens']:,}\n")
        f.write(f"- Turns compacted: {savings['compacted_turns']}\n")
        f.write(f"- Est. compaction savings: {savings['estimated_compaction_savings']:,} tokens\n")

    print(f"  Report saved to: {report_path}\n")

    return assistant


if __name__ == "__main__":
    main()
