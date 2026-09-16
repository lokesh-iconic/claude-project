"""
server.py — MCP server exposing inventory tools, resources, and prompts.

Uses FastMCP to create a proper MCP server over stdio transport.
Exposes the same inventory operations as the custom tool and skill
implementations, using the same shared data and error model.

Run directly:
    python server.py
    # or via fastmcp:
    fastmcp run server.py

The server communicates via JSON-RPC over stdin/stdout.
"""

from __future__ import annotations

import json
import os
import sys

# Ensure parent packages are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inventory_data import (
    lookup_by_sku,
    search_by_name,
    list_low_stock,
    get_category_summary,
    INVENTORY,
)
from error_model import not_found, invalid_input, internal_error

try:
    from mcp.server.mcpserver import MCPServer as FastMCP
    HAS_MCP = True
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP
        HAS_MCP = True
    except ImportError:
        try:
            from fastmcp import FastMCP
            HAS_MCP = True
        except ImportError:
            HAS_MCP = False


if not HAS_MCP:
    print(
        json.dumps({
            "error": "MCP SDK not installed. Run: uv add mcp",
            "hint": "pip install mcp  OR  pip install fastmcp",
        }),
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Initialize the MCP server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="Inventory Server",
    instructions=(
        "This server provides access to an internal product inventory database. "
        "Use the tools to look up products by SKU, search by name, or check "
        "low-stock alerts. The inventory://catalog resource provides the full "
        "product catalog as read-only data."
    ),
)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def inventory_lookup(sku: str) -> str:
    """Look up a single product by its SKU code.

    Use this when you have a specific product identifier like 'SKU-001'.
    Returns full product details including stock level and reorder status.
    Returns a structured error if the SKU is not found.

    Args:
        sku: The product SKU code (e.g. 'SKU-001'). Case-insensitive.
    """
    if not sku or not sku.strip():
        return json.dumps(invalid_input("Parameter 'sku' is required and must not be empty"))

    result = lookup_by_sku(sku.strip())
    if result is None:
        return json.dumps(not_found(sku.strip()))

    return json.dumps({"product": result})


@mcp.tool()
def inventory_search(query: str) -> str:
    """Search for products by name using a text query.

    Use this when looking for products by name or description (e.g. 'keyboard',
    'monitor', 'desk') without knowing the SKU. Returns matching products.

    Args:
        query: Search term to match against product names. Case-insensitive.
    """
    if not query or not query.strip():
        return json.dumps(invalid_input("Parameter 'query' is required and must not be empty"))

    results = search_by_name(query.strip())
    return json.dumps({"products": results, "count": len(results)})


@mcp.tool()
def inventory_low_stock() -> str:
    """List all products at or below their reorder point.

    Use this to check stock alerts, reorder needs, or find products running low.
    Takes no parameters.
    """
    results = list_low_stock()
    return json.dumps({"products": results, "count": len(results)})


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

@mcp.resource("inventory://catalog")
def get_catalog() -> str:
    """Full product catalog — all 15 products with complete details.

    This read-only resource provides the entire inventory as a JSON document.
    Use this for broad queries or when you need the full picture.
    """
    catalog = [p.to_dict() for p in INVENTORY.values()]
    return json.dumps({
        "catalog": catalog,
        "total_products": len(catalog),
        "categories": get_category_summary(),
    }, indent=2)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

@mcp.prompt()
def inventory_check(question: str) -> str:
    """Pre-built prompt template for common inventory queries.

    Wraps the user's question with context about available tools and
    expected response format.

    Args:
        question: The user's inventory-related question.
    """
    return (
        f"You are an inventory management assistant. "
        f"Use the inventory_lookup, inventory_search, and inventory_low_stock tools "
        f"to answer the following question.\n\n"
        f"Question: {question}\n\n"
        f"Provide a clear, structured answer with specific numbers. "
        f"If a product needs reordering, flag it."
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
