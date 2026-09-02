"""
agent/runner.py — Agentic loop with custom tool-calling cycle.

This is the AGENT version: Claude receives all tools and decides:
  - Which tool to call
  - In what order
  - Whether to loop back (e.g., re-classify after seeing routing results)
  - When to stop (return a final text response)

The agent can deviate from classify→route→draft when it judges the situation
warrants it — e.g., escalating ambiguous tickets to the specialist subagent,
or reclassifying after discovering a routing conflict.

Architecture:
  1. Send ticket + system prompt + tools to Claude
  2. If Claude returns tool_use → execute the tool, apply hooks, feed result back
  3. Repeat until Claude returns a text-only response (end_turn)
  4. Parse final state into TicketResult
"""

from __future__ import annotations

import json
import os
import sys
from typing import Optional

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import (
    ClassificationResult, RoutingResult, DraftResponse, TicketResult,
    Category, Priority, Team,
)
from tickets import Ticket, TICKETS
from agent.tools import TOOL_DEFINITIONS, TOOL_EXECUTORS, execute_classify_ticket, execute_route_ticket, execute_draft_response
from agent.hooks import create_hooks, DraftFormattingHook
from agent.subagent import run_specialist_classifier

load_dotenv()


# ---------------------------------------------------------------------------
# System Prompt for the Agent
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

You MAY deviate from this order if the situation warrants it. For example:
- If routing reveals a conflict, you can re-classify
- If the draft doesn't match the ticket tone, you can re-draft
- If you detect urgency, escalate immediately

When you're done with ALL steps (classify, route, draft), provide a final
summary as plain text. Include the classification, routing, and confirm the
draft is ready.

Always process the COMPLETE pipeline. Do not stop after just classification."""


# ---------------------------------------------------------------------------
# Mock Agent Loop (simulates Claude's tool-calling behavior)
# ---------------------------------------------------------------------------

class MockAgentLoop:
    """
    Simulates Claude's agentic behavior for mock mode.

    In live mode, the actual Anthropic API handles tool selection.
    In mock mode, this class follows a deterministic flow that mimics
    what Claude would do, including escalation for ambiguous tickets.
    """

    def __init__(self, hooks: dict):
        self.hooks = hooks
        self.tool_calls_log: list[dict] = []

    def process_ticket(self, ticket: Ticket) -> tuple[dict, dict, dict]:
        """
        Process a ticket through the mock agent loop.

        Returns (classification, routing, draft) dicts.
        """
        # Step 1: Classify
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

            # Use specialist's classification (overrides initial)
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
# Live Agent Loop (uses Anthropic API with tool calling)
# ---------------------------------------------------------------------------

def run_agent_loop_live(ticket: Ticket, client, hooks: dict) -> tuple[dict, dict, dict]:
    """
    Run the real agentic loop using Anthropic API tool calling.

    This is a standard tool-calling loop:
    1. Send messages + tools to Claude
    2. If response contains tool_use → execute tool, apply hooks, add result to messages
    3. Repeat until Claude stops calling tools
    """
    messages = [{
        "role": "user",
        "content": (
            f"Process this support ticket through the full pipeline "
            f"(classify → route → draft):\n\n"
            f"Ticket ID: {ticket.id}\n"
            f"Customer: {ticket.customer_name}\n"
            f"Subject: {ticket.subject}\n"
            f"Body: {ticket.body}"
        ),
    }]

    classification = {}
    routing = {}
    draft = {}
    max_iterations = 10  # Safety limit

    for iteration in range(max_iterations):
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=AGENT_SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        # Collect the assistant's full response
        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        # Check if we're done (no more tool calls)
        tool_use_blocks = [b for b in assistant_content if b.type == "tool_use"]
        if not tool_use_blocks:
            break  # Claude returned final text → done

        # Process each tool call
        tool_results = []
        for tool_block in tool_use_blocks:
            tool_name = tool_block.name
            tool_input = tool_block.input

            # Execute the tool
            if tool_name == "escalate_to_specialist":
                result = run_specialist_classifier(
                    ticket_id=tool_input.get("ticket_id", ticket.id),
                    subject=tool_input.get("subject", ticket.subject),
                    body=tool_input.get("body", ticket.body),
                    initial_category=tool_input.get("initial_category"),
                    reason_for_escalation=tool_input.get("reason_for_escalation", ""),
                    client=client,
                )
            elif tool_name in TOOL_EXECUTORS:
                result = TOOL_EXECUTORS[tool_name](tool_input, client)
            else:
                result = {"error": f"Unknown tool: {tool_name}"}

            # Apply PostToolUse hook
            post_hook = hooks.get("PostToolUse")
            if post_hook:
                result = post_hook(tool_name, tool_input, result)

            # Track results by tool type
            if tool_name == "classify_ticket":
                classification = result
            elif tool_name == "escalate_to_specialist":
                classification = result  # Override with specialist
            elif tool_name == "route_ticket":
                routing = result
            elif tool_name == "draft_response":
                draft = result

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_block.id,
                "content": json.dumps(result),
            })

        messages.append({"role": "user", "content": tool_results})

    return classification, routing, draft


# ---------------------------------------------------------------------------
# Public Interface
# ---------------------------------------------------------------------------

def _get_client():
    """Get the Anthropic client, or None if in mock mode."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or api_key.startswith("sk-ant-your"):
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=api_key)
    except Exception:
        return None


