"""
run_comparison.py — Run both systems against the full ticket set and compare.

Executes:
  1. Workflow pipeline (deterministic 3-step chain)
  2. Agent system (tool-calling loop with hooks + subagent)
  3. PydanticAI classifier (framework comparison)

Then produces a comparison table showing where outputs diverge.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

# Force UTF-8 on Windows
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv, find_dotenv

# Ensure .env is loaded from workspace root
load_dotenv(find_dotenv(usecwd=True))

# Ensure the package root is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tickets import TICKETS, Ticket
from shared import TicketResult
from workflow.pipeline import run_all as run_workflow
from agent.runner import run_all as run_agent
from pydantic_ai_component.classifier import run_all as run_pydantic_classifier


def compare_results(
    workflow_results: list[TicketResult],
    agent_results: list[TicketResult],
    pydantic_classifications: list,
) -> str:
    """
    Build a markdown comparison table.

    Highlights divergences between workflow and agent outputs.
    """
    lines = []
    lines.append("# Comparison: Workflow vs Agent\n")
    lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")

    # ── Summary Statistics ──
    lines.append("## Summary\n")

    # Count divergences
    cat_divergences = 0
    route_divergences = 0
    priority_divergences = 0
    escalation_divergences = 0

    for wf, ag in zip(workflow_results, agent_results):
        if wf.classification.category != ag.classification.category:
            cat_divergences += 1
        if wf.routing.team != ag.routing.team:
            route_divergences += 1
        if wf.classification.priority != ag.classification.priority:
            priority_divergences += 1
        if wf.routing.escalate != ag.routing.escalate:
            escalation_divergences += 1

    lines.append(f"| Metric | Count |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total tickets | {len(workflow_results)} |")
    lines.append(f"| Category divergences | {cat_divergences} |")
    lines.append(f"| Priority divergences | {priority_divergences} |")
    lines.append(f"| Routing divergences | {route_divergences} |")
    lines.append(f"| Escalation divergences | {escalation_divergences} |")
    lines.append("")

    # ── Per-Ticket Comparison ──
    lines.append("## Per-Ticket Results\n")
    lines.append(
        "| Ticket | Subject | WF Category | Agent Category | WF Team | Agent Team | "
        "WF Priority | Agent Priority | Diverged? |"
    )
    lines.append(
        "|--------|---------|-------------|----------------|---------|------------|"
        "------------|----------------|-----------|"
    )

    for wf, ag in zip(workflow_results, agent_results):
        ticket = next((t for t in TICKETS if t.id == wf.ticket_id), None)
        subject = (ticket.subject[:30] + "...") if ticket and len(ticket.subject) > 30 else (ticket.subject if ticket else "?")

        wf_cat = wf.classification.category.value
        ag_cat = ag.classification.category.value
        wf_team = wf.routing.team.value
        ag_team = ag.routing.team.value
        wf_pri = wf.classification.priority.value
        ag_pri = ag.classification.priority.value

        diverged = wf_cat != ag_cat or wf_team != ag_team or wf_pri != ag_pri
        diverge_marker = "!! YES" if diverged else "OK No"

        # Bold divergent cells
        cat_wf = f"**{wf_cat}**" if wf_cat != ag_cat else wf_cat
        cat_ag = f"**{ag_cat}**" if wf_cat != ag_cat else ag_cat
        team_wf = f"**{wf_team}**" if wf_team != ag_team else wf_team
        team_ag = f"**{ag_team}**" if wf_team != ag_team else ag_team
        pri_wf = f"**{wf_pri}**" if wf_pri != ag_pri else wf_pri
        pri_ag = f"**{ag_pri}**" if wf_pri != ag_pri else ag_pri

        lines.append(
            f"| {wf.ticket_id} | {subject} | {cat_wf} | {cat_ag} | "
            f"{team_wf} | {team_ag} | {pri_wf} | {pri_ag} | {diverge_marker} |"
        )

    lines.append("")

    # ── PydanticAI Comparison ──
    lines.append("## PydanticAI Classifier vs Hand-Rolled\n")
    lines.append("| Ticket | Hand-Rolled Category | PydanticAI Category | Match? |")
    lines.append("|--------|---------------------|---------------------|--------|")

    for wf, pai in zip(workflow_results, pydantic_classifications):
        wf_cat = wf.classification.category.value
        pai_cat = pai.category.value
        match = "OK" if wf_cat == pai_cat else "!!"
        lines.append(f"| {wf.ticket_id} | {wf_cat} | {pai_cat} | {match} |")

    lines.append("")

    # ── Divergence Analysis ──
    lines.append("## Divergence Analysis\n")

    lines.append("### Where the Agent's Flexibility Helped\n")
    for wf, ag in zip(workflow_results, agent_results):
        ticket = next((t for t in TICKETS if t.id == wf.ticket_id), None)
        if not ticket:
            continue

        gt_cat = ticket.ground_truth.get("category", "")
        if (wf.classification.category.value != ag.classification.category.value
                and ag.classification.category.value == gt_cat):
            lines.append(
                f"- **{wf.ticket_id}**: Agent correctly classified as `{gt_cat}` "
                f"(workflow said `{wf.classification.category.value}`). "
                f"The agent used the specialist subagent for deeper analysis."
            )

        if ticket.ground_truth.get("is_ambiguous") and ag.classification.is_ambiguous:
            lines.append(
                f"- **{ag.ticket_id}**: Agent correctly flagged as ambiguous and "
                f"escalated to specialist subagent."
            )

    lines.append("")
    lines.append("### Where the Workflow's Predictability Was Better\n")
    lines.append(
        "- **Cost**: The workflow makes exactly 3 API calls per ticket. The agent "
        "may make 4-6+ calls (classify + escalate + route + draft + potential retries)."
    )
    lines.append(
        "- **Latency**: Fixed pipeline = predictable execution time. The agent's "
        "loop introduces variable latency."
    )
    lines.append(
        "- **Auditability**: Each workflow step has a single, traceable prompt->response. "
        "The agent's reasoning is emergent and harder to audit."
    )
    lines.append(
        "- **Testing**: Workflow steps can be unit-tested independently with fixed inputs. "
        "Agent behavior depends on the model's tool-selection logic."
    )

    lines.append("")

    # ── Architectural Recommendation ──
    lines.append("## When to Use Which\n")
    lines.append("| Criterion | Workflow | Agent |")
    lines.append("|-----------|----------|-------|")
    lines.append("| Predictable inputs | [+] Best | Overkill |")
    lines.append("| Ambiguous/variable inputs | Limited | [+] Best |")
    lines.append("| Cost sensitivity | [+] Fewer API calls | More expensive |")
    lines.append("| Auditability requirements | [+] Fully traceable | Harder to audit |")
    lines.append("| Self-correction needed | Not possible | [+] Can re-classify |")
    lines.append("| Development speed | [+] Simpler to build | More complex |")
    lines.append("| Scalability | [+] Linear, predictable | Variable |")

    return "\n".join(lines)


def main():
    """Run the full comparison."""
    print("\n" + "=" * 60)
    print("  AGENTS & WORKFLOWS — FULL COMPARISON RUN")
    print("=" * 60)

    # 1. Run workflow
    workflow_results = run_workflow()

    # 2. Run agent
    agent_results, hook_stats = run_agent()

    # 3. Run PydanticAI classifier
    pydantic_results = run_pydantic_classifier()

    # 4. Generate comparison
    comparison_md = compare_results(workflow_results, agent_results, pydantic_results)

    # 5. Save results
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)

    # Save comparison markdown
    comparison_path = os.path.join(output_dir, "comparison.md")
    with open(comparison_path, "w", encoding="utf-8") as f:
        f.write(comparison_md)

    # Save raw results as JSON
    results_path = os.path.join(output_dir, "results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump({
            "workflow": [r.model_dump() for r in workflow_results],
            "agent": [r.model_dump() for r in agent_results],
            "pydantic_ai_classifications": [r.model_dump() for r in pydantic_results],
            "hook_stats": hook_stats,
            "timestamp": datetime.now().isoformat(),
        }, f, indent=2, default=str)

    # Print summary
    print("\n" + "=" * 60)
    print("  RESULTS SAVED")
    print("=" * 60)
    print(f"\n  [FILE] Comparison:  {comparison_path}")
    print(f"  [DATA] Raw results: {results_path}")

    # Print the comparison to stdout too
    print("\n" + comparison_md)

    # Hook stats
    print(f"\n--- Hook Statistics ---")
    print(json.dumps(hook_stats, indent=2))


if __name__ == "__main__":
    main()
