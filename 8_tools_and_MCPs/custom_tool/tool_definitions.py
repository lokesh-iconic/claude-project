"""
tool_definitions.py — Anthropic tool_use JSON Schema definitions.

These are the tool schemas that would be passed to the Anthropic API in the
`tools` parameter. Each has a clear, differentiated description explaining
what it does and when to use it.
"""

from __future__ import annotations

TOOL_DEFINITIONS = [
    {
        "name": "inventory_lookup",
        "description": (
            "Look up a single product by its SKU (Stock Keeping Unit) code. "
            "Use this when you have a specific product identifier like 'SKU-001'. "
            "Returns full product details: name, category, price, stock level, "
            "warehouse location, and whether it needs reordering. "
            "Returns a structured error if the SKU is not found."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sku": {
                    "type": "string",
                    "description": (
                        "The product SKU code (e.g. 'SKU-001'). "
                        "Case-insensitive. Format: SKU-NNN."
                    ),
                },
            },
            "required": ["sku"],
        },
    },
    {
        "name": "inventory_search",
        "description": (
            "Search for products by name using a text query. "
            "Use this when the user asks about a product by name or description "
            "(e.g. 'keyboard', 'monitor', 'desk') but doesn't have the SKU. "
            "Returns a list of matching products. May return zero results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Search term to match against product names. "
                        "Case-insensitive substring match."
                    ),
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "inventory_low_stock",
        "description": (
            "List all products that are at or below their reorder point. "
            "Use this when the user asks about stock alerts, reorder needs, "
            "or wants to know which products are running low. "
            "Takes no parameters. Returns a list of products needing restock."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]
