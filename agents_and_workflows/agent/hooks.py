"""
agent/hooks.py — PreToolUse hook that enforces formatting on draft responses.

WHY A HOOK AND NOT A PROMPT INSTRUCTION?
=========================================
Prompts are probabilistic — even with explicit instructions like "always start with
'Hi {name}'" or "always end with 'Best regards'", models occasionally omit or
reformat these elements. For customer-facing responses where formatting consistency
is a business requirement (brand voice, compliance), we need a DETERMINISTIC
guarantee.

The hook intercepts the draft_response tool's output and applies shared.enforce_formatting()
programmatically. This means:
  - The greeting is always present and correctly formatted
  - The sign-off is always appended
  - Paragraph length limits are always enforced
  - The model can focus on writing good content instead of remembering formatting rules

This is the canonical example of "use a hook for deterministic rules, use the prompt
for creative/judgmental work."
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import DraftResponse, enforce_formatting


class DraftFormattingHook:
    """
    A PostToolUse hook that intercepts draft_response results and enforces
    formatting rules deterministically.

    In the Claude Agent SDK, this would be registered as a PostToolUse hook.
    Here we implement it as a callable class that the agent runner invokes
    after any tool execution.
    """

    def __init__(self):
        self.invocation_count = 0
        self.corrections_made = []

    def __call__(self, tool_name: str, tool_input: dict, tool_result: dict) -> dict:
        """
        Intercept tool results. Only modifies draft_response outputs.

        Args:
            tool_name: Name of the tool that was executed
            tool_input: The input arguments passed to the tool
            tool_result: The raw result from the tool

        Returns:
            The (potentially modified) tool result
        """
        if tool_name != "draft_response":
            return tool_result

        self.invocation_count += 1

        # Parse the raw draft
        try:
            raw_draft = DraftResponse(**tool_result)
        except Exception:
            # If we can't parse it, return as-is and log the issue
            self.corrections_made.append({
                "ticket_id": tool_input.get("ticket_id", "unknown"),
                "issue": "Could not parse draft for formatting",
            })
            return tool_result

        # Extract customer name from tool input
        customer_name = tool_input.get("customer_name", "there")

        # Record the original body for comparison
        original_body = raw_draft.body

        # Apply deterministic formatting
        formatted_draft = enforce_formatting(raw_draft, customer_name=customer_name)

        # Track what changed
        if formatted_draft.body != original_body:
            self.corrections_made.append({
                "ticket_id": tool_input.get("ticket_id", "unknown"),
                "changes": _diff_summary(original_body, formatted_draft.body),
            })

        return formatted_draft.model_dump()

    def get_stats(self) -> dict:
        """Return hook invocation statistics."""
        return {
            "total_invocations": self.invocation_count,
            "corrections_made": len(self.corrections_made),
            "details": self.corrections_made,
        }


def _diff_summary(original: str, formatted: str) -> list[str]:
    """Summarize what the formatting hook changed."""
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


# ---------------------------------------------------------------------------
# Hook Registration Helper
# ---------------------------------------------------------------------------

def create_hooks() -> dict[str, DraftFormattingHook]:
    """
    Create the hook registry for the agent runner.

    In the Claude Agent SDK, hooks would be registered via ClaudeAgentOptions.
    Here we return a dict mapping hook event types to hook instances.

    Example of how this maps to the SDK:

        # Claude Agent SDK equivalent:
        # options = ClaudeAgentOptions(
        #     hooks={
        #         "PostToolUse": [draft_formatting_hook]
        #     }
        # )
    """
    return {
        "PostToolUse": DraftFormattingHook(),
    }
