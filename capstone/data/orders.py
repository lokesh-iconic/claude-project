"""
orders.py — Mock order and account database for the support assistant.

Provides 10 sample orders across 5 customer accounts with realistic data
for testing the lookup_order and lookup_account custom tools.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from typing import Optional


@dataclass(frozen=True)
class OrderItem:
    """A single item in an order."""
    name: str
    sku: str
    quantity: int
    unit_price: float

    @property
    def total(self) -> float:
        return round(self.quantity * self.unit_price, 2)


@dataclass(frozen=True)
class Order:
    """A customer order."""
    order_id: str
    customer_email: str
    status: str  # pending, processing, shipped, delivered, cancelled, refunded
    items: tuple[OrderItem, ...]
    order_date: str
    shipping_address: str
    tracking_number: Optional[str] = None
    estimated_delivery: Optional[str] = None
    notes: str = ""

    @property
    def total_amount(self) -> float:
        return round(sum(item.total for item in self.items), 2)

    def to_dict(self) -> dict:
        d = {
            "order_id": self.order_id,
            "customer_email": self.customer_email,
            "status": self.status,
            "items": [
                {
                    "name": item.name,
                    "sku": item.sku,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "total": item.total,
                }
                for item in self.items
            ],
            "total_amount": self.total_amount,
            "order_date": self.order_date,
            "shipping_address": self.shipping_address,
            "tracking_number": self.tracking_number,
            "estimated_delivery": self.estimated_delivery,
            "notes": self.notes,
        }
        return d


@dataclass(frozen=True)
class Account:
    """A customer account."""
    account_id: str
    email: str
    name: str
    plan: str  # free, basic, pro, enterprise
    status: str  # active, suspended, cancelled
    created_date: str
    billing_cycle: str  # monthly, annual
    next_billing_date: str
    payment_method: str  # ending in last 4 digits
    total_spent: float

    def to_dict(self) -> dict:
        return {
            "account_id": self.account_id,
            "email": self.email,
            "name": self.name,
            "plan": self.plan,
            "status": self.status,
            "created_date": self.created_date,
            "billing_cycle": self.billing_cycle,
            "next_billing_date": self.next_billing_date,
            "payment_method": self.payment_method,
            "total_spent": self.total_spent,
        }


# ---------------------------------------------------------------------------
# Mock Data
# ---------------------------------------------------------------------------

ORDERS: dict[str, Order] = {}
ACCOUNTS: dict[str, Account] = {}

_orders_raw = [
    Order(
        order_id="ORD-1001",
        customer_email="sarah.chen@email.com",
        status="delivered",
        items=(
            OrderItem("USB-C Hub 7-Port", "SKU-001", 1, 49.99),
            OrderItem("Wireless Mouse Ergonomic", "SKU-002", 2, 34.99),
        ),
        order_date="2025-08-15",
        shipping_address="123 Oak Street, Austin, TX 78701",
        tracking_number="1Z999AA10123456784",
        estimated_delivery="2025-08-20",
    ),
    Order(
        order_id="ORD-1002",
        customer_email="sarah.chen@email.com",
        status="shipped",
        items=(
            OrderItem("27\" 4K Monitor", "SKU-004", 1, 399.99),
        ),
        order_date="2025-09-10",
        shipping_address="123 Oak Street, Austin, TX 78701",
        tracking_number="1Z999AA10123456785",
        estimated_delivery="2025-09-18",
    ),
    Order(
        order_id="ORD-1003",
        customer_email="james.rodriguez@company.com",
        status="processing",
        items=(
            OrderItem("Mechanical Keyboard TKL", "SKU-003", 3, 89.99),
            OrderItem("Webcam 1080p", "SKU-005", 3, 59.99),
        ),
        order_date="2025-09-15",
        shipping_address="456 Elm Avenue, Seattle, WA 98101",
        notes="Bulk order for new hires",
    ),
    Order(
        order_id="ORD-1004",
        customer_email="james.rodriguez@company.com",
        status="cancelled",
        items=(
            OrderItem("Standing Desk Electric", "SKU-201", 1, 549.99),
        ),
        order_date="2025-08-20",
        shipping_address="456 Elm Avenue, Seattle, WA 98101",
        notes="Customer requested cancellation — changed office layout",
    ),
    Order(
        order_id="ORD-1005",
        customer_email="meera.patel@acmecorp.com",
        status="delivered",
        items=(
            OrderItem("A4 Copy Paper 5-Ream", "SKU-101", 10, 24.99),
            OrderItem("Ballpoint Pens 50-Pack", "SKU-102", 5, 12.99),
            OrderItem("Sticky Notes Assorted", "SKU-103", 10, 8.49),
        ),
        order_date="2025-07-01",
        shipping_address="789 Corporate Blvd, Chicago, IL 60601",
        tracking_number="1Z999AA10123456786",
        estimated_delivery="2025-07-08",
    ),
    Order(
        order_id="ORD-1006",
        customer_email="meera.patel@acmecorp.com",
        status="refunded",
        items=(
            OrderItem("Ergonomic Office Chair", "SKU-202", 2, 349.99),
        ),
        order_date="2025-08-01",
        shipping_address="789 Corporate Blvd, Chicago, IL 60601",
        notes="Chairs arrived with damaged armrests — full refund processed",
    ),
    Order(
        order_id="ORD-1007",
        customer_email="oliver.kim@startup.io",
        status="pending",
        items=(
            OrderItem("Standing Desk Electric", "SKU-201", 5, 549.99),
            OrderItem("Monitor Arm Dual", "SKU-203", 5, 79.99),
            OrderItem("Desk Lamp LED", "SKU-205", 5, 44.99),
        ),
        order_date="2025-09-18",
        shipping_address="321 Innovation Drive, San Francisco, CA 94102",
        notes="Enterprise order — awaiting PO approval",
    ),
    Order(
        order_id="ORD-1008",
        customer_email="oliver.kim@startup.io",
        status="delivered",
        items=(
            OrderItem("Whiteboard Markers 12-Set", "SKU-105", 4, 14.99),
        ),
        order_date="2025-08-25",
        shipping_address="321 Innovation Drive, San Francisco, CA 94102",
        tracking_number="1Z999AA10123456787",
        estimated_delivery="2025-08-30",
    ),
    Order(
        order_id="ORD-1009",
        customer_email="diana.wright@email.com",
        status="shipped",
        items=(
            OrderItem("Filing Cabinet 3-Drawer", "SKU-204", 1, 129.99),
            OrderItem("Binder Clips Large 24-Pack", "SKU-104", 3, 6.99),
        ),
        order_date="2025-09-12",
        shipping_address="555 Main Street, Denver, CO 80202",
        tracking_number="1Z999AA10123456788",
        estimated_delivery="2025-09-19",
    ),
    Order(
        order_id="ORD-1010",
        customer_email="diana.wright@email.com",
        status="processing",
        items=(
            OrderItem("USB-C Hub 7-Port", "SKU-001", 1, 49.99),
            OrderItem("Mechanical Keyboard TKL", "SKU-003", 1, 89.99),
        ),
        order_date="2025-09-17",
        shipping_address="555 Main Street, Denver, CO 80202",
    ),
]

_accounts_raw = [
    Account(
        account_id="ACC-2001",
        email="sarah.chen@email.com",
        name="Sarah Chen",
        plan="pro",
        status="active",
        created_date="2024-03-15",
        billing_cycle="monthly",
        next_billing_date="2025-10-15",
        payment_method="Visa ending in 4242",
        total_spent=1249.87,
    ),
    Account(
        account_id="ACC-2002",
        email="james.rodriguez@company.com",
        name="James Rodriguez",
        plan="enterprise",
        status="active",
        created_date="2024-01-10",
        billing_cycle="annual",
        next_billing_date="2026-01-10",
        payment_method="Corporate PO #8834",
        total_spent=8750.00,
    ),
    Account(
        account_id="ACC-2003",
        email="meera.patel@acmecorp.com",
        name="Meera Patel",
        plan="enterprise",
        status="active",
        created_date="2023-06-01",
        billing_cycle="annual",
        next_billing_date="2025-06-01",
        payment_method="Corporate PO #6621",
        total_spent=15430.50,
    ),
    Account(
        account_id="ACC-2004",
        email="oliver.kim@startup.io",
        name="Oliver Kim",
        plan="basic",
        status="active",
        created_date="2025-05-20",
        billing_cycle="monthly",
        next_billing_date="2025-10-20",
        payment_method="Mastercard ending in 5555",
        total_spent=329.90,
    ),
    Account(
        account_id="ACC-2005",
        email="diana.wright@email.com",
        name="Diana Wright",
        plan="pro",
        status="active",
        created_date="2024-11-01",
        billing_cycle="monthly",
        next_billing_date="2025-10-01",
        payment_method="Visa ending in 1234",
        total_spent=876.45,
    ),
]

# Build lookup dicts
for order in _orders_raw:
    ORDERS[order.order_id] = order

for account in _accounts_raw:
    ACCOUNTS[account.account_id] = account


# ---------------------------------------------------------------------------
# Query Functions
# ---------------------------------------------------------------------------

def lookup_order(order_id: str) -> Optional[dict]:
    """Look up an order by ID. Returns order dict or None."""
    order = ORDERS.get(order_id.upper().strip())
    if order is None:
        return None
    return order.to_dict()


def lookup_account_by_email(email: str) -> Optional[dict]:
    """Look up an account by email. Returns account dict or None."""
    email_lower = email.lower().strip()
    for account in ACCOUNTS.values():
        if account.email.lower() == email_lower:
            return account.to_dict()
    return None


def lookup_account_by_id(account_id: str) -> Optional[dict]:
    """Look up an account by account ID. Returns account dict or None."""
    account = ACCOUNTS.get(account_id.upper().strip())
    if account is None:
        return None
    return account.to_dict()


def get_orders_for_email(email: str) -> list[dict]:
    """Get all orders for a customer email."""
    email_lower = email.lower().strip()
    return [
        order.to_dict()
        for order in ORDERS.values()
        if order.customer_email.lower() == email_lower
    ]
