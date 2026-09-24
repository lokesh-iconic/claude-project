"""
knowledge_base.py — Product FAQ and knowledge base for the support assistant.

15 FAQ entries covering common support questions. This data is served via
the MCP server (Domain 8) — a different capability from the custom tool
(order lookup), justifying the different integration approach.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class KBArticle:
    """A knowledge base article."""
    article_id: str
    title: str
    category: str  # shipping, returns, billing, product, account, general
    content: str
    tags: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "article_id": self.article_id,
            "title": self.title,
            "category": self.category,
            "content": self.content,
            "tags": list(self.tags),
        }


# ---------------------------------------------------------------------------
# Knowledge Base Articles
# ---------------------------------------------------------------------------

ARTICLES: dict[str, KBArticle] = {}

_articles_raw = [
    # Shipping (3)
    KBArticle(
        article_id="KB-001",
        title="Shipping Times and Methods",
        category="shipping",
        content=(
            "We offer three shipping methods: Standard (5-7 business days, free on orders over $50), "
            "Express (2-3 business days, $9.99), and Overnight (next business day, $24.99). "
            "All orders are processed within 1-2 business days before shipping. "
            "Tracking numbers are emailed once the order ships. "
            "We ship to all 50 US states. International shipping is not available at this time."
        ),
        tags=("shipping", "delivery", "tracking", "methods"),
    ),
    KBArticle(
        article_id="KB-002",
        title="Order Tracking",
        category="shipping",
        content=(
            "Once your order ships, you'll receive a tracking number via email. "
            "You can track your package at our website or directly on the carrier's site. "
            "If you haven't received a tracking number within 3 business days of ordering, "
            "please contact support with your order ID. "
            "Note: tracking information may take 24 hours to update after initial shipment."
        ),
        tags=("tracking", "shipping", "order status"),
    ),
    KBArticle(
        article_id="KB-003",
        title="Shipping to PO Boxes",
        category="shipping",
        content=(
            "Standard shipping can deliver to PO Boxes via USPS. Express and Overnight "
            "shipping require a physical street address as they use UPS/FedEx. "
            "If you provide a PO Box with Express/Overnight, we will automatically "
            "downgrade to Standard shipping and refund the shipping cost difference."
        ),
        tags=("shipping", "PO box", "address"),
    ),

    # Returns (3)
    KBArticle(
        article_id="KB-004",
        title="Return Policy",
        category="returns",
        content=(
            "We accept returns within 30 days of delivery for a full refund. "
            "Items must be in original packaging and unused condition. "
            "Electronics must include all accessories and original box. "
            "Furniture items have a 14-day return window due to shipping costs. "
            "To start a return, contact support with your order ID and reason for return."
        ),
        tags=("returns", "refund", "policy", "exchange"),
    ),
    KBArticle(
        article_id="KB-005",
        title="Refund Processing Times",
        category="returns",
        content=(
            "Refunds are processed within 3-5 business days after we receive the returned item. "
            "Credit card refunds take an additional 5-10 business days to appear on your statement. "
            "Corporate PO refunds are applied as credit to your next invoice. "
            "You'll receive an email confirmation when your refund is processed."
        ),
        tags=("refund", "processing", "timeline", "credit"),
    ),
    KBArticle(
        article_id="KB-006",
        title="Damaged Items",
        category="returns",
        content=(
            "If your item arrived damaged, please contact support within 48 hours of delivery. "
            "Include photos of the damage and your order ID. We will either send a replacement "
            "at no charge or issue a full refund including original shipping costs. "
            "Do not discard the damaged item or packaging until instructed by our team."
        ),
        tags=("damaged", "replacement", "defective", "broken"),
    ),

    # Billing (3)
    KBArticle(
        article_id="KB-007",
        title="Payment Methods",
        category="billing",
        content=(
            "We accept Visa, Mastercard, American Express, and Discover credit/debit cards. "
            "Enterprise customers can use corporate Purchase Orders (POs) with Net-30 terms. "
            "We do not accept PayPal, cryptocurrency, or cash on delivery. "
            "All prices are in USD. Sales tax is calculated based on the shipping address."
        ),
        tags=("payment", "credit card", "billing", "PO"),
    ),
    KBArticle(
        article_id="KB-008",
        title="Subscription Plans",
        category="billing",
        content=(
            "We offer four plans: Free (limited catalog access), Basic ($9.99/month), "
            "Pro ($29.99/month with priority support and bulk discounts), and Enterprise "
            "(custom pricing with dedicated account manager). Annual billing saves 20%. "
            "You can upgrade or downgrade at any time — changes take effect at the next billing cycle. "
            "Downgrades to Free require cancelling all active subscriptions first."
        ),
        tags=("plans", "subscription", "pricing", "upgrade", "downgrade"),
    ),
    KBArticle(
        article_id="KB-009",
        title="Invoice and Receipt Requests",
        category="billing",
        content=(
            "Invoices are automatically emailed after each purchase. You can also download "
            "invoices from your account dashboard under Billing > Invoice History. "
            "For custom invoice formats or W-9 requests, contact support with your account ID. "
            "Enterprise customers receive consolidated monthly invoices by default."
        ),
        tags=("invoice", "receipt", "billing history", "W-9"),
    ),

    # Product (3)
    KBArticle(
        article_id="KB-010",
        title="Product Warranty",
        category="product",
        content=(
            "All electronics carry a 1-year manufacturer's warranty covering defects in materials "
            "and workmanship. Furniture items have a 2-year warranty. Office supplies are not warrantied. "
            "Warranty claims require proof of purchase (order ID or receipt). "
            "Warranty does not cover damage from misuse, accidents, or unauthorized modifications."
        ),
        tags=("warranty", "guarantee", "defect", "coverage"),
    ),
    KBArticle(
        article_id="KB-011",
        title="Product Compatibility",
        category="product",
        content=(
            "Our USB-C hubs are compatible with all USB-C devices including MacBook, Windows laptops, "
            "and tablets. The 4K monitors support HDMI 2.1, DisplayPort 1.4, and USB-C input. "
            "Mechanical keyboards use USB-A or USB-C connection (cable included). "
            "Monitor arms support VESA 75x75 and 100x100 mounting patterns, up to 27 inches."
        ),
        tags=("compatibility", "specs", "USB-C", "VESA", "connection"),
    ),
    KBArticle(
        article_id="KB-012",
        title="Bulk and Enterprise Orders",
        category="product",
        content=(
            "Orders of 10+ units qualify for bulk pricing (10-15% discount depending on product). "
            "Enterprise customers get dedicated account managers and custom pricing. "
            "Bulk orders over $5,000 qualify for free Express shipping. "
            "Contact our sales team at sales@company.com for custom quotes."
        ),
        tags=("bulk", "enterprise", "discount", "wholesale"),
    ),

    # Account (3)
    KBArticle(
        article_id="KB-013",
        title="Account Security",
        category="account",
        content=(
            "We recommend enabling two-factor authentication (2FA) on your account. "
            "You can enable 2FA from Account Settings > Security. We support authenticator apps "
            "(Google Authenticator, Authy) and SMS codes. "
            "If you suspect unauthorized access, change your password immediately and contact support. "
            "We will never ask for your password via email or chat."
        ),
        tags=("security", "2FA", "password", "unauthorized access"),
    ),
    KBArticle(
        article_id="KB-014",
        title="Data Privacy and GDPR",
        category="account",
        content=(
            "We comply with GDPR, CCPA, and other applicable data privacy regulations. "
            "You can request a copy of your personal data or account deletion from "
            "Account Settings > Privacy. Data deletion requests are processed within 30 days. "
            "Deleted accounts cannot be recovered. Please download any needed data before requesting deletion."
        ),
        tags=("privacy", "GDPR", "CCPA", "data deletion", "data export"),
    ),
    KBArticle(
        article_id="KB-015",
        title="Account Transfer",
        category="account",
        content=(
            "Account ownership can be transferred to another person within your organization. "
            "Both the current and new owner must verify their identity. "
            "Submit a transfer request through Account Settings > Transfer Ownership, "
            "or contact support with both email addresses. "
            "Transfer processing takes 2-3 business days."
        ),
        tags=("transfer", "ownership", "admin", "change owner"),
    ),
]

# Build lookup dict
for article in _articles_raw:
    ARTICLES[article.article_id] = article


# ---------------------------------------------------------------------------
# Query Functions
# ---------------------------------------------------------------------------

def search_articles(query: str) -> list[dict]:
    """Search knowledge base articles by keyword (case-insensitive substring match)."""
    query_lower = query.lower().strip()
    if not query_lower:
        return []

    results = []
    for article in ARTICLES.values():
        # Search in title, content, and tags
        searchable = (
            article.title.lower()
            + " " + article.content.lower()
            + " " + " ".join(article.tags)
        )
        if query_lower in searchable:
            results.append(article.to_dict())

    return results


def get_article_by_id(article_id: str) -> Optional[dict]:
    """Get a specific article by ID."""
    article = ARTICLES.get(article_id.upper().strip())
    if article is None:
        return None
    return article.to_dict()


def list_articles_by_category(category: str) -> list[dict]:
    """List all articles in a category."""
    category_lower = category.lower().strip()
    return [
        article.to_dict()
        for article in ARTICLES.values()
        if article.category.lower() == category_lower
    ]


def get_all_articles() -> list[dict]:
    """Get all knowledge base articles."""
    return [article.to_dict() for article in ARTICLES.values()]
