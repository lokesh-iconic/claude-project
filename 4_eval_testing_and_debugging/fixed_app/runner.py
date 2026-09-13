"""
fixed_app/runner.py — Agent runner with Bug 2 FIXED.

FIX: Restored explicit priority rubric in AGENT_SYSTEM_PROMPT so the model
(and mock classifier) assigns priorities consistently:
  - URGENT: system down, data loss, security breach, deadline
  - HIGH:   money involved, blocking issue, compliance (GDPR)
  - MEDIUM: inconvenience, workaround available
  - LOW:    suggestion, feature request, non-blocking question

This is a PROMPT FIX, not a code fix — the correct layer for a model-output problem.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Optional

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True), override=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import (
    ClassificationResult, RoutingResult, DraftResponse, TicketResult,
    Category, Priority, Team,
)
from tickets import Ticket, TICKETS
from fixed_app.tools import TOOL_DEFINITIONS, TOOL_EXECUTORS, execute_classify_ticket, execute_route_ticket, execute_draft_response
from fixed_app.hooks import create_hooks, DraftFormattingHook
from fixed_app.subagent import run_specialist_classifier


def _get_model() -> str:
    return os.getenv("CLAUDE_MODEL", os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"))


# ---------------------------------------------------------------------------
# System Prompt — FIXED VERSION
#
# The explicit priority rubric ensures the model assigns priorities
# consistently based on clear, objective criteria.
# ---------------------------------------------------------------------------

AGENT_SYSTEM_PROMPT = """\
You are an intelligent support ticket triage agent. You have tools to classify,
route, and draft responses to customer support tickets.

Your process:
1. First, classify the ticket to understand its category and priority
2. If the classification confidence is LOW (< 0.7) or is_ambiguous is true,
   use escalate_to_specialist for a deeper analysis
3. Route the ticket to the appropriate team
4. Draft a professional customer response

## Priority Rubric (ALWAYS follow this):
- URGENT: System outage, data loss, security breach, or customer has a hard deadline
- HIGH:   Money involved (charges, refunds), blocking issue, compliance request (GDPR)
- MEDIUM: Inconvenience with a workaround, informational request, plan changes
- LOW:    Feature suggestion, product feedback, non-blocking question

You MAY deviate from the classify→route→draft order if the situation warrants it.

When you're done with ALL steps (classify, route, draft), provide a final
summary as plain text. Include the classification, routing, and confirm the
draft is ready.

