"""
mock_model.py — Simulated "model" used by both broken_app and fixed_app in mock mode.

The simulated model reads the agent's system prompt. If the prompt contains an
explicit priority rubric, it assigns priorities with the standard classifier. If it
does not, it falls back to the behaviour a model shows when given only vague guidance:
anything that is not clearly a feature request is rated "medium".

Because the behaviour is driven by the prompt text, changing only the prompt changes
the outcome. No other code differs between the two apps for this concern.
"""

from __future__ import annotations

RUBRIC_MARKER = "Priority Rubric"

# Phrases that mark a ticket as vague, multi-intent or non-English.
AMBIGUITY_MARKERS = ["nothing works", "frustrated", "broken", "nobody", "fwd:", "re: re:", "quiero", "necesito"]

_URGENT_WORDS = ["deadline", "urgently", "blocking", "production", "outage", "data loss", "security breach", "weeks"]
_HIGH_WORDS = ["charged", "charge", "refund", "payment", "paying", "billing", "bill ", "gdpr", "crash", "missing"]
_LOW_WORDS = ["copy of my invoice", "feature", "dark mode", "mobile app", "export for reports"]


def has_priority_rubric(system_prompt: str) -> bool:
    """True when the system prompt gives the model explicit priority criteria."""
    return RUBRIC_MARKER in system_prompt


def rubric_priority(subject: str, body: str) -> str:
    """Priority a model assigns when the prompt contains the explicit rubric."""
    text = (subject + " " + body).lower()
    if any(w in text for w in _URGENT_WORDS):
        return "urgent"
    if any(w in text for w in _HIGH_WORDS):
        return "high"
    if any(w in text for w in _LOW_WORDS):
        return "low"
    return "medium"


def vague_prompt_classification(args: dict) -> dict:
    """Classification a model produces when the prompt gives no priority criteria."""
    text = (args.get("subject", "") + " " + args.get("body", "")).lower()

    if any(w in text for w in AMBIGUITY_MARKERS):
        return {"category": "general", "priority": "medium", "confidence": 0.45,
                "reasoning": "Seems like a general complaint", "is_ambiguous": True}
    elif any(w in text for w in ["billing", "charged", "invoice", "refund", "promo", "payment"]):
        return {"category": "billing", "priority": "medium", "confidence": 0.88,
                "reasoning": "Billing related concern", "is_ambiguous": False}
    elif any(w in text for w in ["login", "api", "crash", "error", "timeout", "webhook", "firefox"]):
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
