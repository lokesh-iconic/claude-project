"""
models/cost_tracker.py — Token and cost tracking with prompt caching measurement.

Wraps Domain 5's MetricsTracker pattern for the capstone support assistant.
Tracks per-call metrics and produces comparison tables showing:
  - Token usage per task type
  - Cost with and without prompt caching
  - Model selection effectiveness
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from capstone.models.router import ModelId, calculate_cost, format_cost, PRICING


@dataclass
class CallMetrics:
    """Metrics for a single API call."""
    call_id: str
    model_id: ModelId
    task: str
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    latency_seconds: float = 0.0
    cost_usd: float = 0.0

    def __post_init__(self):
        if self.cost_usd == 0.0:
            self.cost_usd = calculate_cost(
                self.model_id,
                self.input_tokens,
                self.output_tokens,
                self.cache_write_tokens,
                self.cache_read_tokens,
            )


class CostTracker:
    """
    Tracks token usage and costs across the support assistant's operation.

    Key metrics:
    - Per-task cost breakdown (which tasks cost the most?)
    - Cache hit rate and savings (is prompt caching effective?)
    - Model utilization (are we routing to Haiku when we should?)
    """

    def __init__(self):
        self.calls: list[CallMetrics] = []
        self._session_start = time.time()

    def record_call(
        self,
        call_id: str,
        model_id: ModelId,
        task: str,
        input_tokens: int,
        output_tokens: int,
        cache_write_tokens: int = 0,
        cache_read_tokens: int = 0,
        latency_seconds: float = 0.0,
    ) -> CallMetrics:
        """Record a completed API call."""
        metrics = CallMetrics(
            call_id=call_id,
            model_id=model_id,
            task=task,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_write_tokens=cache_write_tokens,
            cache_read_tokens=cache_read_tokens,
            latency_seconds=latency_seconds,
        )
        self.calls.append(metrics)
        return metrics

    def get_total_cost(self) -> float:
        """Get total cost across all calls."""
        return sum(c.cost_usd for c in self.calls)

    def get_cache_savings(self) -> dict:
        """Calculate prompt caching savings."""
        total_cache_read = sum(c.cache_read_tokens for c in self.calls)
        total_cache_write = sum(c.cache_write_tokens for c in self.calls)

        if total_cache_read == 0 and total_cache_write == 0:
            return {"savings_usd": 0.0, "cache_hit_rate": 0.0}

        # Calculate what it would have cost without caching
        cost_without_cache = 0.0
        cost_with_cache = 0.0
        for c in self.calls:
            p = PRICING[c.model_id]
            # Without cache: all tokens at full input price
            full_input = c.input_tokens + c.cache_read_tokens + c.cache_write_tokens
            cost_without_cache += (full_input / 1_000_000) * p.input_per_mtok
            cost_without_cache += (c.output_tokens / 1_000_000) * p.output_per_mtok
            # With cache: actual cost
            cost_with_cache += c.cost_usd

        savings = cost_without_cache - cost_with_cache
        total_cacheable = total_cache_read + total_cache_write
        hit_rate = total_cache_read / total_cacheable if total_cacheable > 0 else 0.0

        return {
            "savings_usd": round(savings, 6),
            "cost_without_cache": round(cost_without_cache, 6),
            "cost_with_cache": round(cost_with_cache, 6),
            "cache_hit_rate": round(hit_rate, 2),
            "total_cache_read_tokens": total_cache_read,
            "total_cache_write_tokens": total_cache_write,
        }

    def get_model_breakdown(self) -> dict:
        """Get cost breakdown by model."""
        breakdown = {}
        for c in self.calls:
            model_name = "Haiku" if c.model_id == ModelId.HAIKU else "Sonnet"
            if model_name not in breakdown:
                breakdown[model_name] = {"calls": 0, "cost": 0.0, "tokens": 0}
            breakdown[model_name]["calls"] += 1
            breakdown[model_name]["cost"] += c.cost_usd
            breakdown[model_name]["tokens"] += c.input_tokens + c.output_tokens
        return breakdown

    def format_summary(self) -> str:
        """Format a cost summary report."""
        if not self.calls:
            return "  No API calls recorded.\n"

        total = self.get_total_cost()
        cache = self.get_cache_savings()
        models = self.get_model_breakdown()

        lines = [
            f"  Total API calls: {len(self.calls)}",
            f"  Total cost: {format_cost(total)}",
            "",
            "  Model Breakdown:",
        ]

        for model, stats in models.items():
            lines.append(f"    {model}: {stats['calls']} calls, {format_cost(stats['cost'])}, "
                         f"{stats['tokens']:,} tokens")

        if cache["savings_usd"] > 0:
            lines.extend([
                "",
                "  Prompt Caching:",
                f"    Cache hit rate: {cache['cache_hit_rate']:.0%}",
                f"    Cost without cache: {format_cost(cache['cost_without_cache'])}",
                f"    Cost with cache: {format_cost(cache['cost_with_cache'])}",
                f"    Savings: {format_cost(cache['savings_usd'])}",
            ])

        return "\n".join(lines)
