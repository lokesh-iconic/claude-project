"""
tracer.py — Trace/logging instrumentation for diagnosing agent pipeline failures.

Wraps the agent pipeline to capture:
  - Every tool call with inputs and outputs
  - Field-level data flow between steps (detect dropped/mutated fields)
  - Priority assignments vs. ground truth
  - Escalation decisions
  - Anomaly detection (fields present in step A but missing in step B)

Produces structured JSON traces and a human-readable anomaly summary.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any


@dataclass
class ToolTrace:
    """A single tool invocation trace."""
    step: int
    tool_name: str
    inputs: dict
    outputs: dict
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class TicketTrace:
    """Complete trace for one ticket through the pipeline."""
    ticket_id: str
    ticket_subject: str
    ground_truth: dict
    tool_traces: list[ToolTrace] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)
    final_result: dict = field(default_factory=dict)


@dataclass
class PipelineTrace:
    """Complete trace for a full pipeline run."""
    system: str  # "broken" or "fixed"
    run_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    ticket_traces: list[TicketTrace] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


def analyze_ticket_trace(trace: TicketTrace) -> list[str]:
    """
    Analyze a ticket's trace for anomalies.

    Checks for:
    1. Dropped fields between classification and routing
    2. Priority mismatches vs. ground truth
    3. Missing escalation for ambiguous tickets
    4. Inconsistent data flow
    """
    anomalies = []

    classify_result = None
    route_input = None
    route_result = None

    for tt in trace.tool_traces:
        if tt.tool_name == "classify_ticket":
            classify_result = tt.outputs
        elif tt.tool_name == "escalate_to_specialist":
            classify_result = tt.outputs  # Specialist overrides classification
        elif tt.tool_name == "route_ticket":
            route_input = tt.inputs
            route_result = tt.outputs

    # Check 1: Dropped fields between classify → route
    if classify_result and route_input:
        if classify_result.get("is_ambiguous") and not route_input.get("is_ambiguous"):
            anomalies.append(
                f"DROPPED FIELD: classify output has is_ambiguous=True, "
                f"but route input has is_ambiguous={route_input.get('is_ambiguous', 'MISSING')}. "
                f"The ambiguity signal was lost between classification and routing."
            )

        # Check if priority was carried correctly
        if classify_result.get("priority") != route_input.get("priority"):
            anomalies.append(
                f"PRIORITY MISMATCH: classify output priority={classify_result.get('priority')}, "
                f"but route input priority={route_input.get('priority')}."
            )

    # Check 2: Priority vs. ground truth
    gt = trace.ground_truth
    if classify_result and gt:
        expected_priority = gt.get("priority")
        actual_priority = classify_result.get("priority")
        if expected_priority and actual_priority and expected_priority != actual_priority:
            anomalies.append(
                f"WRONG PRIORITY: Expected '{expected_priority}' (ground truth), "
                f"got '{actual_priority}'. The model's priority assignment doesn't "
                f"match the expected severity level."
            )

    # Check 3: Ambiguous ticket not escalated
    if gt.get("is_ambiguous") and route_result:
        if not route_result.get("escalate"):
            anomalies.append(
                f"MISSING ESCALATION: Ticket is ambiguous (ground truth), "
                f"but routing did not trigger escalation. "
                f"escalate={route_result.get('escalate')}."
            )

    return anomalies


def trace_pipeline_run(
    system_name: str,
    run_func,
    tickets,
) -> PipelineTrace:
    """
    Run a pipeline and capture traces.

    Args:
        system_name: "broken" or "fixed"
        run_func: The runner's process_ticket function
        tickets: List of Ticket objects

    Returns:
        PipelineTrace with all tool traces and anomalies
    """
    from shared import TicketResult

    pipeline_trace = PipelineTrace(system=system_name)
    priority_mismatches = 0
    escalation_failures = 0
    dropped_fields = 0

    for ticket in tickets:
        ticket_trace = TicketTrace(
            ticket_id=ticket.id,
            ticket_subject=ticket.subject,
            ground_truth=ticket.ground_truth,
        )

        # Run the pipeline and capture the mock agent's tool calls
        if system_name == "broken":
            from broken_app.runner import MockAgentLoop
            from broken_app.hooks import create_hooks
        else:
            from fixed_app.runner import MockAgentLoop
            from fixed_app.hooks import create_hooks

        hooks = create_hooks()
        mock_agent = MockAgentLoop(hooks)
        classification, routing, draft = mock_agent.process_ticket(ticket)

        # Record tool traces from the mock agent's log
        for i, call in enumerate(mock_agent.tool_calls_log):
            ticket_trace.tool_traces.append(ToolTrace(
                step=i + 1,
                tool_name=call["tool"],
                inputs=call["args"],
                outputs=call["result"],
            ))

        # Store final result
        ticket_trace.final_result = {
            "classification": classification,
            "routing": routing,
            "draft": {
                "subject_line": draft.get("subject_line", ""),
                "body_preview": draft.get("body", "")[:100] + "...",
            },
        }

        # Analyze for anomalies
        ticket_trace.anomalies = analyze_ticket_trace(ticket_trace)

        # Count anomaly types
        for anomaly in ticket_trace.anomalies:
            if "WRONG PRIORITY" in anomaly:
                priority_mismatches += 1
            if "MISSING ESCALATION" in anomaly:
                escalation_failures += 1
            if "DROPPED FIELD" in anomaly:
                dropped_fields += 1

        pipeline_trace.ticket_traces.append(ticket_trace)

    # Summary statistics
    total = len(tickets)
    anomalous = sum(1 for t in pipeline_trace.ticket_traces if t.anomalies)
    pipeline_trace.summary = {
        "total_tickets": total,
        "tickets_with_anomalies": anomalous,
        "anomaly_rate": f"{anomalous / total * 100:.1f}%",
        "priority_mismatches": priority_mismatches,
        "escalation_failures": escalation_failures,
        "dropped_fields": dropped_fields,
    }

    return pipeline_trace


def format_trace_report(trace: PipelineTrace) -> str:
    """Format a pipeline trace as a human-readable report."""
    lines = []
    lines.append(f"\n{'='*70}")
    lines.append(f"  TRACE REPORT — {trace.system.upper()} SYSTEM")
    lines.append(f"  Run: {trace.run_timestamp}")
    lines.append(f"{'='*70}\n")

    # Summary
    s = trace.summary
    lines.append(f"  Summary:")
    lines.append(f"    Total tickets:         {s['total_tickets']}")
    lines.append(f"    With anomalies:        {s['tickets_with_anomalies']} ({s['anomaly_rate']})")
    lines.append(f"    Priority mismatches:   {s['priority_mismatches']}")
    lines.append(f"    Escalation failures:   {s['escalation_failures']}")
    lines.append(f"    Dropped fields:        {s['dropped_fields']}")
    lines.append("")

    # Per-ticket details (only anomalous tickets)
    anomalous = [t for t in trace.ticket_traces if t.anomalies]
    if anomalous:
        lines.append(f"  {'─'*66}")
        lines.append(f"  ANOMALOUS TICKETS ({len(anomalous)}):")
        lines.append(f"  {'─'*66}\n")

        for tt in anomalous:
            lines.append(f"  [{tt.ticket_id}] {tt.ticket_subject}")
            lines.append(f"    Ground truth: category={tt.ground_truth.get('category')}, "
                         f"priority={tt.ground_truth.get('priority')}, "
                         f"ambiguous={tt.ground_truth.get('is_ambiguous')}")

            # Show tool call chain
            lines.append(f"    Tool chain:")
            for step in tt.tool_traces:
                lines.append(f"      Step {step.step}: {step.tool_name}")
                if step.tool_name == "classify_ticket" or step.tool_name == "escalate_to_specialist":
                    lines.append(f"        → category={step.outputs.get('category')}, "
                                 f"priority={step.outputs.get('priority')}, "
                                 f"is_ambiguous={step.outputs.get('is_ambiguous')}")
                elif step.tool_name == "route_ticket":
                    lines.append(f"        inputs: is_ambiguous={step.inputs.get('is_ambiguous')}")
                    lines.append(f"        → team={step.outputs.get('team')}, "
                                 f"escalate={step.outputs.get('escalate')}")

            # Show anomalies
            lines.append(f"    ⚠ Anomalies:")
            for anomaly in tt.anomalies:
                lines.append(f"      • {anomaly}")
            lines.append("")

    else:
        lines.append("  ✅ No anomalies detected.\n")

    return "\n".join(lines)


def save_trace(trace: PipelineTrace, filepath: str) -> None:
    """Save a pipeline trace to a JSON file."""
    # Convert dataclass to dict, handling nested dataclasses
    def _to_dict(obj: Any) -> Any:
        if hasattr(obj, "__dataclass_fields__"):
            return {k: _to_dict(v) for k, v in asdict(obj).items()}
        elif isinstance(obj, list):
            return [_to_dict(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: _to_dict(v) for k, v in obj.items()}
        return obj

    data = _to_dict(trace)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


import os  # needed for save_trace
