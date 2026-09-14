"""
problems.py -- 5 complex reasoning problems for extended thinking evaluation.

Each problem requires multi-step analysis, has a known correct answer,
and includes a scoring rubric (0-10) for evaluating response quality.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ReasoningProblem:
    """A complex problem with a rubric for evaluating answer quality."""
    id: str
    title: str
    problem: str
    expected_answer: str
    rubric: list[str]  # Scoring criteria (each worth points)
    max_score: int = 10


PROBLEMS: list[ReasoningProblem] = [
    ReasoningProblem(
        id="R-001",
        title="Contract Risk Analysis",
        problem="""\
Analyze the following contract clause and identify ALL risks, dependencies, and recommended actions.

CLAUSE: "The Vendor shall deliver the Software no later than 90 calendar days after the Effective Date.
If the Vendor fails to deliver within this period, the Client may, at its sole discretion, either
(a) extend the deadline by an additional 30 days with a 5% reduction in the total contract price per
week of delay, or (b) terminate the Agreement and recover all payments made, provided that the Client
has given written notice of its intent to terminate at least 15 business days before the termination
takes effect. Notwithstanding the foregoing, the Vendor shall not be liable for delays caused by
Force Majeure events, provided that the Vendor notifies the Client within 48 hours of the occurrence
of such event."

Identify: (1) risks for both parties, (2) ambiguities, (3) dependencies, (4) recommended changes.""",
        expected_answer="Key risks: unlimited 5% weekly penalty can exceed contract value; 15-business-day notice period creates gap; 48-hour force majeure notification is short; no cap on liability; ambiguity on 'calendar days' vs 'business days' inconsistency; no definition of Force Majeure events; no partial delivery terms.",
        rubric=[
            "Identifies the uncapped 5%/week penalty risk (2 pts)",
            "Spots the calendar vs business days inconsistency (2 pts)",
            "Notes the 48-hour force majeure notification window (1 pt)",
            "Identifies the 15-day notice gap for termination (1 pt)",
            "Mentions lack of partial delivery provisions (1 pt)",
            "Notes missing Force Majeure definition (1 pt)",
            "Provides actionable recommendations (2 pts)",
        ],
    ),
    ReasoningProblem(
        id="R-002",
        title="Multi-Step Logic Puzzle",
        problem="""\
Five people (Alice, Bob, Carol, Dave, Eve) sit around a circular table. Determine each person's
position (1-5, clockwise) given these constraints:

1. Alice sits exactly two seats from Bob (in either direction around the circle)
2. Carol sits directly next to Dave
3. Eve does NOT sit next to Alice
4. Bob sits in position 1
5. Dave does NOT sit in position 3

