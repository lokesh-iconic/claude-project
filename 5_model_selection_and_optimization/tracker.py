"""
tracker.py -- Unified token/cost/latency tracker.

Captures per-call metrics and produces formatted summary tables.
Works identically in mock and live modes -- cost calculations use
real pricing regardless of whether the API was actually called.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from models import ModelId, calculate_cost, format_cost, MODELS


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
    thinking_tokens: int = 0
    latency_seconds: float = 0.0
    cost_usd: float = 0.0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.cost_usd == 0.0:
            self.cost_usd = calculate_cost(
                self.model_id,
                self.input_tokens,
                self.output_tokens,
                self.cache_write_tokens,
                self.cache_read_tokens,
            )


@dataclass
class TaskSummary:
    """Aggregated metrics for a task."""
    task_name: str
    model_id: ModelId
    total_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_write_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_thinking_tokens: int = 0
    total_cost_usd: float = 0.0
    total_latency_seconds: float = 0.0
    avg_latency_seconds: float = 0.0
    avg_cost_per_call: float = 0.0
    throughput_calls_per_sec: float = 0.0


class MetricsTracker:
    """
    Collects per-call metrics and produces summaries.

    Usage:
        tracker = MetricsTracker()
        with tracker.track("call-1", ModelId.HAIKU, "classification") as t:
            # ... make API call or mock ...
            t.set_tokens(input=150, output=30)
        tracker.print_summary()
    """

    def __init__(self):
        self.calls: list[CallMetrics] = []

    def track(self, call_id: str, model_id: ModelId, task: str) -> CallTracker:
        """Start tracking a call. Use as a context manager."""
        return CallTracker(self, call_id, model_id, task)

    def record(self, metrics: CallMetrics) -> None:
        """Record a completed call's metrics."""
        self.calls.append(metrics)

    def get_task_summary(self, task: str) -> Optional[TaskSummary]:
        """Get aggregated metrics for a specific task."""
        task_calls = [c for c in self.calls if c.task == task]
        if not task_calls:
            return None

        model_id = task_calls[0].model_id
        total_latency = sum(c.latency_seconds for c in task_calls)
        total_cost = sum(c.cost_usd for c in task_calls)
        n = len(task_calls)

        return TaskSummary(
            task_name=task,
            model_id=model_id,
            total_calls=n,
            total_input_tokens=sum(c.input_tokens for c in task_calls),
            total_output_tokens=sum(c.output_tokens for c in task_calls),
            total_cache_write_tokens=sum(c.cache_write_tokens for c in task_calls),
            total_cache_read_tokens=sum(c.cache_read_tokens for c in task_calls),
            total_thinking_tokens=sum(c.thinking_tokens for c in task_calls),
            total_cost_usd=total_cost,
            total_latency_seconds=total_latency,
            avg_latency_seconds=total_latency / n if n else 0,
            avg_cost_per_call=total_cost / n if n else 0,
            throughput_calls_per_sec=n / total_latency if total_latency > 0 else 0,
        )

    def get_all_summaries(self) -> list[TaskSummary]:
        """Get summaries for all tracked tasks."""
        tasks = sorted(set(c.task for c in self.calls))
        return [s for t in tasks if (s := self.get_task_summary(t)) is not None]

    def format_calls_table(self, task: Optional[str] = None) -> str:
        """Format per-call metrics as a table."""
        calls = [c for c in self.calls if task is None or c.task == task]
        if not calls:
            return "  No calls recorded.\n"

        lines = []
        lines.append(f"  {'Call ID':<20} {'Model':<22} {'In Tok':>8} {'Out Tok':>8} "
                      f"{'Cache W':>8} {'Cache R':>8} {'Think':>7} "
                      f"{'Latency':>8} {'Cost':>10}")
        lines.append(f"  {'─'*111}")

        for c in calls:
            model_name = MODELS[c.model_id].display_name[:20]
            lines.append(
                f"  {c.call_id:<20} {model_name:<22} {c.input_tokens:>8,} {c.output_tokens:>8,} "
                f"{c.cache_write_tokens:>8,} {c.cache_read_tokens:>8,} {c.thinking_tokens:>7,} "
                f"{c.latency_seconds:>7.2f}s {format_cost(c.cost_usd):>10}"
            )

        return "\n".join(lines)

    def format_summary_table(self) -> str:
        """Format task-level summaries as a comparison table."""
        summaries = self.get_all_summaries()
        if not summaries:
            return "  No tasks recorded.\n"

        lines = []
        lines.append(f"  {'Task':<30} {'Model':<22} {'Calls':>6} {'Tokens':>10} "
                      f"{'Avg Latency':>12} {'Avg Cost':>10} {'Total Cost':>11} {'Throughput':>12}")
        lines.append(f"  {'─'*115}")

        for s in summaries:
            model_name = MODELS[s.model_id].display_name[:20]
            total_tokens = s.total_input_tokens + s.total_output_tokens
            lines.append(
                f"  {s.task_name:<30} {model_name:<22} {s.total_calls:>6} {total_tokens:>10,} "
                f"{s.avg_latency_seconds:>11.2f}s {format_cost(s.avg_cost_per_call):>10} "
                f"{format_cost(s.total_cost_usd):>11} {s.throughput_calls_per_sec:>10.1f}/s"
            )

        return "\n".join(lines)


class CallTracker:
    """Context manager for tracking a single API call."""

    def __init__(self, tracker: MetricsTracker, call_id: str, model_id: ModelId, task: str):
        self._tracker = tracker
        self._call_id = call_id
        self._model_id = model_id
        self._task = task
        self._start_time = 0.0
        self._input_tokens = 0
        self._output_tokens = 0
        self._cache_write_tokens = 0
        self._cache_read_tokens = 0
        self._thinking_tokens = 0
        self._metadata: dict = {}

    def __enter__(self) -> CallTracker:
        self._start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        elapsed = time.perf_counter() - self._start_time
        metrics = CallMetrics(
            call_id=self._call_id,
            model_id=self._model_id,
            task=self._task,
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
            cache_write_tokens=self._cache_write_tokens,
            cache_read_tokens=self._cache_read_tokens,
            thinking_tokens=self._thinking_tokens,
            latency_seconds=elapsed,
            metadata=self._metadata,
        )
        self._tracker.record(metrics)

    def set_tokens(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_write_tokens: int = 0,
        cache_read_tokens: int = 0,
        thinking_tokens: int = 0,
    ) -> None:
        """Set token counts from API response usage."""
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self._cache_write_tokens = cache_write_tokens
        self._cache_read_tokens = cache_read_tokens
        self._thinking_tokens = thinking_tokens

    def set_metadata(self, **kwargs) -> None:
        """Attach arbitrary metadata to this call."""
        self._metadata.update(kwargs)
