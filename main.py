"""
main.py — Run all 8 modules sequentially.

Usage:
    uv run python main.py
"""

from __future__ import annotations

import subprocess
import sys
import os
import time

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Each module: (number, title, commands_list)
# Commands are (description, [cmd_args]) tuples
MODULES = [
    (
        1,
        "Agents & Workflows",
        [("Workflow vs Agent comparison", [sys.executable, os.path.join("1_agents_and_workflows", "run_comparison.py")])],
    ),
    (
        2,
        "Applications & Integration",
        [("DocuQuery server test", [
            sys.executable, "-c",
            "import sys, os; sys.path.insert(0, os.path.join(os.environ['PROJECT_ROOT'], "
            "'2_applications_and_integration')); "
            "from app.main import app; print('  DocuQuery FastAPI app loads successfully')"
        ])],
    ),
    (
        3,
        "Claude Code",
        [("Setup validation", [sys.executable, os.path.join("3_claude_code", "validate_setup.py")])],
    ),
    (
        4,
        "Eval, Testing & Debugging",
        [("Broken vs Fixed comparison", [sys.executable, os.path.join("4_eval_testing_and_debugging", "run_comparison.py")])],
    ),
    (
        5,
        "Model Selection & Optimization",
        [("All tasks", [sys.executable, os.path.join("5_model_selection_and_optimization", "run_all.py")])],
    ),
    (
        6,
        "Prompt & Context Engineering",
        [
            ("25-turn session test", [sys.executable, os.path.join("6_prompt_and_context_engineering", "run_session.py")]),
            ("Parser robustness test", [sys.executable, os.path.join("6_prompt_and_context_engineering", "run_parser_test.py")]),
        ],
    ),
    (
        7,
        "Security & Safety",
        [("Attack/defense comparison", [sys.executable, os.path.join("7_security_and_safety", "run_comparison.py")])],
    ),
    (
        8,
        "Tools and MCPs",
        [("Three-way comparison", [sys.executable, os.path.join("8_tools_and_MCPs", "run_all.py")])],
    ),
]


def run_module(number: int, title: str, commands: list) -> tuple[bool, float]:
    """Run a single module's commands. Returns (success, elapsed_seconds)."""
    print(f"\n{'█' * 70}")
    print(f"█  MODULE {number}: {title}")
    print(f"{'█' * 70}")

    start = time.time()
    all_passed = True

    for desc, cmd in commands:
        print(f"\n  ▸ {desc}")
        try:
            result = subprocess.run(
                cmd,
                cwd=PROJECT_ROOT,
                timeout=120,
                capture_output=False,
                env={**os.environ, "PROJECT_ROOT": PROJECT_ROOT},
            )
            if result.returncode != 0:
                print(f"  ✗ Exited with code {result.returncode}")
                all_passed = False
        except subprocess.TimeoutExpired:
            print(f"  ✗ Timed out after 120s")
            all_passed = False
        except Exception as exc:
            print(f"  ✗ Error: {exc}")
            all_passed = False

    elapsed = time.time() - start
    status = "✓ PASS" if all_passed else "✗ FAIL"
    print(f"\n  {status} — Module {number} completed in {elapsed:.1f}s")

    return all_passed, elapsed


def main():
    print("=" * 70)
    print("  CLAUDE PROJECT — Running All 8 Modules")
    print("=" * 70)

    results = []
    total_start = time.time()

    for number, title, commands in MODULES:
        passed, elapsed = run_module(number, title, commands)
        results.append((number, title, passed, elapsed))

    # Summary
    total_elapsed = time.time() - total_start

    print(f"\n\n{'=' * 70}")
    print("  SUMMARY")
    print(f"{'=' * 70}\n")

    print(f"  {'#':<4} {'Module':<40} {'Status':>8} {'Time':>8}")
    print(f"  {'─'*4} {'─'*40} {'─'*8} {'─'*8}")

    pass_count = 0
    for number, title, passed, elapsed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        if passed:
            pass_count += 1
        print(f"  {number:<4} {title:<40} {status:>8} {elapsed:>6.1f}s")

    print(f"\n  {'─'*62}")
    print(f"  Total: {pass_count}/{len(results)} modules passed in {total_elapsed:.1f}s")
    print(f"{'=' * 70}\n")

    # Save report
    _save_report(results, pass_count, total_elapsed)

    return 0 if pass_count == len(results) else 1


def _save_report(results, pass_count, total_elapsed):
    """Save a markdown report to output/run_report.md."""
    from datetime import datetime

    output_dir = os.path.join(PROJECT_ROOT, "output")
    os.makedirs(output_dir, exist_ok=True)
    report_path = os.path.join(output_dir, "run_report.md")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "# Claude Project — Run Report\n",
        f"**Date:** {now}  ",
        f"**Total time:** {total_elapsed:.1f}s  ",
        f"**Result:** {pass_count}/{len(results)} modules passed\n",
        "## Results\n",
        "| # | Module | Status | Time |",
        "|---|--------|--------|------|",
    ]

    for number, title, passed, elapsed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        lines.append(f"| {number} | {title} | {status} | {elapsed:.1f}s |")

    lines.append("")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"  Report saved to: {report_path}")


if __name__ == "__main__":
    sys.exit(main())
