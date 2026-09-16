"""
inventory_skill.py — Standalone CLI script for the Skill implementation.

This script is designed to be invoked by an agent via subprocess:
    python inventory_skill.py <command> [args...]

Commands:
    lookup <sku>       — Look up a product by SKU
    search <query>     — Search products by name
    low-stock          — List products at or below reorder point

All output is structured JSON to stdout.
Errors are returned in the same structured format.

Usage:
    python inventory_skill.py lookup SKU-001
    python inventory_skill.py search "desk"
    python inventory_skill.py low-stock
"""

from __future__ import annotations

import json
import os
import sys

# Ensure parent packages are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from inventory_data import lookup_by_sku, search_by_name, list_low_stock
from error_model import not_found, invalid_input, internal_error


def main() -> int:
    """Parse CLI args and execute the appropriate command."""
    args = sys.argv[1:]

    if not args:
        result = invalid_input(
            "No command provided. Usage: inventory_skill.py <lookup|search|low-stock> [args]"
        )
        print(json.dumps(result))
        return 1

    command = args[0].lower().strip()

    try:
        if command == "lookup":
            if len(args) < 2 or not args[1].strip():
                result = invalid_input("Usage: inventory_skill.py lookup <sku>")
            else:
                sku = args[1].strip()
                product = lookup_by_sku(sku)
                if product is None:
                    result = not_found(sku)
                else:
                    result = {"product": product}

        elif command == "search":
            if len(args) < 2 or not args[1].strip():
                result = invalid_input("Usage: inventory_skill.py search <query>")
            else:
                query = args[1].strip()
                products = search_by_name(query)
                result = {"products": products, "count": len(products)}

        elif command in ("low-stock", "low_stock", "lowstock"):
            products = list_low_stock()
            result = {"products": products, "count": len(products)}

        else:
            result = invalid_input(
                f"Unknown command: '{command}'. "
                "Valid commands: lookup, search, low-stock"
            )

    except Exception as exc:
        result = internal_error(f"Skill execution failed: {exc}")

    # Output structured JSON
    print(json.dumps(result))
    return 1 if "error" in result else 0


if __name__ == "__main__":
    sys.exit(main())
