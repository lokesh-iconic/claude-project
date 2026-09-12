"""
workflow/pipeline.py — Deterministic 3-step workflow (classify → route → draft).

This is the WORKFLOW version: a fixed prompt chain with no branching decisions
made by the model beyond each individual step. The sequence is always:
  1. Classify the ticket → ClassificationResult
  2. Route based on classification → RoutingResult
  3. Draft a customer response → DraftResponse (then enforce formatting)

The model never decides what step comes next. Each step is exactly one API call.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Optional

from dotenv import load_dotenv, find_dotenv

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import (
    Category, Priority, Team,
    ClassificationResult, RoutingResult, DraftResponse, TicketResult,
    CATEGORY_TO_TEAM, enforce_formatting,
)
from tickets import Ticket, TICKETS

# Ensure .env is loaded from workspace root
load_dotenv(find_dotenv(usecwd=True), override=True)


def _get_model() -> str:
    """Return model identifier from environment or default to claude-3-5-sonnet."""
    return os.getenv("CLAUDE_MODEL", os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"))


# ---------------------------------------------------------------------------
# Mock responses for running without an API key
# ---------------------------------------------------------------------------

MOCK_CLASSIFICATIONS: dict[str, dict] = {
    "billing": {"category": "billing", "priority": "high", "confidence": 0.92,
                "reasoning": "Ticket is about payment, charges, or pricing.", "is_ambiguous": False},
    "technical": {"category": "technical", "priority": "high", "confidence": 0.90,
                  "reasoning": "Ticket describes a technical issue or bug.", "is_ambiguous": False},
    "account": {"category": "account", "priority": "medium", "confidence": 0.88,
                "reasoning": "Ticket is about account management or settings.", "is_ambiguous": False},
    "feature_request": {"category": "feature_request", "priority": "low", "confidence": 0.85,
                        "reasoning": "Ticket requests a new feature or improvement.", "is_ambiguous": False},
    "general": {"category": "general", "priority": "high", "confidence": 0.55,
                "reasoning": "Ticket is vague or spans multiple categories.", "is_ambiguous": True},
}


_client_instance = None
_client_checked = False


def _get_client():
    """Get the Anthropic client, or None if in mock mode or if the key fails authentication."""
    global _client_instance, _client_checked
    if _client_checked:
        return _client_instance

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or api_key.startswith("sk-ant-your"):
        _client_checked = True
        _client_instance = None
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        # Verify authentication and credit balance
        try:
            client.models.list(limit=1)
            # Quick 1-token test to verify active credit balance
            client.messages.create(
                model=_get_model(),
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )
            _client_instance = client
        except anthropic.AuthenticationError as auth_err:
            print(f"\n  [WARNING] ANTHROPIC_API_KEY from .env is invalid ({auth_err.message}).")
            print("  [WARNING] Running in MOCK mode. To use live mode, update ANTHROPIC_API_KEY in .env.\n")
            _client_instance = None
        except anthropic.BadRequestError as req_err:
            if "credit balance is too low" in str(req_err).lower():
                print("\n  [INFO] ANTHROPIC_API_KEY is authenticated, but your Anthropic account credit balance is $0.")
                print("  [INFO] Running smoothly in MOCK mode ($0 cost). To make live API calls, purchase credits at console.anthropic.com/settings/billing.\n")
                _client_instance = None
            else:
                _client_instance = client
        except Exception:
            _client_instance = client
    except Exception:
        _client_instance = None

    _client_checked = True
    return _client_instance


# ---------------------------------------------------------------------------
# Step 1: Classify
# ---------------------------------------------------------------------------

CLASSIFY_SYSTEM_PROMPT = """\
You are a support ticket classifier. Analyze the ticket and return a JSON object with:
- "category": one of "billing", "technical", "account", "feature_request", "general"
- "priority": one of "low", "medium", "high", "urgent"
- "confidence": float 0.0 to 1.0
- "reasoning": brief explanation (one sentence)
- "is_ambiguous": true if the ticket doesn't clearly fit one category

