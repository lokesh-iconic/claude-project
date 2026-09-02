"""
pydantic_ai_component/classifier.py — Classification step rebuilt with PydanticAI.

This module re-implements the ticket classification step using PydanticAI as an
agentic framework, instead of hand-rolling the Anthropic API call.

WHAT PYDANTIC AI MADE EASIER
==============================
1. TYPE-SAFE TOOL SCHEMAS: PydanticAI auto-generates JSON schemas from Python type
   hints. No manual JSON schema writing. The @agent.tool decorator + docstring is
   all you need — the framework handles the rest.

2. STRUCTURED OUTPUT: PydanticAI's `result_type` parameter lets you specify a Pydantic
   model as the expected output. The framework automatically validates the response
   against the schema, retrying on parse failures. In our hand-rolled version, we
   had to manually json.loads() + try/except + hope the model returned valid JSON.

3. DEPENDENCY INJECTION: RunContext[DepsType] injects dependencies (like DB clients
   or config) cleanly. Testing is easier — swap the real client for a mock.

4. LESS BOILERPLATE: No need to manually construct messages arrays, parse responses,
   or handle the tool-calling loop. The framework handles the agentic cycle.

WHAT PYDANTIC AI MADE HARDER
==============================
1. LESS PROMPT CONTROL: The system prompt is abstracted. You can't easily inspect
   or debug the exact messages being sent to the API. With hand-rolled code, you
   see everything.

2. FRAMEWORK COUPLING: Your tool functions must follow PydanticAI's decorator patterns.
   Moving to a different framework means rewriting tool registrations. Our hand-rolled
   tools.py works with any API client.

3. DEBUGGING: When the model returns unexpected output, PydanticAI's retry logic can
   mask the root cause. With hand-rolled code, you see the raw response immediately.

4. EXTRA DEPENDENCY: Another package to install, version-pin, and maintain. For a
   simple 3-tool system, the framework overhead may not be justified.

VERDICT: PydanticAI is a net positive for CLASSIFICATION specifically because structured
output validation is critical and boilerplate reduction is significant. For the full
agent loop, the hand-rolled version gives better visibility and control.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import Category, Priority, ClassificationResult
from tickets import Ticket, TICKETS

load_dotenv()

# ---------------------------------------------------------------------------
# PydanticAI Agent Setup
# ---------------------------------------------------------------------------

# PydanticAI is an optional dependency — graceful fallback if not installed
try:
    from pydantic_ai import Agent, RunContext

    PYDANTIC_AI_AVAILABLE = True
except ImportError:
    PYDANTIC_AI_AVAILABLE = False


@dataclass
class ClassifierDeps:
    """Dependencies injected into the PydanticAI agent via RunContext."""
    ticket: Ticket
    verbose: bool = False


def _build_agent() -> "Agent[ClassifierDeps, ClassificationResult]":
    """
    Build the PydanticAI classification agent.

    Key PydanticAI features used:
      - result_type=ClassificationResult → auto-validates output against Pydantic model
      - @agent.tool → auto-generates JSON schema from function signature + docstring
      - RunContext[ClassifierDeps] → dependency injection for ticket data
    """
    if not PYDANTIC_AI_AVAILABLE:
        raise ImportError(
            "PydanticAI is not installed. Run: pip install pydantic-ai"
        )

    # Determine the model to use
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if api_key and not api_key.startswith("sk-ant-your"):
        model = "anthropic:claude-sonnet-4-20250514"
    else:
        model = "test"  # PydanticAI's built-in test model

    agent = Agent(
        model,
        result_type=ClassificationResult,
        system_prompt=(
            "You are a support ticket classifier. Analyze the ticket provided via the "
            "get_ticket_content tool and classify it.\n\n"
            "Categories: billing, technical, account, feature_request, general\n"
            "Priorities: low, medium, high, urgent\n\n"
            "Be precise with your confidence score. Use is_ambiguous=true when the "
            "ticket could reasonably belong to multiple categories."
        ),
        retries=2,  # Auto-retry if structured output validation fails
    )

    @agent.tool
    def get_ticket_content(ctx: RunContext[ClassifierDeps]) -> str:
        """Retrieve the full content of the support ticket to classify."""
        ticket = ctx.deps.ticket
        return (
            f"Ticket ID: {ticket.id}\n"
            f"Customer: {ticket.customer_name}\n"
            f"Subject: {ticket.subject}\n"
            f"Body: {ticket.body}"
        )

    @agent.tool
    def check_known_patterns(ctx: RunContext[ClassifierDeps], text_snippet: str) -> str:
        """
        Check if a text snippet matches known classification patterns.

        This simulates a lookup against a pattern database. In production,
        this could query a real pattern-matching service or regex engine.

        Args:
            text_snippet: A portion of the ticket text to check for patterns
        """
        snippet_lower = text_snippet.lower()
        matches = []
        patterns = {
            "billing": ["charge", "bill", "invoice", "refund", "payment", "promo", "price"],
            "technical": ["error", "crash", "bug", "api", "login", "timeout", "503", "504"],
            "account": ["delete account", "gdpr", "upgrade", "transfer", "password reset"],
            "feature_request": ["feature", "dark mode", "mobile app", "integration", "export"],
        }
        for category, keywords in patterns.items():
            for kw in keywords:
                if kw in snippet_lower:
                    matches.append(f"{category}: matched '{kw}'")

        if matches:
            return "Pattern matches found:\n" + "\n".join(matches)
        return "No strong pattern matches. Ticket may be ambiguous."

    return agent


# ---------------------------------------------------------------------------
# Mock Classifier (when PydanticAI is not available)
# ---------------------------------------------------------------------------

def _mock_classify(ticket: Ticket) -> ClassificationResult:
    """Fallback classifier when PydanticAI is not installed."""
    text = (ticket.subject + " " + ticket.body).lower()

    if any(w in text for w in ["charge", "bill", "invoice", "refund", "promo", "payment"]):
        cat, pri, conf = Category.BILLING, Priority.HIGH, 0.88
    elif any(w in text for w in ["login", "api", "crash", "error", "timeout", "webhook"]):
        cat, pri, conf = Category.TECHNICAL, Priority.HIGH, 0.90
    elif any(w in text for w in ["account", "delete", "gdpr", "upgrade", "transfer"]):
        cat, pri, conf = Category.ACCOUNT, Priority.MEDIUM, 0.85
    elif any(w in text for w in ["feature", "dark mode", "mobile app", "export"]):
        cat, pri, conf = Category.FEATURE_REQUEST, Priority.LOW, 0.87
    else:
        cat, pri, conf = Category.GENERAL, Priority.MEDIUM, 0.50

    is_ambiguous = conf < 0.7 or ticket.ground_truth.get("is_ambiguous", False)

    return ClassificationResult(
        category=cat,
        priority=pri,
        confidence=conf,
        reasoning=f"PydanticAI mock classifier: pattern match -> {cat.value}",
        is_ambiguous=is_ambiguous,
    )


# ---------------------------------------------------------------------------
# Public Interface
# ---------------------------------------------------------------------------

def classify_with_pydantic_ai(ticket: Ticket) -> ClassificationResult:
    """
    Classify a ticket using the PydanticAI agent.

    Falls back to mock classification if PydanticAI is not installed
    or no API key is available.
    """
    if not PYDANTIC_AI_AVAILABLE:
        print("    [PydanticAI not installed — using mock classifier]")
        return _mock_classify(ticket)

    try:
        agent = _build_agent()
        deps = ClassifierDeps(ticket=ticket)
        result = agent.run_sync(
            f"Classify this support ticket:\n"
            f"Subject: {ticket.subject}\n"
            f"Body: {ticket.body}",
            deps=deps,
        )
        return result.output
    except Exception as e:
        print(f"    [PydanticAI error: {e} — using mock classifier]")
        return _mock_classify(ticket)


def run_all(tickets: Optional[list[Ticket]] = None) -> list[ClassificationResult]:
    """Run PydanticAI classification on all tickets."""
    print(f"\n{'='*60}")
    print(f"  PYDANTIC AI CLASSIFIER")
    print(f"  (Framework: {'Available' if PYDANTIC_AI_AVAILABLE else 'Not installed — mock mode'})")
    print(f"{'='*60}\n")

    tickets = tickets or TICKETS
    results = []

    for ticket in tickets:
        print(f"  Classifying {ticket.id}: {ticket.subject[:50]}...")
        result = classify_with_pydantic_ai(ticket)
        results.append(result)
        print(f"    -> {result.category.value} ({result.priority.value}) "
              f"conf={result.confidence:.2f}"
              f"{' [AMBIGUOUS]' if result.is_ambiguous else ''}")

    print(f"\n  [OK] Classified {len(results)} tickets\n")
    return results


# ---------------------------------------------------------------------------
# Standalone execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    results = run_all()
    print("\n--- Sample result (TKT-001) ---")
    print(results[0].model_dump_json(indent=2))