def process_ticket(ticket: Ticket, client=None, hooks: dict | None = None) -> TicketResult:
    """Process a single ticket through the agent system."""
    if hooks is None:
        hooks = create_hooks()

    if client is not None:
        classification, routing, draft = run_agent_loop_live(ticket, client, hooks)
    else:
        mock_agent = MockAgentLoop(hooks)
        classification, routing, draft = mock_agent.process_ticket(ticket)

    # Parse into Pydantic models (with defaults for missing fields)
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
        system="agent",
    )


def run_all(tickets: Optional[list[Ticket]] = None) -> tuple[list[TicketResult], dict]:
    """
    Run the agent system on all tickets.

    Returns:
        (results, hook_stats) — results for each ticket and hook statistics
    """
    client = _get_client()
    hooks = create_hooks()
    mode = "LIVE (Anthropic API)" if client else "MOCK (no API key)"

    print(f"\n{'='*60}")
    print(f"  AGENT SYSTEM — {mode}")
    print(f"{'='*60}\n")

    tickets = tickets or TICKETS
    results = []

    for ticket in tickets:
        print(f"  Processing {ticket.id}: {ticket.subject[:50]}...")
        result = process_ticket(ticket, client, hooks)
        results.append(result)

        # Show the agent's decision path
        flags = []
        if result.classification.is_ambiguous:
            flags.append("AMBIGUOUS->SPECIALIST")
        if result.routing.escalate:
            flags.append("ESCALATED")

        flag_str = f" [{', '.join(flags)}]" if flags else ""
        print(f"    -> {result.classification.category.value} "
              f"({result.classification.priority.value}) "
              f"-> {result.routing.team.value}{flag_str}")

    # Get hook stats
    post_hook = hooks.get("PostToolUse")
    hook_stats = post_hook.get_stats() if isinstance(post_hook, DraftFormattingHook) else {}

    print(f"\n  [OK] Processed {len(results)} tickets")
    print(f"  [OK] Hook stats: {hook_stats.get('total_invocations', 0)} invocations, "
          f"{hook_stats.get('corrections_made', 0)} formatting corrections\n")

    return results, hook_stats


# ---------------------------------------------------------------------------
# Standalone execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    results, hook_stats = run_all()
    print("\n--- Sample result (TKT-001) ---")
    print(results[0].model_dump_json(indent=2))
    print("\n--- Hook Statistics ---")
    print(json.dumps(hook_stats, indent=2))