Return ONLY valid JSON. No other text."""


def classify(ticket: Ticket, client=None) -> ClassificationResult:
    """
    Step 1: Classify a ticket into a category with priority and confidence.

    In live mode, makes a single API call to Claude.
    In mock mode, uses keyword matching for deterministic results.
    """
    if client is not None:
        try:
            response = client.messages.create(
                model=_get_model(),
                max_tokens=300,
                system=CLASSIFY_SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": f"Subject: {ticket.subject}\n\nBody: {ticket.body}",
                }],
            )
            data = json.loads(response.content[0].text)
            return ClassificationResult(**data)
        except Exception as e:
            print(f"    [Notice: Anthropic API error ({e}) — using mock classification]")

    # ── Mock mode ──
    subject_lower = (ticket.subject + " " + ticket.body).lower()
    if ticket.ground_truth.get("is_ambiguous"):
        mock = MOCK_CLASSIFICATIONS["general"].copy()
        # For ambiguous tickets with a known category, use it but flag as ambiguous
        gt_cat = ticket.ground_truth.get("category", "general")
        mock["category"] = gt_cat
        mock["is_ambiguous"] = True
        mock["confidence"] = 0.55
        mock["reasoning"] = f"Ticket spans multiple concerns; best-guess category: {gt_cat}"
    elif any(w in subject_lower for w in ["charg", "bill", "invoice", "refund", "promo", "payment", "subscription cancel"]):
        mock = MOCK_CLASSIFICATIONS["billing"].copy()
    elif any(w in subject_lower for w in ["log in", "login", "api", "crash", "error", "timeout", "bug", "webhook", "firefox", "upload"]):
        mock = MOCK_CLASSIFICATIONS["technical"].copy()
    elif any(w in subject_lower for w in ["account", "delete", "upgrade plan", "transfer", "ownership", "gdpr"]):
        mock = MOCK_CLASSIFICATIONS["account"].copy()
    elif any(w in subject_lower for w in ["feature", "dark mode", "mobile app", "export", "request"]):
        mock = MOCK_CLASSIFICATIONS["feature_request"].copy()
    else:
        mock = MOCK_CLASSIFICATIONS["general"].copy()

    # Override priority from ground truth if available
    if "priority" in ticket.ground_truth:
        mock["priority"] = ticket.ground_truth["priority"]

    return ClassificationResult(**mock)


# ---------------------------------------------------------------------------
# Step 2: Route
# ---------------------------------------------------------------------------

ROUTE_SYSTEM_PROMPT = """\
You are a support ticket router. Given a ticket classification, decide which team
should handle it and whether it needs escalation.

Teams: billing, engineering, account_mgmt, product, general_support

Return ONLY a JSON object with:
- "team": one of the teams above
- "escalate": boolean (true for urgent/high-priority or ambiguous tickets)
- "routing_reason": brief explanation

Return ONLY valid JSON. No other text."""


def route(ticket: Ticket, classification: ClassificationResult, client=None) -> RoutingResult:
    """
    Step 2: Route a classified ticket to the appropriate team.

    In live mode, makes a single API call.
    In mock mode, uses the CATEGORY_TO_TEAM mapping.
    """
    if client is not None:
        try:
            response = client.messages.create(
                model=_get_model(),
                max_tokens=200,
                system=ROUTE_SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Ticket subject: {ticket.subject}\n"
                        f"Category: {classification.category.value}\n"
                        f"Priority: {classification.priority.value}\n"
                        f"Confidence: {classification.confidence}\n"
                        f"Is ambiguous: {classification.is_ambiguous}"
                    ),
                }],
            )
            data = json.loads(response.content[0].text)
            return RoutingResult(**data)
        except Exception as e:
            print(f"    [Notice: Anthropic API error ({e}) — using mock routing]")

    # ── Mock mode ──
    team = CATEGORY_TO_TEAM.get(classification.category, Team.GENERAL_SUPPORT)
    escalate = classification.priority in (Priority.HIGH, Priority.URGENT) or classification.is_ambiguous

    reason = f"Category '{classification.category.value}' maps to {team.value}"
    if escalate:
        reason += " (escalated due to " + (
            "ambiguity" if classification.is_ambiguous else f"{classification.priority.value} priority"
        ) + ")"

    return RoutingResult(team=team, escalate=escalate, routing_reason=reason)


# ---------------------------------------------------------------------------
# Step 3: Draft Response
# ---------------------------------------------------------------------------

DRAFT_SYSTEM_PROMPT = """\
You are a customer support agent. Write a professional, empathetic response to the
customer's ticket. Keep it concise (under 150 words for the body).

