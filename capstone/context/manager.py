"""
context/manager.py — Conversation context management with pruning and compaction.

Adapted from Domain 6's ContextManager for the support assistant use case.

Three strategies applied automatically as conversation grows:
  Stage 1 (turns 1-6):   Full history — keep everything
  Stage 2 (turns 7-12):  Prune tool outputs — replace verbose tool results with summaries
  Stage 3 (turns 13+):   Compact old turns — summarize oldest turns into a single block

The support assistant version has tighter thresholds than the general
ContextManager because support conversations tend to be more tool-heavy
(each turn may invoke 1-3 tools with JSON results).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~1.33 tokens per word, minimum 1)."""
    return max(1, len(text.split()) * 4 // 3)


@dataclass
class Message:
    """A single message in the conversation."""
    role: str             # "user", "assistant", or "system"
    content: str
    turn_number: int
    is_tool_output: bool = False
    original_token_count: int = 0
    pruned: bool = False


@dataclass
class TurnMetrics:
    """Token metrics for a single conversation turn."""
    turn_number: int
    context_tokens: int
    user_tokens: int
    assistant_tokens: int
    tool_output_tokens: int
    pruned_tokens: int
    compacted: bool


class SupportContextManager:
    """
    Manages conversation context for the support assistant.

    Prevents context bloat in support sessions by:
    1. Tracking token usage at every turn
    2. Pruning verbose tool outputs (order details, KB articles) after turn 6
    3. Compacting oldest turns into summaries after turn 12

    Tighter thresholds than the general ContextManager because support
    conversations are tool-heavy.
    """

    PRUNE_AFTER_TURN = 6
    COMPACT_AFTER_TURN = 12
    MAX_TOOL_OUTPUT_TOKENS = 80  # Support tool outputs are structured JSON
    KEEP_RECENT_TURNS = 6       # Always keep last 6 turns in full detail

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
        """Add a tool result to the conversation."""
        self.messages.append(Message(
            role="user",
            content=content,
            turn_number=self.current_turn,
            is_tool_output=True,
            original_token_count=estimate_tokens(content),
        ))

    def get_messages_for_api(self) -> list[dict]:
        """
        Build the messages array for the API call, applying pruning/compaction.

        Stage 1 (turns 1-6):   send everything
        Stage 2 (turns 7-12):  prune verbose tool outputs
        Stage 3 (turns 13+):   compact old turns + prune tool outputs
        """
        if self.current_turn > self.COMPACT_AFTER_TURN:
            return self._build_compacted_messages()
        elif self.current_turn > self.PRUNE_AFTER_TURN:
            return self._build_pruned_messages()
        else:
            return self._build_full_messages()

    def _build_full_messages(self) -> list[dict]:
        """Stage 1: Return all messages as-is."""
        return [{"role": m.role, "content": m.content} for m in self.messages]

    def _build_pruned_messages(self) -> list[dict]:
        """Stage 2: Replace verbose tool outputs with summaries."""
        result = []
        for m in self.messages:
            if m.is_tool_output and estimate_tokens(m.content) > self.MAX_TOOL_OUTPUT_TOKENS:
                pruned_content = self._prune_tool_output(m.content)
                m.pruned = True
                result.append({"role": m.role, "content": pruned_content})
            else:
                result.append({"role": m.role, "content": m.content})
        return result

    def _build_compacted_messages(self) -> list[dict]:
        """Stage 3: Summarize old turns + prune tool outputs."""
        keep_after_turn = self.current_turn - self.KEEP_RECENT_TURNS

        old_messages = [m for m in self.messages if m.turn_number <= keep_after_turn]
        recent_messages = [m for m in self.messages if m.turn_number > keep_after_turn]

        result = []

        # Add compaction summary for old turns
        if old_messages:
            summary = self._generate_compaction_summary(old_messages)
            result.append({
                "role": "user",
                "content": f"[CONVERSATION SUMMARY — Turns 1 to {keep_after_turn}]\n{summary}"
            })
            result.append({
                "role": "assistant",
                "content": "Understood. I have the context from our earlier conversation and will continue helping you."
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
        if len(words) <= 60:
            return content
        summary_words = words[:25] + ["[...pruned...]"] + words[-15:]
        return " ".join(summary_words)

    def _generate_compaction_summary(self, old_messages: list[Message]) -> str:
        """Generate a summary of old conversation turns."""
        topics = []
        for m in old_messages:
            if m.role == "user" and not m.is_tool_output:
                first_sentence = m.content.split(".")[0].strip()
                if len(first_sentence.split()) > 15:
                    first_sentence = " ".join(first_sentence.split()[:15]) + "..."
                topics.append(f"- Turn {m.turn_number}: {first_sentence}")

        summary = "Topics discussed:\n" + "\n".join(topics)
        self._compaction_summary = summary
        return summary

    def record_turn_metrics(self) -> TurnMetrics:
        """Record metrics for the current turn."""
        api_messages = self.get_messages_for_api()
        context_tokens = sum(estimate_tokens(m["content"]) for m in api_messages)

        turn_user = [m for m in self.messages
                     if m.turn_number == self.current_turn and m.role == "user" and not m.is_tool_output]
        turn_asst = [m for m in self.messages
                     if m.turn_number == self.current_turn and m.role == "assistant"]
        tool_messages = [m for m in self.messages
                         if m.turn_number == self.current_turn and m.is_tool_output]

        user_tokens = sum(estimate_tokens(m.content) for m in turn_user)
        assistant_tokens = sum(estimate_tokens(m.content) for m in turn_asst)
        tool_tokens = sum(m.original_token_count for m in tool_messages)
        pruned_tokens = sum(
            m.original_token_count - estimate_tokens(self._prune_tool_output(m.content))
            for m in tool_messages if m.original_token_count > self.MAX_TOOL_OUTPUT_TOKENS
        )

        metrics = TurnMetrics(
            turn_number=self.current_turn,
            context_tokens=context_tokens,
            user_tokens=user_tokens,
            assistant_tokens=assistant_tokens,
            tool_output_tokens=tool_tokens,
            pruned_tokens=pruned_tokens,
            compacted=self.current_turn > self.COMPACT_AFTER_TURN,
        )
        self.turn_metrics.append(metrics)
        return metrics

    def get_context_growth_report(self) -> str:
        """Generate a report showing context token growth over time."""
        if not self.turn_metrics:
            return "  No turns recorded.\n"

        lines = []
        lines.append(f"  {'Turn':>5} {'Context':>10} {'User':>8} {'Asst':>8} "
                      f"{'Tool':>8} {'Pruned':>8} {'Compact':>8}")
        lines.append(f"  {'-'*62}")

        for m in self.turn_metrics:
            lines.append(
                f"  {m.turn_number:>5} {m.context_tokens:>10,} {m.user_tokens:>8,} "
                f"{m.assistant_tokens:>8,} {m.tool_output_tokens:>8,} {m.pruned_tokens:>8,} "
                f"{'YES' if m.compacted else 'no':>8}"
            )

        return "\n".join(lines)

    def get_token_savings(self) -> dict:
        """Calculate total token savings from pruning and compaction."""
        if not self.turn_metrics:
            return {"total_pruned": 0, "compacted_turns": 0}

        total_pruned = sum(m.pruned_tokens for m in self.turn_metrics)
        compacted_turns = sum(1 for m in self.turn_metrics if m.compacted)

        return {
            "total_pruned_tokens": total_pruned,
            "compacted_turns": compacted_turns,
            "total_turns": len(self.turn_metrics),
        }
