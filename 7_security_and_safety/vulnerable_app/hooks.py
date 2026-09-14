"""
vulnerable_app/hooks.py -- No-op hooks (no guardrail enforcement).

DELIBERATELY VULNERABLE:
  - Both pre-processing and post-processing hooks pass everything through
  - No injection detection, no content policy, no output sanitization
  - Demonstrates the anti-pattern of having NO deterministic guardrails

This exists to contrast with the hardened version's hooks.
"""

from __future__ import annotations


def pre_process_hook(article_text: str) -> dict:
    """
    Pre-processing hook -- DOES NOTHING.

    In the hardened version, this is where injection detection happens
    BEFORE content reaches the model. Here, everything passes through.

    Returns:
        {"allowed": True/False, "reason": str, "sanitized_text": str}
    """
    return {
        "allowed": True,
        "reason": "No checks performed",
        "sanitized_text": article_text,  # unchanged
    }


def post_process_hook(response_text: str) -> dict:
    """
    Post-processing hook -- DOES NOTHING.

    In the hardened version, this checks model output for policy violations
    (leaked prompts, credentials, unauthorized actions). Here, everything
    passes through.

    Returns:
        {"allowed": True/False, "reason": str, "sanitized_response": str}
    """
    return {
        "allowed": True,
        "reason": "No checks performed",
        "sanitized_response": response_text,  # unchanged
    }
