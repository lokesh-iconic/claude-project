"""
models/router.py — Per-task model selection for the support assistant.

Implements Domain 5's requirement: choose models DELIBERATELY per task,
not one-size-fits-all. Each task type maps to a specific model with
justification documented in config.yaml.

Model assignments:
  simple_lookup  → Haiku   ($0.80/MTok in, $4.00/MTok out) — data retrieval
  classification → Haiku   ($0.80/MTok in, $4.00/MTok out) — keyword-heavy
  complex_reasoning → Sonnet ($3.00/MTok in, $15.00/MTok out) — nuanced
  specialist     → Sonnet  ($3.00/MTok in, $15.00/MTok out) — chain-of-thought
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TaskType(str, Enum):
    """Task types for model routing."""
    SIMPLE_LOOKUP = "simple_lookup"
    CLASSIFICATION = "classification"
    COMPLEX_REASONING = "complex_reasoning"
    SPECIALIST = "specialist"


class ModelId(str, Enum):
    """Supported model identifiers."""
    HAIKU = "claude-3-5-haiku-20241022"
    SONNET = "claude-sonnet-4-20250514"


@dataclass(frozen=True)
class ModelPricing:
    """Per-million-token pricing."""
    input_per_mtok: float
    output_per_mtok: float
    cache_write_per_mtok: float
    cache_read_per_mtok: float


@dataclass(frozen=True)
class TaskModelConfig:
    """Configuration for a task's model assignment."""
    task_type: TaskType
    model_id: ModelId
    max_tokens: int
    temperature: float
    justification: str


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
# Task → Model Mapping
# ---------------------------------------------------------------------------

TASK_CONFIGS: dict[TaskType, TaskModelConfig] = {
    TaskType.SIMPLE_LOOKUP: TaskModelConfig(
        task_type=TaskType.SIMPLE_LOOKUP,
        model_id=ModelId.HAIKU,
        max_tokens=512,
        temperature=0.0,
        justification=(
            "Order/account lookups are deterministic data retrieval — "
            "Haiku is 3.75x cheaper ($0.80 vs $3.00/MTok input) and 2.5x faster"
        ),
    ),
    TaskType.CLASSIFICATION: TaskModelConfig(
        task_type=TaskType.CLASSIFICATION,
        model_id=ModelId.HAIKU,
        max_tokens=300,
        temperature=0.0,
        justification=(
            "Keyword-heavy intent classification doesn't need deep reasoning — "
            "Haiku handles it with >90% accuracy at a fraction of the cost"
        ),
    ),
    TaskType.COMPLEX_REASONING: TaskModelConfig(
        task_type=TaskType.COMPLEX_REASONING,
        model_id=ModelId.SONNET,
        max_tokens=2048,
        temperature=0.3,
        justification=(
            "Nuanced customer responses, multi-step reasoning, and empathetic "
            "drafting require Sonnet's deeper understanding"
        ),
    ),
    TaskType.SPECIALIST: TaskModelConfig(
        task_type=TaskType.SPECIALIST,
        model_id=ModelId.SONNET,
        max_tokens=1024,
        temperature=0.2,
        justification=(
            "Chain-of-thought analysis for ambiguous multi-category queries "
            "needs Sonnet's reasoning capability"
        ),
    ),
}


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

class ModelRouter:
    """
    Routes tasks to the appropriate model.

    Uses the task type to look up the pre-configured model assignment.
    Falls back to Sonnet for unknown task types (safe default).
    """

    def __init__(self):
        self._configs = TASK_CONFIGS.copy()

    def get_config(self, task_type: TaskType) -> TaskModelConfig:
        """Get the model configuration for a task type."""
        return self._configs.get(task_type, self._configs[TaskType.COMPLEX_REASONING])

    def get_model_name(self, task_type: TaskType) -> str:
        """Get the model identifier for a task type."""
        return self.get_config(task_type).model_id.value

    def get_max_tokens(self, task_type: TaskType) -> int:
        """Get the max tokens for a task type."""
        return self.get_config(task_type).max_tokens

    def get_temperature(self, task_type: TaskType) -> float:
        """Get the temperature for a task type."""
        return self.get_config(task_type).temperature

    def classify_intent(self, user_message: str) -> TaskType:
        """
        Classify a user message into a task type for model routing.

        This is a fast, deterministic classifier (not LLM-based) used
        to decide which model to use for the main agent loop.
        """
        msg = user_message.lower()

        # Order/account lookups → Haiku
        if any(w in msg for w in ["order", "ord-", "tracking", "shipment", "delivery status"]):
            return TaskType.SIMPLE_LOOKUP
        if any(w in msg for w in ["account", "acc-", "billing", "subscription", "plan", "invoice"]):
            return TaskType.SIMPLE_LOOKUP

        # Simple FAQ questions → Haiku (classification + KB lookup)
        if any(w in msg for w in ["return policy", "shipping time", "warranty", "payment method"]):
            return TaskType.CLASSIFICATION

        # Everything else → Sonnet (needs reasoning)
        return TaskType.COMPLEX_REASONING

    def format_justifications(self) -> str:
        """Format all model justifications for documentation."""
        lines = []
        for task_type, config in self._configs.items():
            model_name = "Haiku" if config.model_id == ModelId.HAIKU else "Sonnet"
            lines.append(f"  {task_type.value:<25} → {model_name:<8} — {config.justification}")
        return "\n".join(lines)


def calculate_cost(
    model_id: ModelId,
    input_tokens: int,
    output_tokens: int,
    cache_write_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float:
    """Calculate the cost of a single API call in USD."""
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
