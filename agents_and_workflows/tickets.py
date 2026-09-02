"""
tickets.py — 20 sample support tickets covering clear-cut and ambiguous cases.

Each ticket includes a ground_truth dict for evaluation:
  - category: the "correct" category
  - priority: the expected priority level
  - is_ambiguous: whether reasonable people (or models) might disagree
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Ticket:
    """A single support ticket."""
    id: str
    subject: str
    body: str
    customer_name: str
    ground_truth: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Clear-cut tickets (15)
# ---------------------------------------------------------------------------

TICKETS: list[Ticket] = [
    # ── Billing (4) ──────────────────────────────────────────────────────
    Ticket(
        id="TKT-001",
        subject="Double charged for my subscription",
        body=(
            "I was charged $29.99 twice on September 1st for my Pro plan. "
            "My bank statement shows two identical transactions. "
            "Please refund the duplicate charge as soon as possible."
        ),
        customer_name="Sarah Chen",
        ground_truth={"category": "billing", "priority": "high", "is_ambiguous": False},
    ),
    Ticket(
        id="TKT-002",
        subject="Promo code SAVE20 not working",
        body=(
            "I'm trying to apply the promo code SAVE20 at checkout but it says "
            "'invalid code'. The promotional email I received says it's valid "
            "until September 30th. Can you help me apply the discount?"
        ),
        customer_name="James Rodriguez",
        ground_truth={"category": "billing", "priority": "medium", "is_ambiguous": False},
    ),
    Ticket(
        id="TKT-003",
        subject="Request for invoice copy",
        body=(
            "Hi, I need a copy of my invoice from August 2025 for my company's "
            "expense report. My account email is m.patel@acmecorp.com. "
            "A PDF would be great."
        ),
        customer_name="Meera Patel",
        ground_truth={"category": "billing", "priority": "low", "is_ambiguous": False},
    ),
    Ticket(
        id="TKT-004",
        subject="Cancel subscription and get refund for unused portion",
        body=(
            "I'd like to cancel my annual subscription effective immediately. "
            "I've only used 3 months of my 12-month plan. Please process a "
            "pro-rated refund for the remaining 9 months to my original payment method."
        ),
        customer_name="Oliver Kim",
        ground_truth={"category": "billing", "priority": "high", "is_ambiguous": False},
    ),

    # ── Technical (5) ────────────────────────────────────────────────────
    Ticket(
        id="TKT-005",
        subject="Can't log in — password reset email never arrives",
        body=(
            "I've tried resetting my password four times. Each time it says "
            "'reset email sent' but nothing shows up in my inbox or spam. "
            "I've waited over an hour. My email is d.wright@email.com. "
            "I need access urgently for a deadline."
        ),
        customer_name="Diana Wright",
        ground_truth={"category": "technical", "priority": "urgent", "is_ambiguous": False},
    ),
    Ticket(
        id="TKT-006",
        subject="API returns 504 Gateway Timeout intermittently",
        body=(
            "Our integration is hitting your /v2/data endpoint and getting "
            "504 errors roughly 30% of the time since yesterday. We're sending "
            "about 200 req/min. Here's a sample request ID: req_8f3a2b. "
            "This is blocking our production pipeline."
        ),
        customer_name="Alex Tanaka",
        ground_truth={"category": "technical", "priority": "urgent", "is_ambiguous": False},
    ),
    Ticket(
        id="TKT-007",
        subject="Dashboard charts not loading on Firefox",
        body=(
            "The analytics dashboard loads fine on Chrome but the charts are "
            "blank on Firefox 118. I see console errors about 'canvas rendering "
            "context'. Other pages work. Screenshots attached."
        ),
        customer_name="Liam O'Brien",
        ground_truth={"category": "technical", "priority": "medium", "is_ambiguous": False},
    ),
    Ticket(
        id="TKT-008",
        subject="App crashes when uploading files over 50MB",
        body=(
            "Every time I try to upload a PDF larger than 50MB, the web app "
            "freezes for about 30 seconds, then shows a white screen. "
            "Smaller files work fine. Using Chrome 116 on Windows 11."
        ),
        customer_name="Nina Petrova",
        ground_truth={"category": "technical", "priority": "high", "is_ambiguous": False},
    ),
    Ticket(
        id="TKT-009",
        subject="Webhook payloads missing 'user_id' field",
        body=(
            "Since your v3.2 release, the webhook events for 'subscription.updated' "
            "no longer include the 'user_id' field in the payload. This was there "
            "in v3.1. Is this a breaking change or a bug? Our downstream systems "
            "depend on this field."
        ),
        customer_name="Raj Gupta",
        ground_truth={"category": "technical", "priority": "high", "is_ambiguous": False},
    ),

    # ── Account (3) ──────────────────────────────────────────────────────
    Ticket(
        id="TKT-010",
        subject="Please delete my account and all data",
        body=(
            "Under GDPR, I am requesting the complete deletion of my account "
            "and all associated personal data. My account email is "
            "h.mueller@protonmail.com. Please confirm once this is processed."
        ),
        customer_name="Hans Mueller",
        ground_truth={"category": "account", "priority": "high", "is_ambiguous": False},
    ),
    Ticket(
        id="TKT-011",
        subject="Upgrade from Basic to Enterprise plan",
        body=(
            "Our team has grown and we need to upgrade from the Basic plan to "
            "Enterprise. We currently have 12 seats and will need 50. "
            "Can you walk me through the upgrade process and pricing?"
        ),
        customer_name="Patricia Gomez",
        ground_truth={"category": "account", "priority": "medium", "is_ambiguous": False},
    ),
    Ticket(
        id="TKT-012",
        subject="Transfer account ownership to new admin",
        body=(
            "I'm leaving the company and need to transfer the account ownership "
            "to my colleague j.smith@company.com. What documentation or "
            "verification do you need to process this?"
        ),
        customer_name="Tom Anderson",
        ground_truth={"category": "account", "priority": "medium", "is_ambiguous": False},
    ),

    # ── Feature Request (3) ──────────────────────────────────────────────
    Ticket(
        id="TKT-013",
        subject="Feature request: Dark mode for the dashboard",
        body=(
            "I spend 8+ hours daily on your dashboard and the bright white "
            "background causes eye strain. A dark mode option would be amazing. "
            "Even a simple CSS inversion toggle would help."
        ),
        customer_name="Yuki Sato",
        ground_truth={"category": "feature_request", "priority": "low", "is_ambiguous": False},
    ),
    Ticket(
        id="TKT-014",
        subject="Bulk export for reports",
        body=(
            "Currently I have to export reports one at a time. When running "
            "monthly analytics across 30 projects, this takes forever. "
            "Could you add a 'select all and export as ZIP' option?"
        ),
        customer_name="Emma Johnson",
        ground_truth={"category": "feature_request", "priority": "low", "is_ambiguous": False},
    ),
    Ticket(
        id="TKT-015",
        subject="Mobile app please!",
        body=(
            "Any plans for a mobile app? I travel a lot and checking the "
            "dashboard on mobile Safari is painful — the responsive design "
            "doesn't quite work and I can't access half the features."
        ),
        customer_name="Carlos Rivera",
        ground_truth={"category": "feature_request", "priority": "low", "is_ambiguous": False},
    ),

    # ── Ambiguous (5) ────────────────────────────────────────────────────
    Ticket(
        id="TKT-016",
        subject="Nothing works",
        body=(
            "I'm really frustrated. Everything is broken. I can't do anything. "
            "Fix this ASAP. I'm paying good money for this service."
        ),
        customer_name="Mike Thompson",
        ground_truth={"category": "general", "priority": "high", "is_ambiguous": True},
    ),
    Ticket(
        id="TKT-017",
        subject="Billing issue or bug?",
        body=(
            "My usage dashboard shows I've used 500GB this month but my bill "
            "shows charges for 750GB. Either your billing is wrong or your "
            "usage tracker is wrong. Either way, I shouldn't be paying for "
            "250GB I didn't use. Please investigate."
        ),
        customer_name="Aisha Khan",
        ground_truth={"category": "billing", "priority": "high", "is_ambiguous": True},
    ),
    Ticket(
        id="TKT-018",
        subject="Re: Re: Fwd: problem",
        body=(
            "See below thread. I've been going back and forth with your team "
            "for two weeks. First they said it was a billing issue, then "
            "technical, now account. Nobody seems to know. Can someone who "
            "actually knows what they're doing look at this?"
        ),
        customer_name="Chris Walker",
        ground_truth={"category": "general", "priority": "urgent", "is_ambiguous": True},
    ),
    Ticket(
        id="TKT-019",
        subject="Quiero cancelar pero también necesito exportar datos",
        body=(
            "Necesito cancelar mi suscripción pero antes necesito exportar "
            "todos mis datos. ¿Cómo puedo hacer ambas cosas? También me "
            "gustaría saber si puedo reactivar la cuenta después. "
            "No estoy seguro si esto es un problema de cuenta o técnico."
        ),
        customer_name="Maria Lopez",
        ground_truth={"category": "account", "priority": "medium", "is_ambiguous": True},
    ),
    Ticket(
        id="TKT-020",
        subject="Great product but...",
        body=(
            "Love your product honestly! But here's the thing — I signed up for "
            "the annual plan, the payment went through, but my account still "
            "shows 'Free tier'. Also the onboarding tutorial video is a dead "
            "link. And while I have your attention, any chance of adding Slack "
            "integration? Thanks! 😊"
        ),
        customer_name="Jordan Blake",
        ground_truth={"category": "billing", "priority": "high", "is_ambiguous": True},
    ),
]
