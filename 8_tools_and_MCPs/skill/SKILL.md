---
name: inventory-lookup
description: >
  Look up products in the internal inventory database by SKU, search by name,
  or list products that are below their reorder point. Use when you need to check
  stock levels, find product details, or identify items that need restocking.
---

# Inventory Lookup Skill

Query the internal product inventory database.

## Usage

Run the script with one of three commands:

```bash
# Look up a product by SKU
python scripts/inventory_skill.py lookup SKU-001

# Search products by name
python scripts/inventory_skill.py search "desk"

# List all products below reorder point
python scripts/inventory_skill.py low-stock
```

## Output

All commands output **structured JSON** to stdout:

### Successful lookup
```json
{
  "product": {
    "sku": "SKU-001",
    "name": "USB-C Hub 7-Port",
    "category": "electronics",
    "price": 49.99,
    "stock": 142,
    "warehouse": "warehouse-east",
    "reorder_point": 50,
    "needs_reorder": false
  }
}
```

### Error
```json
{
  "error": {
    "category": "not_found",
    "retryable": false,
    "description": "No product found with SKU 'SKU-999'"
  }
}
```

## Error Categories

| Category | Retryable | When |
|----------|-----------|------|
| `not_found` | No | SKU doesn't exist in inventory |
| `invalid_input` | No | Missing or empty required parameter |
| `internal_error` | Yes | Unexpected failure during execution |

## Notes

- SKU codes are case-insensitive (e.g., `sku-001` and `SKU-001` both work)
- Name search is a case-insensitive substring match
- The skill returns the same structured JSON as the custom tool and MCP server implementations
