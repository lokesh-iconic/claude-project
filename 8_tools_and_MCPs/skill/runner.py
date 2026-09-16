"""
runner.py — Run 5 test queries through the Skill implementation (subprocess).

Invokes the skill script via subprocess, parses JSON output, and reports results.

Usage:
    uv run python .\\8_tools_and_MCPs\\skill\\runner.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

SKILL_SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "scripts",
    "inventory_skill.py",
)

# Same 5 test queries, mapped to CLI commands
TEST_QUERIES = [
    ("SKU lookup (exists)",      ["lookup", "SKU-003"]),
    ("SKU lookup (not found)",   ["lookup", "SKU-999"]),
    ("Name search",              ["search", "desk"]),
    ("Low stock report",         ["low-stock"]),
    ("Search (no results)",      ["search", "xyz-nonexistent"]),
]


def run_skill_command(args: list[str]) -> dict:
    """Invoke the skill script and return parsed JSON."""
    cmd = [sys.executable, SKILL_SCRIPT] + args
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        output = proc.stdout.strip()
        if not output:
            return {"error": {"category": "internal_error", "retryable": True,
                              "description": f"Skill produced no output. stderr: {proc.stderr.strip()}"}}
        return json.loads(output)
    except subprocess.TimeoutExpired:
        return {"error": {"category": "internal_error", "retryable": True,
                          "description": "Skill script timed out"}}
    except json.JSONDecodeError as exc:
        return {"error": {"category": "internal_error", "retryable": False,
                          "description": f"Invalid JSON from skill: {exc}"}}
    except Exception as exc:
        return {"error": {"category": "internal_error", "retryable": True,
                          "description": f"Failed to invoke skill: {exc}"}}


def main():
    print("\n" + "=" * 70)
    print("  IMPLEMENTATION 2: Skill (SKILL.md + CLI Script)")
    print("=" * 70)

    print(f"\n  Skill script: {SKILL_SCRIPT}")
    print(f"\n  Running {len(TEST_QUERIES)} test queries...\n")

    results = []
    for label, cli_args in TEST_QUERIES:
        result = run_skill_command(cli_args)
        results.append({
            "label": label,
            "cli_args": cli_args,
            "result": result,
        })

        # Display
        cmd_str = " ".join(cli_args)
        print(f"  Query: {label}")
        print(f"    Command: inventory_skill.py {cmd_str}")
        if "error" in result:
            err = result["error"]
            print(f"    Error:   [{err['category']}] {err['description']}")
        else:
            if "product" in result:
                p = result["product"]
                print(f"    Result:  {p['name']} — ${p['price']}, {p['stock']} in stock")
            elif "products" in result:
                print(f"    Result:  {result['count']} product(s) returned")
        print()

    print("  " + "=" * 66)

    return results


if __name__ == "__main__":
    main()
