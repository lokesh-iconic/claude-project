"""
context_manager.py -- Conversation pruning, compaction, and token budget tracking.

Three strategies applied automatically as conversation grows:

  Stage 1 (turns 1-8):   Full history — keep everything
  Stage 2 (turns 9-15):  Prune tool outputs — replace verbose results with summaries
  Stage 3 (turns 16+):   Compact old turns — summarize oldest turns into a single block

Tracks token usage per turn so we can MEASURE whether compaction reduces costs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TurnMetrics:
    """Token metrics for a single conversation turn."""
    turn_number: int
    user_tokens: int
    assistant_tokens: int
    context_tokens: int        # Total tokens in the messages array sent to the API
    tool_output_tokens: int    # Tokens from tool/subagent outputs (before pruning)
    pruned_tokens: int         # Tokens saved by pruning
    compacted: bool            # Whether compaction was applied this turn
    format_compliant: bool     # Whether response followed the structured format
    summary_word_count: int    # Words in the summary field


@dataclass
class Message:
    """A single message in the conversation."""
    role: str             # "user", "assistant", or "system"
    content: str
    turn_number: int
    is_tool_output: bool = False
    original_token_count: int = 0
    pruned: bool = False


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~1.33 tokens per word, minimum 1)."""
    return max(1, len(text.split()) * 4 // 3)


class ContextManager:
    """
    Manages conversation context with automatic pruning and compaction.

    Prevents context bloat in long sessions by:
    1. Tracking token usage at every turn
    2. Pruning verbose tool outputs after turn 8
    3. Compacting oldest turns into summaries after turn 15
    """

    # Thresholds for switching strategies
    PRUNE_AFTER_TURN = 8
    COMPACT_AFTER_TURN = 15
    MAX_TOOL_OUTPUT_TOKENS = 100  # Prune tool outputs longer than this

    def __init__(self):
        self.messages: list[Message] = []
        self.turn_metrics: list[TurnMetrics] = []
        self.current_turn = 0
        self._compaction_summary: Optional[str] = None

    def add_user_message(self, content: str) -> None:
        """Add a user message to the conversation."""
        self.current_turn += 1
        self.messages.append(Message(
            role="user",
            content=content,
            turn_number=self.current_turn,
            original_token_count=estimate_tokens(content),
        ))

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant response to the conversation."""
        self.messages.append(Message(
            role="assistant",
            content=content,
            turn_number=self.current_turn,
            original_token_count=estimate_tokens(content),
        ))

    def add_tool_output(self, content: str) -> None:
        """Add a tool/subagent output to the conversation."""
        self.messages.append(Message(
            role="user",  # Tool outputs injected as context
            content=content,
            turn_number=self.current_turn,
            is_tool_output=True,
            original_token_count=estimate_tokens(content),
        ))

    def get_messages_for_api(self) -> list[dict]:
        """
        Build the messages array for the API call, applying pruning/compaction.

        This is where the context engineering happens:
        - Stage 1 (turns 1-8): send everything
        - Stage 2 (turns 9-15): prune verbose tool outputs
        - Stage 3 (turns 16+): compact old turns + prune tool outputs
        """
        messages = []

        # --- Stage 3: Compact old turns if past threshold ---
        if self.current_turn > self.COMPACT_AFTER_TURN:
            messages = self._build_compacted_messages()
        # --- Stage 2: Just prune tool outputs ---
        elif self.current_turn > self.PRUNE_AFTER_TURN:
            messages = self._build_pruned_messages()
        # --- Stage 1: Send everything ---
        else:
            messages = self._build_full_messages()

        return messages

    def _build_full_messages(self) -> list[dict]:
        """Stage 1: Return all messages as-is."""
        return [{"role": m.role, "content": m.content} for m in self.messages]

    def _build_pruned_messages(self) -> list[dict]:
        """Stage 2: Replace verbose tool outputs with summaries."""
        result = []
        for m in self.messages:
            if m.is_tool_output and estimate_tokens(m.content) > self.MAX_TOOL_OUTPUT_TOKENS:
                # Prune: replace with a compact summary
                pruned_content = self._prune_tool_output(m.content)
                m.pruned = True
                result.append({"role": m.role, "content": pruned_content})
            else:
                result.append({"role": m.role, "content": m.content})
        return result

    def _build_compacted_messages(self) -> list[dict]:
        """Stage 3: Summarize old turns + prune tool outputs."""
        # Keep the last 8 turns in full detail
        keep_after_turn = self.current_turn - 8

        old_messages = [m for m in self.messages if m.turn_number <= keep_after_turn]
        recent_messages = [m for m in self.messages if m.turn_number > keep_after_turn]

        result = []

        # Add compaction summary for old turns
        if old_messages:
            summary = self._generate_compaction_summary(old_messages)
            result.append({
                "role": "user",
                "content": f"[CONVERSATION SUMMARY - Turns 1 to {keep_after_turn}]\n{summary}"
            })
            result.append({
                "role": "assistant",
                "content": '{"summary": "Acknowledged conversation history.", "details": "I have the context from our previous discussion.", "sources": [], "confidence": "high", "follow_up": null}'
            })

        # Add recent messages with pruning
        for m in recent_messages:
            if m.is_tool_output and estimate_tokens(m.content) > self.MAX_TOOL_OUTPUT_TOKENS:
                pruned_content = self._prune_tool_output(m.content)
                m.pruned = True
                result.append({"role": m.role, "content": pruned_content})
            else:
                result.append({"role": m.role, "content": m.content})

        return result

    def _prune_tool_output(self, content: str) -> str:
        """Replace a verbose tool output with a compact summary."""
        words = content.split()
        if len(words) <= 75:  # Already short enough
            return content

        # Take first 30 and last 20 words as a summary
        summary_words = words[:30] + ["[...pruned...]"] + words[-20:]
        return " ".join(summary_words)

    def _generate_compaction_summary(self, old_messages: list[Message]) -> str:
        """Generate a summary of old conversation turns."""
        topics = []
        for m in old_messages:
            if m.role == "user" and not m.is_tool_output:
                # Extract first sentence or first 15 words as topic
                first_sentence = m.content.split(".")[0].strip()
                if len(first_sentence.split()) > 15:
                    first_sentence = " ".join(first_sentence.split()[:15]) + "..."
                topics.append(f"- Turn {m.turn_number}: {first_sentence}")

        summary = "Topics discussed so far:\n" + "\n".join(topics)
        self._compaction_summary = summary
        return summary

    def record_turn_metrics(self, format_compliant: bool, summary_word_count: int) -> TurnMetrics:
        """Record metrics for the current turn."""
        # Calculate token usage
        api_messages = self.get_messages_for_api()
        context_tokens = sum(estimate_tokens(m["content"]) for m in api_messages)

        # Calculate pruning savings
        tool_messages = [m for m in self.messages
                         if m.turn_number == self.current_turn and m.is_tool_output]
        tool_tokens = sum(m.original_token_count for m in tool_messages)
        pruned_tokens = sum(
            m.original_token_count - estimate_tokens(self._prune_tool_output(m.content))
            for m in tool_messages if m.original_token_count > self.MAX_TOOL_OUTPUT_TOKENS
        )

        # Get user/assistant tokens for this turn
        turn_user = [m for m in self.messages
                     if m.turn_number == self.current_turn and m.role == "user" and not m.is_tool_output]
        turn_asst = [m for m in self.messages
                     if m.turn_number == self.current_turn and m.role == "assistant"]

        user_tokens = sum(estimate_tokens(m.content) for m in turn_user)
        assistant_tokens = sum(estimate_tokens(m.content) for m in turn_asst)

        metrics = TurnMetrics(
            turn_number=self.current_turn,
            user_tokens=user_tokens,
            assistant_tokens=assistant_tokens,
            context_tokens=context_tokens,
            tool_output_tokens=tool_tokens,
            pruned_tokens=pruned_tokens,
            compacted=self.current_turn > self.COMPACT_AFTER_TURN,
            format_compliant=format_compliant,
            summary_word_count=summary_word_count,
        )
        self.turn_metrics.append(metrics)
        return metrics

    def get_context_growth_report(self) -> str:
        """Generate a report showing how context tokens grew over time."""
        if not self.turn_metrics:
            return "  No turns recorded.\n"

        lines = []
        lines.append(f"  {'Turn':>5} {'Context':>10} {'User':>8} {'Asst':>8} "
                      f"{'Tool':>8} {'Pruned':>8} {'Compact':>8} {'Compliant':>10} {'Summary WC':>11}")
        lines.append(f"  {'─'*86}")

        for m in self.turn_metrics:
            lines.append(
                f"  {m.turn_number:>5} {m.context_tokens:>10,} {m.user_tokens:>8,} "
                f"{m.assistant_tokens:>8,} {m.tool_output_tokens:>8,} {m.pruned_tokens:>8,} "
                f"{'YES' if m.compacted else 'no':>8} {'YES' if m.format_compliant else 'FAIL':>10} "
                f"{m.summary_word_count:>11}"
            )

        return "\n".join(lines)

    def get_token_savings_report(self) -> dict:
        """Calculate total token savings from pruning and compaction."""
        if not self.turn_metrics:
            return {"total_pruned": 0, "compacted_turns": 0}

        total_pruned = sum(m.pruned_tokens for m in self.turn_metrics)
        compacted_turns = sum(1 for m in self.turn_metrics if m.compacted)

        # Compare context tokens: what would they be without compaction?
        # Estimate: each compacted turn saves ~80% of the old turns' tokens
        if len(self.turn_metrics) >= 2:
            early_growth_rate = self.turn_metrics[min(7, len(self.turn_metrics) - 1)].context_tokens / max(1, min(8, len(self.turn_metrics)))
            projected_no_compact = int(early_growth_rate * len(self.turn_metrics))
            actual = self.turn_metrics[-1].context_tokens if self.turn_metrics else 0
            compaction_savings = max(0, projected_no_compact - actual)
        else:
            compaction_savings = 0

        return {
            "total_pruned_tokens": total_pruned,
            "compacted_turns": compacted_turns,
            "estimated_compaction_savings": compaction_savings,
            "total_turns": len(self.turn_metrics),
        }
