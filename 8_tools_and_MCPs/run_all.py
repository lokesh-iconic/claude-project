"""
run_all.py — Run all three implementations and compare results.

Executes the same 5 queries against custom tool, skill, and MCP server,
then checks that all three produce equivalent results.

Usage:
    uv run python .\\8_tools_and_MCPs\\run_all.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    print("\n" + "#" * 70)
    print("#  MODULE 8: Tools and MCPs — Build the Same Capability Three Ways")
    print("#" * 70)

    # --- Implementation 1: Custom Tool ---
    from custom_tool.runner import main as run_custom_tool
    custom_results = run_custom_tool()

    # --- Implementation 2: Skill ---
    from skill.runner import main as run_skill
    skill_results = run_skill()

    # --- Implementation 3: MCP Server ---
    from mcp_server.runner import main as run_mcp
    mcp_results = run_mcp()

    # --- Equivalence Check ---
    print("\n" + "#" * 70)
    print("#  EQUIVALENCE CHECK")
    print("#" * 70)

    all_pass = True
    mcp_available = mcp_results is not None

    print(f"\n  {'#':<3} {'Query':<25} {'Custom Tool':>12} {'Skill':>12} {'MCP':>12}  {'Match'}")
    print(f"  {'─'*3}  {'─'*24} {'─'*12} {'─'*12} {'─'*12}  {'─'*6}")

    for i in range(len(custom_results)):
        ct = custom_results[i]
        sk = skill_results[i]

        ct_result = ct["result"]
        sk_result = sk["result"]

        # Determine result type for display
        ct_type = _result_summary(ct_result)
        sk_type = _result_summary(sk_result)

        # Compare custom tool vs skill
        results_match = _results_equivalent(ct_result, sk_result)

        # Compare with MCP if available
        if mcp_available and i < len(mcp_results):
            mc = mcp_results[i]
            mc_result = mc["result"]
            mc_type = _result_summary(mc_result)
            mcp_match = _results_equivalent(ct_result, mc_result)
            results_match = results_match and mcp_match
        else:
            mc_type = "N/A"

        match_str = "✓ PASS" if results_match else "✗ FAIL"
        if not results_match:
            all_pass = False

        label = ct["label"]
        print(f"  {i+1:<3} {label:<25} {ct_type:>12} {sk_type:>12} {mc_type:>12}  {match_str}")

    # Summary
    print(f"\n  {'='*70}")
    if all_pass:
        print("  ✓ All implementations produce EQUIVALENT results")
    else:
        print("  ✗ Some results DIFFER between implementations")

    if not mcp_available:
        print("  ⚠ MCP server was skipped (SDK not installed)")
        print("    Install with: uv add mcp")

    # --- Feature Comparison ---
    print(f"\n  {'='*70}")
    print("  FEATURE COMPARISON")
    print(f"  {'='*70}\n")

    print(f"  {'Feature':<35} {'Custom Tool':>12} {'Skill':>12} {'MCP Server':>12}")
    print(f"  {'─'*35} {'─'*12} {'─'*12} {'─'*12}")
    features = [
        ("Tool invocation",                   "✓",  "✓",  "✓"),
        ("Structured errors",                 "✓",  "✓",  "✓"),
        ("Read-only data resources",           "—",  "—",  "✓"),
        ("Prompt templates",                   "—",  "—",  "✓"),
        ("Cross-application reuse",            "—",  "✓",  "✓"),
        ("No code copying needed",             "—",  "✓",  "✓"),
        ("Works without SDK dependency",       "✓",  "✓",  "—"),
        ("Process isolation",                  "—",  "✓",  "✓"),
        ("Language-agnostic interface",         "—",  "—",  "✓"),
        ("Discoverable (list_tools)",           "—",  "—",  "✓"),
    ]
    for feat, ct, sk, mc in features:
        print(f"  {feat:<35} {ct:>12} {sk:>12} {mc:>12}")

    print(f"\n  {'='*70}\n")

    # --- Generate Report ---
    _generate_report(custom_results, skill_results, mcp_results, mcp_available)

    print(f"\n{'#' * 70}\n")


def _result_summary(result: dict) -> str:
    """One-word summary of a result for the comparison table."""
    if "error" in result:
        return f"err:{result['error']['category'][:8]}"
    if "product" in result:
        return "1 product"
    if "products" in result:
        return f"{result['count']} product" + ("s" if result["count"] != 1 else "")
    return "ok"


def _results_equivalent(a: dict, b: dict) -> bool:
    """Check if two results are structurally equivalent."""
    # Both errors with same category
    if "error" in a and "error" in b:
        return a["error"]["category"] == b["error"]["category"]

    # Both have product
    if "product" in a and "product" in b:
        return a["product"]["sku"] == b["product"]["sku"]

    # Both have products list
    if "products" in a and "products" in b:
        if a["count"] != b["count"]:
            return False
        a_skus = sorted(p["sku"] for p in a["products"])
        b_skus = sorted(p["sku"] for p in b["products"])
        return a_skus == b_skus

    return False


def _generate_report(custom_results, skill_results, mcp_results, mcp_available):
    """Generate a markdown report to output/."""
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)

    lines = [
        "# Module 8: Tools and MCPs — Comparison Report\n",
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n",
        "## Equivalence Results\n",
        "| # | Query | Custom Tool | Skill | MCP | Match |",
        "|---|-------|------------|-------|-----|-------|",
    ]

    for i in range(len(custom_results)):
        ct = custom_results[i]
        sk = skill_results[i]
        ct_s = _result_summary(ct["result"])
        sk_s = _result_summary(sk["result"])

        if mcp_available and mcp_results and i < len(mcp_results):
            mc_s = _result_summary(mcp_results[i]["result"])
            match = _results_equivalent(ct["result"], sk["result"]) and \
                    _results_equivalent(ct["result"], mcp_results[i]["result"])
        else:
            mc_s = "N/A"
            match = _results_equivalent(ct["result"], sk["result"])

        lines.append(f"| {i+1} | {ct['label']} | {ct_s} | {sk_s} | {mc_s} | {'✓' if match else '✗'} |")

    lines.append("")
    lines.append("## Implementation Summary\n")
    lines.append("| Aspect | Custom Tool | Skill | MCP Server |")
    lines.append("|--------|------------|-------|------------|")
    lines.append("| Interface | JSON Schema + executor | CLI script + SKILL.md | FastMCP + stdio |")
    lines.append("| Error handling | Structured (category, retryable) | Structured (same) | Structured (same) |")
    lines.append("| Reusable across apps | No (code must be copied) | Yes (reference SKILL.md) | Yes (run as separate process) |")
    lines.append("| Fastest to build | ✓ (just Python functions) | Medium (needs packaging) | Slowest (needs SDK) |")
    lines.append("| Production choice | For single-app use | For Claude Code workflows | For multi-app/multi-language |")
    lines.append("")

    report_path = os.path.join(output_dir, "comparison_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  Report saved to: {report_path}")


if __name__ == "__main__":
    main()
