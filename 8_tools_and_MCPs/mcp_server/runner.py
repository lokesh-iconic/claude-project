"""
runner.py — Run 5 test queries through the MCP server implementation.

Starts the MCP server as a subprocess, connects via stdio, runs queries,
and shuts down.

Usage:
    uv run python .\\8_tools_and_MCPs\\mcp_server\\runner.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from client import run_mcp_queries, HAS_MCP
except ImportError:
    HAS_MCP = False


def main():
    print("\n" + "=" * 70)
    print("  IMPLEMENTATION 3: MCP Server (FastMCP + stdio)")
    print("=" * 70)

    if not HAS_MCP:
        print("\n  ⚠  MCP SDK not installed. Skipping.")
        print("     Install with: uv add mcp")
        print("\n  " + "=" * 66)
        return None

    print("\n  Starting MCP server via stdio...\n")

    try:
        results, info = asyncio.run(run_mcp_queries())
    except Exception as exc:
        print(f"\n  ✗ MCP server error: {exc}")
        print("    Ensure 'mcp' package is installed: uv add mcp")
        print("\n  " + "=" * 66)
        return None

    # Display server info
    print(f"  Server capabilities:")
    print(f"    Tools:     {', '.join(info['tools'])}")
    print(f"    Resources: {', '.join(info['resources'])}")
    print(f"    Prompts:   {', '.join(info['prompts'])}")
    print()

    # Display results (first 5 are the standard tool queries)
    for entry in results[:5]:
        label = entry["label"]
        result = entry["result"]
        print(f"  Query: {label}")
        print(f"    Tool:   {entry['tool_name']}")
        print(f"    Input:  {json.dumps(entry['tool_input'])}")
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

    # Display bonus MCP features
    if len(results) > 5:
        print("  --- MCP-Exclusive Features ---\n")
        for entry in results[5:]:
            print(f"  {entry['label']}")
            if "total_products" in entry["result"]:
                print(f"    Catalog: {entry['result']['total_products']} products")
            elif "prompt_text" in entry["result"]:
                print(f"    Prompt:  {entry['result']['prompt_text']}")
            print()

    print("  " + "=" * 66)

    return results[:5]  # Return only the 5 standard results for comparison


if __name__ == "__main__":
    main()
