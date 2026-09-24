"""
agent/tools.py — Custom tool definitions for the support assistant.

WHY CUSTOM TOOLS (not MCP) FOR ORDER/ACCOUNT LOOKUP?
======================================================
Order and account lookups are tightly coupled to the agent loop:
  - Per-request, user-specific data (not shared reference data)
  - Structured error handling (not_found → specific user-facing message)
  - The agent needs the result immediately in the same conversation turn

Compare to the knowledge base, which is a shared, read-only reference
data source — better served by MCP's resource/tool model.

Tool definitions follow Anthropic's tool_use JSON Schema format.
"""

from __future__ import annotations

import json
import os
import sys

# Ensure imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from capstone.data.orders import (
    lookup_order,
    lookup_account_by_email,
    lookup_account_by_id,
    get_orders_for_email,
)
from capstone.data.knowledge_base import search_articles


# ---------------------------------------------------------------------------
# Tool Schemas (Anthropic tool_use format)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "lookup_order",
        "description": (
            "Look up a customer order by its order ID (e.g. 'ORD-1001'). "
            "Returns order details including status, items, shipping address, "
            "tracking number, and estimated delivery. "
            "Use this when a customer asks about their order status or details."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The order ID (e.g. 'ORD-1001'). Case-insensitive.",
                },
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "lookup_account",
        "description": (
            "Look up a customer account by email address or account ID. "
            "Returns account details including plan, status, billing info, "
            "and payment method. Use this when a customer asks about their "
            "account, subscription, or billing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "identifier": {
                    "type": "string",
                    "description": (
                        "Customer email (e.g. 'sarah@email.com') or account ID "
                        "(e.g. 'ACC-2001')."
                    ),
                },
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "search_knowledge_base",
        "description": (
            "Search the product knowledge base / FAQ for answers to common questions. "
            "Covers: shipping, returns, billing, product info, and account management. "
            "Use this when a customer asks a general question not specific to their order/account."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term (e.g. 'return policy', 'shipping times', 'warranty').",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": (
            "Escalate an unresolvable issue to a human support agent. "
            "Creates a structured escalation ticket. Use this when: "
            "(1) the customer's issue cannot be resolved with available tools, "
            "(2) the customer explicitly requests a human agent, or "
            "(3) the issue involves a complaint that needs manager review."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why the issue is being escalated.",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "urgent"],
                    "description": "Priority level for the escalation.",
                },
                "customer_summary": {
                    "type": "string",
                    "description": "Brief summary of the customer's issue for the human agent.",
                },
                "attempted_resolution": {
                    "type": "string",
                    "description": "What was tried before escalating.",
                },
            },
            "required": ["reason", "priority", "customer_summary"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool Executors
# ---------------------------------------------------------------------------

def execute_lookup_order(args: dict) -> dict:
    """Execute the lookup_order tool."""
    order_id = args.get("order_id", "").strip()
    if not order_id:
        return {"error": "order_id is required", "error_type": "invalid_input"}

    result = lookup_order(order_id)
    if result is None:
        return {
            "error": f"Order '{order_id}' not found",
            "error_type": "not_found",
            "suggestion": "Please verify the order ID and try again. Order IDs look like 'ORD-1001'.",
        }

    return {"order": result}


def execute_lookup_account(args: dict) -> dict:
    """Execute the lookup_account tool."""
    identifier = args.get("identifier", "").strip()
    if not identifier:
        return {"error": "identifier is required", "error_type": "invalid_input"}

    # Try as account ID first, then as email
    if identifier.upper().startswith("ACC-"):
        result = lookup_account_by_id(identifier)
    else:
        result = lookup_account_by_email(identifier)

    if result is None:
        return {
            "error": f"Account '{identifier}' not found",
            "error_type": "not_found",
            "suggestion": "Please verify the email or account ID.",
        }

    # Also fetch their orders
    orders = get_orders_for_email(result["email"])
    result["recent_orders"] = orders[:3]  # Include last 3 orders
    result["total_orders"] = len(orders)

    return {"account": result}


def execute_search_knowledge_base(args: dict) -> dict:
    """Execute the search_knowledge_base tool."""
    query = args.get("query", "").strip()
    if not query:
        return {"error": "query is required", "error_type": "invalid_input"}

    results = search_articles(query)
    return {"articles": results, "count": len(results)}


def execute_escalate_to_human(args: dict) -> dict:
    """Execute the escalate_to_human tool — creates a structured escalation ticket."""
    import time

    ticket_id = f"ESC-{int(time.time()) % 100000:05d}"

    return {
        "escalation_ticket": {
            "ticket_id": ticket_id,
            "status": "created",
            "priority": args.get("priority", "medium"),
            "reason": args.get("reason", ""),
            "customer_summary": args.get("customer_summary", ""),
            "attempted_resolution": args.get("attempted_resolution", "None recorded"),
            "assigned_to": "Support Queue",
            "estimated_response_time": "2-4 hours" if args.get("priority") == "urgent" else "24 hours",
        },
        "message_to_customer": (
            f"I've created escalation ticket {ticket_id} for you. "
            f"A human support agent will review your case "
            f"within {('2-4 hours' if args.get('priority') == 'urgent' else '24 hours')}."
        ),
    }


# Tool name → executor mapping
TOOL_EXECUTORS = {
    "lookup_order": execute_lookup_order,
    "lookup_account": execute_lookup_account,
    "search_knowledge_base": execute_search_knowledge_base,
    "escalate_to_human": execute_escalate_to_human,
}
