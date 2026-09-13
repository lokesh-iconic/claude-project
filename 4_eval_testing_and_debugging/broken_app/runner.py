"""
broken_app/runner.py — Agent runner with a DELIBERATELY INTRODUCED model-output bug.

██████████████████████████████████████████████████████████████████████████████
██  BUG 2 — MODEL-OUTPUT PROBLEM                                         ██
██                                                                        ██
██  The AGENT_SYSTEM_PROMPT has been modified to remove all guidance      ██
██  about HOW to assign priority levels. The original prompt told the    ██
██  model about priority levels explicitly. This broken version says     ██
██  "determine how important it seems" — a vague instruction that        ██
██  causes inconsistent priority assignments.                            ██
██                                                                        ██
██  This bug is in the MODEL-OUTPUT LAYER (prompt quality), not in the   ██
██  code logic. The fix is a PROMPT change.                              ██
██████████████████████████████████████████████████████████████████████████████
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
from broken_app.tools import TOOL_DEFINITIONS, TOOL_EXECUTORS, execute_classify_ticket, execute_route_ticket, execute_draft_response
from broken_app.hooks import create_hooks, DraftFormattingHook
from broken_app.subagent import run_specialist_classifier


def _get_model() -> str:
    return os.getenv("CLAUDE_MODEL", os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"))


# ---------------------------------------------------------------------------
# System Prompt — BROKEN VERSION (Bug 2)
#
# The original prompt had clear priority-level guidance. This version
# removes that guidance, replacing it with vague language that causes
# the model to assign priorities inconsistently.
# ---------------------------------------------------------------------------

AGENT_SYSTEM_PROMPT = """\
You are a support ticket triage agent. You have tools to classify,
route, and draft responses to customer support tickets.

Your process:
1. First, classify the ticket to understand what it's about
2. If classification seems uncertain, use escalate_to_specialist
3. Route the ticket to a team
4. Draft a response

Determine how important each ticket seems and categorize it appropriately.
Use your best judgment for everything.

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

    In the broken version, the mock classifier uses a DEGRADED priority
    heuristic that mirrors what the vague prompt would cause: inconsistent
    priority assignments where urgent/high-priority tickets sometimes get
    downgraded to "medium" because the prompt doesn't provide clear criteria.
    """

    def __init__(self, hooks: dict):
        self.hooks = hooks
        self.tool_calls_log: list[dict] = []

    def process_ticket(self, ticket: Ticket) -> tuple[dict, dict, dict]:
        # Step 1: Classify — BUT with degraded priority logic (Bug 2 effect)
        classify_args = {
            "ticket_id": ticket.id,
            "subject": ticket.subject,
            "body": ticket.body,
        }
        classification = self._classify_with_vague_priority(classify_args)
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

    def _classify_with_vague_priority(self, args: dict) -> dict:
        """
        ╔════════════════════════════════════════════════════════════════╗
        ║  BUG 2 EFFECT: Without clear priority guidance in the        ║
        ║  prompt, the model's priority assignments become             ║
        ║  inconsistent. This mock simulates that by assigning         ║
        ║  "medium" to tickets that SHOULD be "high" or "urgent".     ║
        ║  Specifically:                                               ║
        ║  - Double charges (billing) → medium instead of high         ║
        ║  - Login failures → medium instead of urgent                 ║
        ║  - App crashes → medium instead of high                      ║
        ║  - Cancellation/refund → medium instead of high              ║
        ╚════════════════════════════════════════════════════════════════╝
        """
        text = (args.get("subject", "") + " " + args.get("body", "")).lower()

        if any(w in text for w in ["nothing works", "frustrated", "broken", "nobody", "fwd:", "re: re:"]):
            return {"category": "general", "priority": "medium", "confidence": 0.45,
                    "reasoning": "Seems like a general complaint", "is_ambiguous": True}
        elif any(w in text for w in ["billing", "charged", "invoice", "refund", "promo", "payment"]):
            # BUG 2: Should be "high" but vague prompt yields "medium"
            return {"category": "billing", "priority": "medium", "confidence": 0.88,
                    "reasoning": "Billing related concern", "is_ambiguous": False}
        elif any(w in text for w in ["login", "api", "crash", "error", "timeout", "webhook", "firefox"]):
            # BUG 2: Should be "high"/"urgent" but vague prompt yields "medium"
            return {"category": "technical", "priority": "medium", "confidence": 0.90,
                    "reasoning": "Technical issue", "is_ambiguous": False}
        elif any(w in text for w in ["account", "delete", "gdpr", "upgrade", "transfer", "cancel"]):
            return {"category": "account", "priority": "medium", "confidence": 0.85,
                    "reasoning": "Account management request", "is_ambiguous": False}
        elif any(w in text for w in ["feature", "dark mode", "mobile app", "export"]):
            return {"category": "feature_request", "priority": "low", "confidence": 0.87,
                    "reasoning": "Feature request or product suggestion", "is_ambiguous": False}
        else:
            return {"category": "general", "priority": "medium", "confidence": 0.50,
                    "reasoning": "Could not clearly categorize", "is_ambiguous": True}


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
        except anthropic.AuthenticationError as auth_err:
            print(f"\n  [WARNING] ANTHROPIC_API_KEY from .env is invalid ({auth_err.message}).")
            print("  [WARNING] Running in MOCK mode.\n")
            _client_instance = None
        except anthropic.BadRequestError as req_err:
            if "credit balance is too low" in str(req_err).lower():
                print("\n  [INFO] Credit balance is $0. Running in MOCK mode.\n")
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
    """Process a single ticket through the broken agent system."""
    if hooks is None:
        hooks = create_hooks()

    if client is not None:
        try:
            # Would use live API here — but bugs still apply via the broken prompt
            mock_agent = MockAgentLoop(hooks)
            classification, routing, draft = mock_agent.process_ticket(ticket)
        except Exception as e:
            print(f"    [Notice: Error ({e}) — using mock agent]")
            mock_agent = MockAgentLoop(hooks)
            classification, routing, draft = mock_agent.process_ticket(ticket)
    else:
        mock_agent = MockAgentLoop(hooks)
        classification, routing, draft = mock_agent.process_ticket(ticket)

    # Parse into Pydantic models
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