Always process the COMPLETE pipeline. Do not stop after just classification."""


# ---------------------------------------------------------------------------
# Mock Agent Loop — FIXED
# ---------------------------------------------------------------------------

class MockAgentLoop:
    """
    Mock agent with CORRECT priority assignment (Bug 2 fixed).
    Uses the same priority heuristics as the original Domain 1 agent.
    """

    def __init__(self, hooks: dict):
        self.hooks = hooks
        self.tool_calls_log: list[dict] = []

    def process_ticket(self, ticket: Ticket) -> tuple[dict, dict, dict]:
        # Step 1: Classify — using the standard (correct) classifier
        classify_args = {
            "ticket_id": ticket.id,
            "subject": ticket.subject,
            "body": ticket.body,
        }
        classification = execute_classify_ticket(classify_args)
        self.tool_calls_log.append({"tool": "classify_ticket", "args": classify_args, "result": classification})

        # Step 2: Check if ambiguous → escalate to specialist
        if classification.get("is_ambiguous") or classification.get("confidence", 1.0) < 0.7:
            specialist_args = {
                "ticket_id": ticket.id,
                "subject": ticket.subject,
                "body": ticket.body,
                "initial_category": classification.get("category"),
                "reason_for_escalation": f"Confidence {classification.get('confidence', 0):.2f}, ambiguous={classification.get('is_ambiguous')}",
            }
            specialist_result = run_specialist_classifier(**specialist_args)
            self.tool_calls_log.append({"tool": "escalate_to_specialist", "args": specialist_args, "result": specialist_result})
            classification = specialist_result

        # Step 3: Route
        route_args = {
            "category": classification.get("category", "general"),
            "priority": classification.get("priority", "medium"),
            "is_ambiguous": classification.get("is_ambiguous", False),
        }
        routing = execute_route_ticket(route_args)
        self.tool_calls_log.append({"tool": "route_ticket", "args": route_args, "result": routing})

        # Step 4: Draft response
        draft_args = {
            "ticket_id": ticket.id,
            "customer_name": ticket.customer_name,
            "category": classification.get("category", "general"),
            "team": routing.get("team", "general_support"),
            "priority": classification.get("priority", "medium"),
            "ticket_subject": ticket.subject,
            "ticket_body": ticket.body,
        }
        draft = execute_draft_response(draft_args)
        self.tool_calls_log.append({"tool": "draft_response", "args": draft_args, "result": draft})

        # Step 5: Apply PostToolUse hook on draft
        post_hook = self.hooks.get("PostToolUse")
        if post_hook:
            draft = post_hook("draft_response", draft_args, draft)

        return classification, routing, draft


# ---------------------------------------------------------------------------
# Public Interface
# ---------------------------------------------------------------------------

_client_instance = None
_client_checked = False


def _get_client():
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
        try:
            client.models.list(limit=1)
            client.messages.create(
                model=os.getenv("CLAUDE_MODEL", os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")),
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )
            _client_instance = client
        except anthropic.AuthenticationError:
            _client_instance = None
        except anthropic.BadRequestError as req_err:
            if "credit balance is too low" in str(req_err).lower():
                _client_instance = None
            else:
                _client_instance = client
        except Exception:
            _client_instance = client
    except Exception:
        _client_instance = None

    _client_checked = True
    return _client_instance


def process_ticket(ticket: Ticket, client=None, hooks: dict | None = None) -> TicketResult:
    """Process a single ticket through the FIXED agent system."""
    if hooks is None:
        hooks = create_hooks()

    mock_agent = MockAgentLoop(hooks)
    classification, routing, draft = mock_agent.process_ticket(ticket)

    try:
        cls_result = ClassificationResult(**classification)
    except Exception:
        cls_result = ClassificationResult(
            category=Category(classification.get("category", "general")),
            priority=Priority(classification.get("priority", "medium")),
            confidence=classification.get("confidence", 0.5),
            reasoning=classification.get("reasoning", "Agent classification"),
            is_ambiguous=classification.get("is_ambiguous", False),
        )
    try:
        rt_result = RoutingResult(**routing)
    except Exception:
        rt_result = RoutingResult(
            team=Team(routing.get("team", "general_support")),
            escalate=routing.get("escalate", False),
            routing_reason=routing.get("routing_reason", "Agent routing"),
        )
    try:
        dr_result = DraftResponse(**draft)
    except Exception:
        dr_result = DraftResponse(
            subject_line=draft.get("subject_line", f"Re: {ticket.subject}"),
            body=draft.get("body", "We are looking into your issue."),
            internal_notes=draft.get("internal_notes", ""),
        )

    return TicketResult(
        ticket_id=ticket.id,
        classification=cls_result,
        routing=rt_result,
        draft=dr_result,
        system="agent-fixed",
    )


def run_all(tickets: Optional[list[Ticket]] = None) -> tuple[list[TicketResult], dict]:
    """Run the fixed agent system on all tickets."""
    hooks = create_hooks()

    print(f"\n{'='*60}")
    print(f"  FIXED AGENT SYSTEM — MOCK MODE")
    print(f"{'='*60}\n")

    tickets = tickets or TICKETS
    results = []

    for ticket in tickets:
        print(f"  Processing {ticket.id}: {ticket.subject[:50]}...")
        result = process_ticket(ticket, None, hooks)
        results.append(result)

        flags = []
        if result.classification.is_ambiguous:
            flags.append("AMBIGUOUS->SPECIALIST")
        if result.routing.escalate:
            flags.append("ESCALATED")

        flag_str = f" [{', '.join(flags)}]" if flags else ""
        print(f"    -> {result.classification.category.value} "
              f"({result.classification.priority.value}) "
              f"-> {result.routing.team.value}{flag_str}")

    post_hook = hooks.get("PostToolUse")
    hook_stats = post_hook.get_stats() if isinstance(post_hook, DraftFormattingHook) else {}

    print(f"\n  [OK] Processed {len(results)} tickets")
    print(f"  [OK] Hook stats: {hook_stats.get('total_invocations', 0)} invocations, "
          f"{hook_stats.get('corrections_made', 0)} formatting corrections\n")

    return results, hook_stats


if __name__ == "__main__":
    results, hook_stats = run_all()
    print("\n--- Sample result (TKT-001) ---")
    print(results[0].model_dump_json(indent=2))