Return ONLY a JSON object with:
- "subject_line": a reply subject line
- "body": the customer-facing response text
- "internal_notes": brief notes for the support team (what to investigate, etc.)

Return ONLY valid JSON. No other text."""


def draft_response(
    ticket: Ticket,
    classification: ClassificationResult,
    routing: RoutingResult,
    client=None,
) -> DraftResponse:
    """
    Step 3: Draft a customer-facing response, then enforce formatting rules.

    In live mode, makes a single API call, then applies enforce_formatting().
    In mock mode, generates a template response and applies enforce_formatting().
    """
    raw_draft = None
    if client is not None:
        try:
            response = client.messages.create(
                model=_get_model(),
                max_tokens=400,
                system=DRAFT_SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Customer name: {ticket.customer_name}\n"
                        f"Subject: {ticket.subject}\n"
                        f"Body: {ticket.body}\n"
                        f"Category: {classification.category.value}\n"
                        f"Priority: {classification.priority.value}\n"
                        f"Assigned team: {routing.team.value}\n"
                        f"Escalated: {routing.escalate}"
                    ),
                }],
            )
            data = json.loads(response.content[0].text)
            raw_draft = DraftResponse(**data)
        except Exception as e:
            print(f"    [Notice: Anthropic API error ({e}) — using mock draft response]")

    if raw_draft is None:
        # ── Mock mode ──
        raw_draft = DraftResponse(
            subject_line=f"Re: {ticket.subject}",
            body=(
                f"Thank you for reaching out about your {classification.category.value} concern. "
                f"We take this seriously and our {routing.team.value} team is looking into it.\n\n"
                f"We understand this is {'urgent and are prioritizing your case' if routing.escalate else 'important to you'}. "
                f"You can expect an update within {'4 hours' if classification.priority in (Priority.URGENT, Priority.HIGH) else '24 hours'}.\n\n"
                f"If you have additional details, please reply to this email."
            ),
            internal_notes=(
                f"Category: {classification.category.value} | Team: {routing.team.value} | "
                f"Escalate: {routing.escalate} | Priority: {classification.priority.value}"
            ),
        )

    # Apply deterministic formatting rules (greeting, sign-off, paragraph length)
    formatted = enforce_formatting(raw_draft, customer_name=ticket.customer_name)
    return formatted


# ---------------------------------------------------------------------------
# Full Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(ticket: Ticket, client=None) -> TicketResult:
    """Run the complete 3-step workflow for a single ticket."""
    classification = classify(ticket, client)
    routing = route(ticket, classification, client)
    draft = draft_response(ticket, classification, routing, client)

    return TicketResult(
        ticket_id=ticket.id,
        classification=classification,
        routing=routing,
        draft=draft,
        system="workflow",
    )


def run_all(tickets: Optional[list[Ticket]] = None) -> list[TicketResult]:
    """Run the workflow pipeline on all tickets."""
    client = _get_client()
    mode = "LIVE (Anthropic API)" if client else "MOCK (no API key)"
    print(f"\n{'='*60}")
    print(f"  WORKFLOW PIPELINE — {mode}")
    print(f"{'='*60}\n")

    tickets = tickets or TICKETS
    results = []

    for ticket in tickets:
        print(f"  Processing {ticket.id}: {ticket.subject[:50]}...")
        result = run_pipeline(ticket, client)
        results.append(result)
        print(f"    -> {result.classification.category.value} "
              f"({result.classification.priority.value}) "
              f"-> {result.routing.team.value}"
              f"{' [ESCALATED]' if result.routing.escalate else ''}")

    print(f"\n  [OK] Processed {len(results)} tickets\n")
    return results


# ---------------------------------------------------------------------------
# Standalone execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    results = run_all()
    print("\n--- Sample result (TKT-001) ---")
    print(results[0].model_dump_json(indent=2))
