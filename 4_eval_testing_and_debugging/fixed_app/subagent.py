"""
fixed_app/subagent.py — Specialist subagent (identical to broken_app, no changes needed).
"""

from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True), override=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import ClassificationResult, Category, Priority


def _get_model() -> str:
    return os.getenv("CLAUDE_MODEL", os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"))


SPECIALIST_SYSTEM_PROMPT = """\
You are a SPECIALIST support ticket classifier for AMBIGUOUS tickets — tickets that
don't clearly fit a single category or contain mixed signals.

Your job is to make a careful judgment call using chain-of-thought reasoning.

## Categories
- billing: Payment, charges, invoices, refunds, pricing, subscriptions (money-related)
- technical: Bugs, errors, crashes, API issues, browser compatibility, performance
- account: Account settings, deletion, upgrades, transfers, GDPR, access management
- feature_request: New feature suggestions, product improvements, integrations
- general: Truly uncategorizable, or requires human judgment to route

## Decision Process
1. List ALL topics the ticket touches
2. Identify the PRIMARY action the customer wants
3. If the primary action maps to a category, use that category
4. If genuinely split, pick the category that best serves the customer's immediate need
5. Always explain your reasoning

Return a JSON object with:
- "category": one of the categories above
- "priority": "low", "medium", "high", or "urgent"
- "confidence": float 0.0-1.0
- "reasoning": your chain-of-thought analysis (2-3 sentences)
- "is_ambiguous": true
- "topics_detected": list of all categories the ticket touches

Return ONLY valid JSON."""


def run_specialist_classifier(
    ticket_id: str,
    subject: str,
    body: str,
    initial_category: str | None = None,
    reason_for_escalation: str = "",
    client=None,
) -> dict:
    if client is not None:
        try:
            user_content = f"Ticket ID: {ticket_id}\nSubject: {subject}\nBody: {body}\n"
            if initial_category:
                user_content += f"\nInitial best-guess category: {initial_category}"
            if reason_for_escalation:
                user_content += f"\nReason for specialist review: {reason_for_escalation}"
            response = client.messages.create(
                model=_get_model(), max_tokens=500,
                system=SPECIALIST_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
            return json.loads(response.content[0].text)
        except Exception as e:
            print(f"    [Notice: Specialist API error ({e}) — mock fallback]")

    text = (subject + " " + body).lower()
    topics = []
    if any(w in text for w in ["bill", "charg", "pay", "refund", "invoice", "pric", "subscript"]):
        topics.append("billing")
    if any(w in text for w in ["error", "crash", "bug", "api", "login", "load", "broken", "link"]):
        topics.append("technical")
    if any(w in text for w in ["account", "cancel", "delet", "gdpr", "upgrade", "transfer", "export"]):
        topics.append("account")
    if any(w in text for w in ["feature", "request", "integrat", "dark mode", "mobile", "slack"]):
        topics.append("feature_request")
    if not topics:
        topics = ["general"]

    primary = topics[0] if len(topics) == 1 else (
        topics[0] if topics[0] != "feature_request" else topics[1] if len(topics) > 1 else topics[0]
    )
    confidence = 0.75 if len(topics) == 1 else max(0.40, 0.70 - 0.10 * len(topics))

    priority = "medium"
    if any(w in text for w in ["urgent", "asap", "frustrated", "angry", "nobody", "two weeks"]):
        priority = "urgent"
    elif any(w in text for w in ["wrong", "shouldn't", "broken"]):
        priority = "high"

    reasoning = (
        f"Specialist analysis: Ticket touches {len(topics)} topic(s): {', '.join(topics)}. "
        f"Primary customer need maps to '{primary}'. "
        f"{'Multiple concerns reduce classification confidence.' if len(topics) > 1 else 'Single concern detected.'}"
    )
    return {
        "category": primary, "priority": priority,
        "confidence": round(confidence, 2), "reasoning": reasoning,
        "is_ambiguous": True, "topics_detected": topics,
    }
