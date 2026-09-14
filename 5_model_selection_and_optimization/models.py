"""
models.py -- Model registry, pricing tables, and cost calculator.

Contains real Anthropic model pricing (as of 2025) so cost calculations
are accurate in both mock and live modes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ModelId(str, Enum):
    """Supported Claude model identifiers."""
    HAIKU = "claude-3-5-haiku-20241022"
    SONNET = "claude-sonnet-4-20250514"


@dataclass(frozen=True)
class ModelPricing:
    """Per-million-token pricing for a Claude model."""
    input_per_mtok: float       # $/MTok for input tokens
    output_per_mtok: float      # $/MTok for output tokens
    cache_write_per_mtok: float # $/MTok for cache write (system prompt caching)
    cache_read_per_mtok: float  # $/MTok for cache read


@dataclass(frozen=True)
class ModelConfig:
    """Configuration and metadata for a model."""
    id: ModelId
    display_name: str
    pricing: ModelPricing
    max_output_tokens: int
    context_window: int
    supports_thinking: bool
    typical_latency_factor: float  # relative speed (1.0 = baseline)


# ---------------------------------------------------------------------------
# Pricing Table (Anthropic official rates, 2025)
# ---------------------------------------------------------------------------

PRICING = {
    ModelId.HAIKU: ModelPricing(
        input_per_mtok=0.80,
        output_per_mtok=4.00,
        cache_write_per_mtok=1.00,
        cache_read_per_mtok=0.08,
    ),
    ModelId.SONNET: ModelPricing(
        input_per_mtok=3.00,
        output_per_mtok=15.00,
        cache_write_per_mtok=3.75,
        cache_read_per_mtok=0.30,
    ),
}


# ---------------------------------------------------------------------------
# Model Configs
# ---------------------------------------------------------------------------

MODELS = {
    ModelId.HAIKU: ModelConfig(
        id=ModelId.HAIKU,
        display_name="Claude 3.5 Haiku",
        pricing=PRICING[ModelId.HAIKU],
        max_output_tokens=8192,
        context_window=200_000,
        supports_thinking=False,
        typical_latency_factor=0.4,  # ~2.5x faster than Sonnet
    ),
    ModelId.SONNET: ModelConfig(
        id=ModelId.SONNET,
        display_name="Claude Sonnet 4",
        pricing=PRICING[ModelId.SONNET],
        max_output_tokens=16_384,
        context_window=200_000,
        supports_thinking=True,
        typical_latency_factor=1.0,  # baseline
    ),
}


# ---------------------------------------------------------------------------
# Cost Calculator
# ---------------------------------------------------------------------------

def calculate_cost(
    model_id: ModelId,
    input_tokens: int,
    output_tokens: int,
    cache_write_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float:
    """
    Calculate the cost of a single API call in USD.

    Args:
        model_id: Which model was used
        input_tokens: Non-cached input tokens
        output_tokens: Output tokens generated
        cache_write_tokens: Tokens written to cache (first call)
        cache_read_tokens: Tokens read from cache (subsequent calls)

    Returns:
        Cost in USD (float)
    """
    p = PRICING[model_id]

    cost = (
        (input_tokens / 1_000_000) * p.input_per_mtok
        + (output_tokens / 1_000_000) * p.output_per_mtok
        + (cache_write_tokens / 1_000_000) * p.cache_write_per_mtok
        + (cache_read_tokens / 1_000_000) * p.cache_read_per_mtok
    )

    return round(cost, 8)


def format_cost(cost: float) -> str:
    """Format a cost in USD for display."""
    if cost < 0.001:
        return f"${cost:.6f}"
    elif cost < 0.01:
        return f"${cost:.4f}"
    else:
        return f"${cost:.4f}"
