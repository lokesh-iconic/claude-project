"""
tool_executor.py — Execute tool calls and return structured results.

Receives a tool name and input dict (as the Anthropic API would provide in a
tool_use content block), validates, executes, and returns the result or a
structured error.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inventory_data import lookup_by_sku, search_by_name, list_low_stock
from error_model import not_found, invalid_input, internal_error, is_error


def execute_tool(tool_name: str, tool_input: dict) -> dict:
    """
    Execute a tool call and return structured JSON result.

    Parameters
    ----------
    tool_name : str
        One of: inventory_lookup, inventory_search, inventory_low_stock
    tool_input : dict
        The input parameters for the tool.

    Returns
    -------
    dict
        Structured result or structured error.
    """
    try:
        if tool_name == "inventory_lookup":
            return _handle_lookup(tool_input)
        elif tool_name == "inventory_search":
            return _handle_search(tool_input)
        elif tool_name == "inventory_low_stock":
            return _handle_low_stock(tool_input)
        else:
            return invalid_input(f"Unknown tool: '{tool_name}'")
    except Exception as exc:
        return internal_error(f"Tool execution failed: {exc}")


def _handle_lookup(tool_input: dict) -> dict:
    """Handle inventory_lookup tool call."""
    sku = tool_input.get("sku", "").strip()
    if not sku:
        return invalid_input("Parameter 'sku' is required and must not be empty")

    result = lookup_by_sku(sku)
    if result is None:
        return not_found(sku)

    return {"product": result}


def _handle_search(tool_input: dict) -> dict:
    """Handle inventory_search tool call."""
    query = tool_input.get("query", "").strip()
    if not query:
        return invalid_input("Parameter 'query' is required and must not be empty")

    results = search_by_name(query)
    return {"products": results, "count": len(results)}


def _handle_low_stock(tool_input: dict) -> dict:
    """Handle inventory_low_stock tool call."""
    results = list_low_stock()
    return {"products": results, "count": len(results)}


# ---------------------------------------------------------------------------
# Mock agent loop — simulates what the Anthropic API tool_use flow does
# ---------------------------------------------------------------------------

def run_agent_query(query: str) -> dict:
    """
    Simulate a single tool_use agent loop:
      1. Agent receives user query
      2. Agent decides which tool to call (keyword matching in mock)
      3. Tool executor runs and returns result
      4. Agent formats final response

    Returns a dict with: query, tool_called, tool_input, tool_result, response
    """
    # Step 1: Mock tool selection (in live mode, the model would decide)
    tool_name, tool_input = _mock_tool_selection(query)

    # Step 2: Execute the tool
    tool_result = execute_tool(tool_name, tool_input)

    # Step 3: Format response
    if is_error(tool_result):
        err = tool_result["error"]
        response = (
            f"I couldn't complete that request. "
            f"{err['description']} "
            f"(Category: {err['category']}, Retryable: {err['retryable']})"
        )
    else:
        response = _format_result(tool_name, tool_result)

    return {
        "query": query,
        "tool_called": tool_name,
        "tool_input": tool_input,
        "tool_result": tool_result,
        "response": response,
    }


def _mock_tool_selection(query: str) -> tuple[str, dict]:
    """
    Mock the model's tool selection based on keywords.

    In live mode, this would be the model's tool_use decision.
    """
    q = query.lower()

    if "low stock" in q or "reorder" in q or "running low" in q:
        return "inventory_low_stock", {}

    # Check for SKU pattern
    import re
    sku_match = re.search(r"SKU-\d{3}", query, re.IGNORECASE)
    if sku_match:
        return "inventory_lookup", {"sku": sku_match.group(0)}

    # Check for "look up" + SKU-like reference
    if "look up" in q or "lookup" in q:
        # Extract the next word as potential identifier
        return "inventory_lookup", {"sku": _extract_sku_from_query(query)}

    # Default to search
    search_term = _extract_search_term(query)
    return "inventory_search", {"query": search_term}


def _extract_sku_from_query(query: str) -> str:
    """Extract a SKU from a query string."""
    import re
    match = re.search(r"SKU-\d{3}", query, re.IGNORECASE)
    if match:
        return match.group(0)
    # Fallback: return a default that will produce a not_found error
    return query.split()[-1] if query.split() else ""


def _extract_search_term(query: str) -> str:
    """Extract the most likely search term from a natural language query."""
    # Remove common question words
    stopwords = {
        "do", "you", "have", "any", "what", "is", "the", "a", "an", "in",
        "stock", "for", "me", "find", "search", "show", "list", "about",
        "tell", "can", "i", "get", "how", "many", "much", "does", "our",
        "we", "inventory", "product", "products", "item", "items",
    }
    words = [w for w in query.lower().split() if w.strip("?.,!") not in stopwords]
    return " ".join(words) if words else query


def _format_result(tool_name: str, result: dict) -> str:
    """Format a successful tool result as a human-readable response."""
    if tool_name == "inventory_lookup":
        p = result["product"]
        reorder_flag = " ⚠️ NEEDS REORDER" if p["needs_reorder"] else ""
        return (
            f"{p['name']} ({p['sku']}): ${p['price']:.2f}, "
            f"{p['stock']} in stock at {p['warehouse']}{reorder_flag}"
        )

    elif tool_name == "inventory_search":
        count = result["count"]
        if count == 0:
            return "No matching products found."
        products = result["products"]
        lines = [f"Found {count} product(s):"]
        for p in products:
            lines.append(f"  • {p['name']} ({p['sku']}): ${p['price']:.2f}, {p['stock']} in stock")
        return "\n".join(lines)

    elif tool_name == "inventory_low_stock":
        count = result["count"]
        if count == 0:
            return "All products are above their reorder points."
        products = result["products"]
        lines = [f"{count} product(s) need reordering:"]
        for p in products:
            lines.append(
                f"  • {p['name']} ({p['sku']}): {p['stock']} left "
                f"(reorder at {p['reorder_point']})"
            )
        return "\n".join(lines)

    return json.dumps(result, indent=2)