What is each person's position?""",
        expected_answer="Bob=1, Alice=3, Eve=2, Carol=5, Dave=4 (or equivalent valid arrangement). Key: Bob at 1, Alice must be at 3 or 4 (two away). If Alice=3, then Eve can't be at 2 or 4 (next to Alice). Carol-Dave adjacent. Working through: Bob=1, Eve=2, Alice=3, Dave=4, Carol=5.",
        rubric=[
            "Correctly places Bob at position 1 (1 pt)",
            "Alice exactly 2 seats from Bob (2 pts)",
            "Carol adjacent to Dave (2 pts)",
            "Eve not adjacent to Alice (2 pts)",
            "Dave not in position 3 (1 pt)",
            "Shows systematic reasoning/work (2 pts)",
        ],
    ),
    ReasoningProblem(
        id="R-003",
        title="Pricing Strategy Analysis",
        problem="""\
A SaaS company has three pricing tiers:

- Basic: $29/mo, 1 user, 10GB storage, email support
- Pro: $79/mo, 5 users, 100GB storage, chat support, API access
- Enterprise: $299/mo, unlimited users, 1TB storage, dedicated support, SSO, audit log

Current customer distribution: 60% Basic, 30% Pro, 10% Enterprise
Monthly churn: Basic 8%, Pro 3%, Enterprise 1%
Average customer lifetime: Basic 12mo, Pro 33mo, Enterprise 100mo

The company wants to increase revenue by 25% without increasing churn.

Analyze: (1) Which tier has the highest LTV? (2) What pricing/packaging changes would you recommend?
(3) What risks does each change carry? (4) How would you measure success?""",
        expected_answer="Enterprise LTV=$29,900, Pro LTV=$2,607, Basic LTV=$348. Strategy: introduce a mid-tier at ~$149 to bridge Pro-Enterprise gap; add usage-based pricing; expand Pro features to reduce Basic churn. Risks: alienating existing customers, feature cannibalization. Measure: track tier migration, churn by cohort, revenue per account.",
        rubric=[
            "Correctly calculates LTV for each tier (3 pts)",
            "Identifies the Pro-Enterprise price gap as an opportunity (1 pt)",
            "Proposes actionable pricing changes (2 pts)",
            "Identifies risks of each proposed change (2 pts)",
            "Specifies measurable success criteria (2 pts)",
        ],
    ),
    ReasoningProblem(
        id="R-004",
        title="System Design Tradeoff",
        problem="""\
You're designing a notification system for a ride-sharing app that needs to:
- Send push notifications to drivers within 500m of a new ride request
- Handle 10,000 concurrent ride requests per second at peak
- Deliver notifications within 200ms of the request
- Handle driver location updates every 5 seconds
- Work across 50 cities globally

Evaluate these three architectures and recommend one with justification:

A) Geospatial database (PostGIS) with polling: drivers poll every 2 seconds
B) In-memory geospatial index (Redis + H3) with WebSocket push
C) Event-driven with Apache Kafka + geo-partitioned consumers

For each: latency, throughput, operational complexity, cost, failure modes.""",
        expected_answer="Architecture B (Redis + H3 + WebSocket) is the best fit. Redis H3 indexing gives O(1) geo lookups; WebSocket push meets 200ms SLA without polling overhead; operational complexity is moderate. Architecture A fails on latency (polling = 2s). Architecture C adds Kafka overhead that's unnecessary for real-time push. Key tradeoff: B has higher memory cost but meets all requirements.",
        rubric=[
            "Evaluates all three architectures (2 pts)",
            "Correctly identifies polling latency issue with A (1 pt)",
            "Identifies B's advantages for real-time push (2 pts)",
            "Discusses Kafka overhead for C (1 pt)",
            "Makes a clear, justified recommendation (2 pts)",
            "Addresses failure modes and operational concerns (2 pts)",
        ],
    ),
    ReasoningProblem(
        id="R-005",
        title="Regulatory Compliance Chain",
        problem="""\
A fintech startup processes payments in the US and EU. They've received the following requirements:

1. PCI DSS Level 1 compliance for card processing
2. GDPR data residency: EU customer data must stay in EU
3. SOX audit trail for all financial transactions
4. The startup uses AWS and wants to minimize infrastructure cost

They currently have:
- One AWS region (us-east-1) running everything
- A single PostgreSQL database with all customer data
- Card numbers stored encrypted in the same database
- Logs shipped to a centralized Elasticsearch cluster in us-east-1

Identify ALL compliance violations in the current setup, prioritize them by severity,
and provide a migration plan that addresses each violation while minimizing cost.""",
        expected_answer="Violations: (1) GDPR - EU data in US region (critical); (2) PCI - card data in same DB as general data (high); (3) SOX - centralized logs in single region (medium). Migration: add eu-west-1 region for EU data; isolate card data in separate PCI-scoped environment (could use tokenization service); implement multi-region log replication. Prioritize GDPR first (regulatory fines), then PCI (breach risk), then SOX.",
        rubric=[
            "Identifies GDPR data residency violation (2 pts)",
            "Identifies PCI scope issue with shared database (2 pts)",
            "Identifies SOX audit trail gaps (1 pt)",
            "Correctly prioritizes by severity (2 pts)",
            "Provides a practical migration plan (2 pts)",
            "Considers cost optimization in the plan (1 pt)",
        ],
    ),
]
