"""
inventory_data.py — Shared product inventory database.

All three implementations (custom tool, skill, MCP server) use this same
data layer so results are guaranteed identical.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    category: str
    price: float
    stock: int
    warehouse: str
    reorder_point: int

    @property
    def needs_reorder(self) -> bool:
        return self.stock <= self.reorder_point

    def to_dict(self) -> dict:
        d = asdict(self)
        d["needs_reorder"] = self.needs_reorder
        return d


# ---------------------------------------------------------------------------
# Inventory: 15 products across 3 categories
# ---------------------------------------------------------------------------

INVENTORY: dict[str, Product] = {}

_raw = [
    # Electronics
    ("SKU-001", "USB-C Hub 7-Port",          "electronics",      49.99,  142, "warehouse-east",  50),
    ("SKU-002", "Wireless Mouse Ergonomic",   "electronics",      34.99,  287, "warehouse-west",  75),
    ("SKU-003", "Mechanical Keyboard TKL",    "electronics",      89.99,   18, "warehouse-east",  25),
    ("SKU-004", "27\" 4K Monitor",            "electronics",     399.99,   53, "warehouse-central", 20),
    ("SKU-005", "Webcam 1080p",               "electronics",      59.99,    8, "warehouse-west",  30),

    # Office Supplies
    ("SKU-101", "A4 Copy Paper 5-Ream",       "office_supplies",  24.99, 512, "warehouse-central", 100),
    ("SKU-102", "Ballpoint Pens 50-Pack",     "office_supplies",  12.99, 834, "warehouse-east",   200),
    ("SKU-103", "Sticky Notes Assorted",      "office_supplies",   8.49,  45, "warehouse-west",    60),
    ("SKU-104", "Binder Clips Large 24-Pack", "office_supplies",   6.99, 156, "warehouse-east",    50),
    ("SKU-105", "Whiteboard Markers 12-Set",  "office_supplies",  14.99,  12, "warehouse-central",  40),

    # Furniture
    ("SKU-201", "Standing Desk Electric",     "furniture",       549.99,  11, "warehouse-central", 10),
    ("SKU-202", "Ergonomic Office Chair",     "furniture",       349.99,  27, "warehouse-west",    15),
    ("SKU-203", "Monitor Arm Dual",           "furniture",        79.99,  63, "warehouse-east",    20),
    ("SKU-204", "Filing Cabinet 3-Drawer",    "furniture",       129.99,   3, "warehouse-central", 10),
    ("SKU-205", "Desk Lamp LED",              "furniture",        44.99,  91, "warehouse-west",    25),
]

for row in _raw:
    p = Product(*row)
    INVENTORY[p.sku] = p


# ---------------------------------------------------------------------------
# Query functions
# ---------------------------------------------------------------------------

def lookup_by_sku(sku: str) -> Optional[dict]:
    """Look up a single product by SKU. Returns product dict or None."""
    product = INVENTORY.get(sku.upper().strip())
    if product is None:
        return None
    return product.to_dict()


def search_by_name(query: str) -> list[dict]:
    """Search products by name (case-insensitive substring match)."""
    query_lower = query.lower().strip()
    if not query_lower:
        return []
    return [
        p.to_dict() for p in INVENTORY.values()
        if query_lower in p.name.lower()
    ]


def list_low_stock() -> list[dict]:
    """List all products at or below their reorder point."""
    return [
        p.to_dict() for p in INVENTORY.values()
        if p.needs_reorder
    ]


def get_category_summary() -> dict:
    """Return per-category summary: count, total stock, total value."""
    categories: dict[str, dict] = {}
    for p in INVENTORY.values():
        if p.category not in categories:
            categories[p.category] = {
                "category": p.category,
                "product_count": 0,
                "total_stock": 0,
                "total_inventory_value": 0.0,
            }
        cat = categories[p.category]
        cat["product_count"] += 1
        cat["total_stock"] += p.stock
        cat["total_inventory_value"] += round(p.price * p.stock, 2)

    # Round totals
    for cat in categories.values():
        cat["total_inventory_value"] = round(cat["total_inventory_value"], 2)

    return categories
