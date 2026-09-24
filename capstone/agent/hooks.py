"""
agent/hooks.py — PostToolUse hook for deterministic response formatting.

WHY A HOOK AND NOT A PROMPT INSTRUCTION?
=========================================
Response formatting (greeting, sign-off, tone) is a brand requirement that
must be deterministic. Prompts are probabilistic — even with "always start
with 'Hi {name}'", models occasionally omit or reformat these elements.

The hook intercepts the assistant's response and applies formatting rules
programmatically. This means:
  - The greeting is always present
  - The sign-off is always correct
  - The model focuses on content, not formatting mechanics

This is the PostToolUse hook pattern from Domain 1.
"""

from __future__ import annotations

import re


FORMATTING_RULES = {
    "greeting_prefix": "Hi",
    "sign_off": "Best regards,\nSupport Team",
    "max_paragraph_words": 80,
}


class ResponseFormattingHook:
    """
    PostToolUse hook that enforces formatting on assistant responses.

    In the Claude Agent SDK, this would be:
        options = ClaudeAgentOptions(
            hooks={"PostToolUse": [response_formatting_hook]}
        )
    """

    def __init__(self):
        self.invocation_count = 0
        self.corrections_made = []

    def __call__(self, response_text: str, customer_name: str = "there") -> str:
        """
        Apply deterministic formatting rules to an assistant response.

        Args:
            response_text: The raw assistant response
            customer_name: Customer's name for the greeting

        Returns:
            The formatted response
        """
        self.invocation_count += 1
        original = response_text
        text = response_text.strip()

        # 1. Ensure greeting
        greeting = f"{FORMATTING_RULES['greeting_prefix']} {customer_name},"
        if not text.lower().startswith(FORMATTING_RULES["greeting_prefix"].lower()):
            text = f"{greeting}\n\n{text}"

        # 2. Enforce paragraph length
        paragraphs = text.split("\n\n")
        trimmed = []
        for para in paragraphs:
            words = para.split()
            if len(words) > FORMATTING_RULES["max_paragraph_words"]:
                chunks = []
                max_w = FORMATTING_RULES["max_paragraph_words"]
                for i in range(0, len(words), max_w):
                    chunks.append(" ".join(words[i:i + max_w]))
                trimmed.extend(chunks)
            else:
                trimmed.append(para)
        text = "\n\n".join(trimmed)

        # 3. Ensure sign-off
        sign_off = FORMATTING_RULES["sign_off"]
        if sign_off.splitlines()[-1].strip() not in text:
            text = f"{text}\n\n{sign_off}"

        # 4. Clean up whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Track corrections
        if text != original:
            changes = []
            if not original.lower().startswith("hi"):
                changes.append("Added greeting")
            if "Best regards" not in original:
                changes.append("Added sign-off")
            if not changes:
                changes.append("Minor formatting")
            self.corrections_made.append(changes)

        return text

    def get_stats(self) -> dict:
        """Return hook invocation statistics."""
        return {
            "total_invocations": self.invocation_count,
            "corrections_made": len(self.corrections_made),
            "correction_details": self.corrections_made,
        }
