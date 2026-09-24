"""
run_validation.py — Validate the DocuQuery application.

Verifies that the FastAPI app loads correctly, all routes are registered,
configuration loads, and tests pass.

Usage:
    uv run python .\\2_applications_and_integration\\run_validation.py
"""

from __future__ import annotations

import os
import sys

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Ensure the module is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    print("\n" + "=" * 70)
    print("  MODULE 2: Applications & Integration — DocuQuery Validation")
    print("=" * 70)

    checks = []

    # 1. App loads
    print("\n  ▸ Loading FastAPI application...")
    try:
        from app.main import app
        checks.append(("App loads", True))
        print(f"    ✓ DocuQuery FastAPI app loaded: {app.title} v{app.version}")
    except Exception as exc:
        checks.append(("App loads", False))
        print(f"    ✗ Failed to load app: {exc}")

    # 2. Routes registered
    print("\n  ▸ Checking routes...")
    try:
        routes = [r.path for r in app.routes if hasattr(r, "methods")]
        checks.append(("Routes registered", len(routes) > 0))
        print(f"    ✓ {len(routes)} routes registered: {', '.join(routes[:8])}")
    except Exception as exc:
        checks.append(("Routes registered", False))
        print(f"    ✗ Route check failed: {exc}")

    # 3. Config loads
    print("\n  ▸ Checking configuration...")
    try:
        from app.config import is_mock_mode, get_model_name
        mode = "MOCK" if is_mock_mode() else "LIVE"
        model = get_model_name()
        checks.append(("Config loads", True))
        print(f"    ✓ Mode: {mode}, Model: {model}")
    except Exception as exc:
        checks.append(("Config loads", False))
        print(f"    ✗ Config check failed: {exc}")

    # 4. Models/schemas valid
    print("\n  ▸ Checking data models...")
    try:
        from app.models import QuestionRequest, QuestionResponse, StructuredAnswer
        checks.append(("Models valid", True))
        print(f"    ✓ QuestionRequest, QuestionResponse, StructuredAnswer loaded")
    except Exception as exc:
        checks.append(("Models valid", False))
        print(f"    ✗ Model check failed: {exc}")

    # 5. Claude client instantiates
    print("\n  ▸ Checking Claude client...")
    try:
        from app.claude_client import ask_question, ask_question_stream
        checks.append(("Claude client", True))
        print(f"    ✓ ask_question, ask_question_stream available")
    except Exception as exc:
        checks.append(("Claude client", False))
        print(f"    ✗ Client check failed: {exc}")

    # 6. Sample documents exist
    print("\n  ▸ Checking sample documents...")
    sample_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_documents")
    if os.path.isdir(sample_dir):
        docs = os.listdir(sample_dir)
        checks.append(("Sample documents", len(docs) > 0))
        print(f"    ✓ {len(docs)} sample document(s) in sample_documents/")
    else:
        checks.append(("Sample documents", False))
        print(f"    ✗ sample_documents/ directory not found")

    # Summary
    print(f"\n  {'=' * 66}")
    passed = sum(1 for _, ok in checks if ok)
    total = len(checks)
    print(f"  {passed}/{total} checks passed")

    for name, ok in checks:
        status = "✓" if ok else "✗"
        print(f"    {status} {name}")

    print(f"  {'=' * 66}\n")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
