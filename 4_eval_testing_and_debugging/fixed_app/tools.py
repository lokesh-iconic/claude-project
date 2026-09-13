"""
fixed_app/tools.py — Tool definitions with Bug 1 FIXED.

FIX: Restored `is_ambiguous` to read from args.get("is_ambiguous", False)
instead of being hardcoded to False. Ambiguous tickets now correctly
trigger escalation during routing.

DIFF FROM BROKEN VERSION:
    # broken:
    is_ambiguous = False
    # fixed:
    is_ambiguous = args.get("is_ambiguous", False)
"""

from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True), override=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import (
    Category, Priority, Team,
    ClassificationResult, RoutingResult, DraftResponse,
    CATEGORY_TO_TEAM,
)


def _get_model() -> str:
    return os.getenv("CLAUDE_MODEL", os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"))


# ---------------------------------------------------------------------------
# Tool Schemas
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "classify_ticket",
        "description": (
            "Classify a support ticket into a category and priority level. "
            "Use this to understand what the ticket is about before routing. "
            "Returns category, priority, confidence, reasoning, and whether "
            "the ticket is ambiguous."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "Unique ticket identifier"},
                "subject": {"type": "string", "description": "Ticket subject line"},
                "body": {"type": "string", "description": "Ticket body text"},
            },
            "required": ["ticket_id", "subject", "body"],
        },
    },
    {
        "name": "route_ticket",
        "description": (
            "Route a classified ticket to the appropriate support team. "
            "Should be called after classification. Can suggest escalation "
            "for high-priority or ambiguous tickets."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": [c.value for c in Category],
                    "description": "Ticket category from classification",
                },
                "priority": {
                    "type": "string",
                    "enum": [p.value for p in Priority],
                    "description": "Ticket priority from classification",
                },
                "is_ambiguous": {
                    "type": "boolean",
                    "description": "Whether the ticket was flagged as ambiguous",
                },
            },
            "required": ["category", "priority"],
        },
    },
    {
        "name": "draft_response",
        "description": (
            "Draft a customer-facing response to the ticket. Should be called "
            "after classification and routing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "Unique ticket identifier"},
                "customer_name": {"type": "string", "description": "Customer's name"},
                "category": {"type": "string", "description": "Ticket category"},
                "team": {"type": "string", "description": "Assigned support team"},
                "priority": {"type": "string", "description": "Ticket priority"},
                "ticket_subject": {"type": "string", "description": "Original ticket subject"},
                "ticket_body": {"type": "string", "description": "Original ticket body"},
            },
            "required": ["ticket_id", "customer_name", "category", "team", "ticket_subject", "ticket_body"],
        },
    },
    {
        "name": "escalate_to_specialist",
        "description": (
            "Delegate an ambiguous or complex ticket to a specialist subagent."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "Unique ticket identifier"},
                "subject": {"type": "string", "description": "Ticket subject line"},
                "body": {"type": "string", "description": "Ticket body text"},
                "initial_category": {"type": "string", "description": "Best-guess category"},
                "reason_for_escalation": {"type": "string", "description": "Why specialist review is needed"},
            },
            "required": ["ticket_id", "subject", "body", "reason_for_escalation"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool Execution Functions
# ---------------------------------------------------------------------------

def execute_classify_ticket(args: dict, client=None) -> dict:
    """Execute the classify_ticket tool."""
    if client is not None:
        try:
            response = client.messages.create(
                model=_get_model(),
                max_tokens=300,
                system=(
                    "You are a support ticket classifier. Analyze the ticket and return "
                    "a JSON object with: category (billing/technical/account/feature_request/general), "
                    "priority (low/medium/high/urgent), confidence (0-1 float), "
                    "reasoning (one sentence), is_ambiguous (boolean). "
                    "Return ONLY valid JSON."
                ),
                messages=[{
                    "role": "user",
                    "content": f"Subject: {args['subject']}\n\nBody: {args['body']}",
                }],
            )
            return json.loads(response.content[0].text)
        except Exception as e:
            print(f"    [Notice: classify API error ({e}) — mock fallback]")

    # Mock mode
    text = (args.get("subject", "") + " " + args.get("body", "")).lower()
    if any(w in text for w in ["nothing works", "frustrated", "broken", "nobody", "fwd:", "re: re:"]):
        return {"category": "general", "priority": "high", "confidence": 0.45,
                "reasoning": "Vague complaint spanning multiple areas", "is_ambiguous": True}
    elif any(w in text for w in ["billing", "charged", "invoice", "refund", "promo", "payment"]):
        return {"category": "billing", "priority": "high", "confidence": 0.88,
                "reasoning": "Payment or billing related concern", "is_ambiguous": False}
    elif any(w in text for w in ["login", "api", "crash", "error", "timeout", "webhook", "firefox"]):
        return {"category": "technical", "priority": "high", "confidence": 0.90,
                "reasoning": "Technical issue or bug report", "is_ambiguous": False}
    elif any(w in text for w in ["account", "delete", "gdpr", "upgrade", "transfer", "cancel"]):
        return {"category": "account", "priority": "medium", "confidence": 0.85,
                "reasoning": "Account management request", "is_ambiguous": False}
    elif any(w in text for w in ["feature", "dark mode", "mobile app", "export"]):
        return {"category": "feature_request", "priority": "low", "confidence": 0.87,
                "reasoning": "Feature request or product suggestion", "is_ambiguous": False}
    else:
        return {"category": "general", "priority": "medium", "confidence": 0.50,
                "reasoning": "Could not clearly categorize", "is_ambiguous": True}


def execute_route_ticket(args: dict, client=None) -> dict:
    """
    Execute the route_ticket tool — BUG 1 FIXED.

    FIX: is_ambiguous now reads from args instead of being hardcoded to False.
    """
    if client is not None:
        try:
            response = client.messages.create(
                model=_get_model(),
                max_tokens=200,
                system=(
                    "You are a ticket router. Given category and priority, assign a team "
                    "(billing/engineering/account_mgmt/product/general_support) and decide "
                    "if escalation is needed. Return JSON with: team, escalate (bool), routing_reason."
                ),
                messages=[{"role": "user", "content": json.dumps(args)}],
            )
            return json.loads(response.content[0].text)
        except Exception as e:
            print(f"    [Notice: route API error ({e}) — mock fallback]")

    # Mock mode — FIXED: is_ambiguous properly read from args
    cat = args.get("category", "general")
    priority = args.get("priority", "medium")
    is_ambiguous = args.get("is_ambiguous", False)  # ← FIX: was hardcoded to False

    team_map = {
        "billing": "billing", "technical": "engineering",
        "account": "account_mgmt", "feature_request": "product",
        "general": "general_support",
    }
    team = team_map.get(cat, "general_support")
    escalate = priority in ("high", "urgent") or is_ambiguous

    return {
        "team": team,
        "escalate": escalate,
        "routing_reason": f"Category '{cat}' -> {team}" + (" (escalated)" if escalate else ""),
    }


def execute_draft_response(args: dict, client=None) -> dict:
    """Execute the draft_response tool."""
    if client is not None:
        try:
            response = client.messages.create(
                model=_get_model(),
                max_tokens=400,
                system=(
                    "Write a professional, empathetic customer support response. "
                    "Keep it under 150 words. Return JSON with: subject_line, body, internal_notes."
                ),
                messages=[{
                    "role": "user",
                    "content": (
                        f"Customer: {args.get('customer_name', 'Customer')}\n"
                        f"Subject: {args.get('ticket_subject', '')}\n"
                        f"Body: {args.get('ticket_body', '')}\n"
                        f"Category: {args.get('category', '')}\n"
                        f"Team: {args.get('team', '')}"
                    ),
                }],
            )
            return json.loads(response.content[0].text)
        except Exception as e:
            print(f"    [Notice: draft API error ({e}) — mock fallback]")

    return {
        "subject_line": f"Re: {args.get('ticket_subject', 'Your ticket')}",
        "body": (
            f"Thank you for contacting us about this {args.get('category', '')} matter. "
            f"Our {args.get('team', 'support')} team has been assigned your case and "
            f"is actively investigating.\n\n"
            f"We understand the urgency and will keep you updated on progress. "
            f"Please don't hesitate to reply with any additional information."
        ),
        "internal_notes": (
            f"Agent-routed to {args.get('team', 'N/A')}. "
            f"Priority: {args.get('priority', 'N/A')}."
        ),
    }


TOOL_EXECUTORS = {
    "classify_ticket": execute_classify_ticket,
    "route_ticket": execute_route_ticket,
    "draft_response": execute_draft_response,
}
