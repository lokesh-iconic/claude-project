"""
broken_app/hooks.py — PostToolUse hook that enforces formatting on draft responses.

This is an UNMODIFIED copy of the working hooks.py from Domain 1.
The hooks are NOT where either bug was introduced.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import DraftResponse, enforce_formatting


class DraftFormattingHook:
    """
    A PostToolUse hook that intercepts draft_response results and enforces
    formatting rules deterministically.
    """

    def __init__(self):
        self.invocation_count = 0
        self.corrections_made = []

    def __call__(self, tool_name: str, tool_input: dict, tool_result: dict) -> dict:
        if tool_name != "draft_response":
            return tool_result

        self.invocation_count += 1

        try:
            raw_draft = DraftResponse(**tool_result)
        except Exception:
            self.corrections_made.append({
                "ticket_id": tool_input.get("ticket_id", "unknown"),
                "issue": "Could not parse draft for formatting",
            })
            return tool_result

        customer_name = tool_input.get("customer_name", "there")
        original_body = raw_draft.body
        formatted_draft = enforce_formatting(raw_draft, customer_name=customer_name)

        if formatted_draft.body != original_body:
            self.corrections_made.append({
                "ticket_id": tool_input.get("ticket_id", "unknown"),
                "changes": _diff_summary(original_body, formatted_draft.body),
            })

        return formatted_draft.model_dump()

    def get_stats(self) -> dict:
        return {
            "total_invocations": self.invocation_count,
            "corrections_made": len(self.corrections_made),
            "details": self.corrections_made,
        }


def _diff_summary(original: str, formatted: str) -> list[str]:
    changes = []
    if not original.startswith("Hi"):
        changes.append("Added greeting")
    if "Best regards" not in original and "Best regards" in formatted:
        changes.append("Added sign-off")
    if len(original.split("\n\n")) != len(formatted.split("\n\n")):
        changes.append("Reformatted paragraphs")
    if not changes:
        changes.append("Minor whitespace cleanup")
    return changes


def create_hooks() -> dict[str, DraftFormattingHook]:
    return {
        "PostToolUse": DraftFormattingHook(),
    }
