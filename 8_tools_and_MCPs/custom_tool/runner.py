"""
runner.py — Run 5 test queries through the custom tool implementation.

Usage:
    uv run python .\\8_tools_and_MCPs\\custom_tool\\runner.py
"""

from __future__ import annotations

import json
import os
import sys

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tool_executor import run_agent_query, execute_tool
from tool_definitions import TOOL_DEFINITIONS

# Standard test queries used by all three implementations
TEST_QUERIES = [
    ("SKU lookup (exists)",      "inventory_lookup",    {"sku": "SKU-003"}),
    ("SKU lookup (not found)",   "inventory_lookup",    {"sku": "SKU-999"}),
    ("Name search",              "inventory_search",    {"query": "desk"}),
    ("Low stock report",         "inventory_low_stock", {}),
    ("Search (no results)",      "inventory_search",    {"query": "xyz-nonexistent"}),
]


def main():
    print("\n" + "=" * 70)
    print("  IMPLEMENTATION 1: Custom Tool (Anthropic tool_use)")
    print("=" * 70)

    # Show tool definitions
    print(f"\n  Registered {len(TOOL_DEFINITIONS)} tools:")
    for td in TOOL_DEFINITIONS:
        print(f"    • {td['name']}: {td['description'][:70]}...")

    # Run test queries
    print(f"\n  Running {len(TEST_QUERIES)} test queries...\n")

    results = []
    for label, tool_name, tool_input in TEST_QUERIES:
        result = execute_tool(tool_name, tool_input)
        results.append({
            "label": label,
            "tool_name": tool_name,
            "tool_input": tool_input,
            "result": result,
        })

        # Display
        result_preview = json.dumps(result, indent=2)
        if len(result_preview) > 200:
            result_preview = result_preview[:200] + "..."
        print(f"  Query: {label}")
        print(f"    Tool:   {tool_name}")
        print(f"    Input:  {json.dumps(tool_input)}")
        if "error" in result:
            err = result["error"]
            print(f"    Error:  [{err['category']}] {err['description']}")
        else:
            if "product" in result:
                p = result["product"]
                print(f"    Result: {p['name']} — ${p['price']}, {p['stock']} in stock")
            elif "products" in result:
                print(f"    Result: {result['count']} product(s) returned")
        print()

    print("  " + "=" * 66)

    return results


if __name__ == "__main__":
    main()
