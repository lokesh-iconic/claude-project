"""
broken_app/runner.py — Agent runner whose system prompt lacks a priority rubric.

Model-output problem: AGENT_SYSTEM_PROMPT tells the model to "determine how important
each ticket seems" instead of giving explicit URGENT / HIGH / MEDIUM / LOW criteria.
The code in this file is identical to fixed_app/runner.py; only the prompt differs.
"""

from __future__ import annotations

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
from mock_model import has_priority_rubric, rubric_priority, vague_prompt_classification
from broken_app.tools import execute_classify_ticket, execute_route_ticket, execute_draft_response
from broken_app.hooks import create_hooks, DraftFormattingHook
from broken_app.subagent import run_specialist_classifier


# ---------------------------------------------------------------------------
# System Prompt
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

Determine how important each ticket seems and use your best judgment.

You MAY deviate from the classify→route→draft order if the situation warrants it.

When you're done with ALL steps (classify, route, draft), provide a final
summary as plain text. Include the classification, routing, and confirm the
draft is ready.

Always process the COMPLETE pipeline. Do not stop after just classification."""


# ---------------------------------------------------------------------------
# Mock Agent Loop
# ---------------------------------------------------------------------------

class MockAgentLoop:
    """
    Simulates Claude's agentic behavior for mock mode.

    Classification is produced by the simulated model in mock_model.py, which
    reads `system_prompt` to decide how it assigns priorities.
    """

    def __init__(self, hooks: dict, system_prompt: str = AGENT_SYSTEM_PROMPT):
        self.hooks = hooks
        self.system_prompt = system_prompt
        self.tool_calls_log: list[dict] = []

    def _classify(self, classify_args: dict) -> dict:
        if has_priority_rubric(self.system_prompt):
            return execute_classify_ticket(classify_args)
        return vague_prompt_classification(classify_args)

    def _judge_priority(self, ticket: Ticket, classification: dict) -> dict:
        """With an explicit rubric the simulated model applies it to the final classification."""
        if has_priority_rubric(self.system_prompt):
            return {**classification, "priority": rubric_priority(ticket.subject, ticket.body)}
        return classification

    def process_ticket(self, ticket: Ticket) -> tuple[dict, dict, dict]:
        # Step 1: Classify
        classify_args = {
            "ticket_id": ticket.id,
            "subject": ticket.subject,
            "body": ticket.body,
        }
        classification = self._judge_priority(ticket, self._classify(classify_args))
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
            specialist_result = self._judge_priority(ticket, run_specialist_classifier(**specialist_args))
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

def process_ticket(ticket: Ticket, hooks: dict | None = None) -> TicketResult:
    """Process a single ticket through the agent system."""
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
        system="agent-broken",
    )


def run_all(tickets: Optional[list[Ticket]] = None) -> tuple[list[TicketResult], dict]:
    """Run the broken agent system on all tickets."""
    hooks = create_hooks()

    print(f"\n{'='*60}")
    print(f"  BROKEN AGENT SYSTEM — MOCK MODE")
    print(f"{'='*60}\n")

    tickets = tickets or TICKETS
    results = []

    for ticket in tickets:
        print(f"  Processing {ticket.id}: {ticket.subject[:50]}...")
        result = process_ticket(ticket, hooks)
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
