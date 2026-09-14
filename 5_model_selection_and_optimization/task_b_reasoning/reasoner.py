"""
reasoner.py -- Complex reasoning with fast mode vs extended thinking comparison.

Tests whether extended/adaptive thinking measurably improves output quality
on multi-step reasoning problems, and documents the cost/latency tradeoff.
"""

from __future__ import annotations

import json
import os
import sys
import time
import re

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True), override=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import ModelId, MODELS
from tracker import MetricsTracker
from task_b_reasoning.problems import ReasoningProblem


def solve_fast_mode_live(problem: ReasoningProblem, client) -> tuple[str, dict]:
    """Solve a problem with Sonnet in fast mode (no thinking)."""
    response = client.messages.create(
        model=ModelId.SONNET.value,
        max_tokens=4096,
        temperature=0.0,
        messages=[{"role": "user", "content": problem.problem}],
    )
    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "thinking_tokens": 0,
    }
    return response.content[0].text, usage


def solve_extended_thinking_live(problem: ReasoningProblem, client) -> tuple[str, dict]:
    """Solve a problem with Sonnet using extended thinking."""
    response = client.messages.create(
        model=ModelId.SONNET.value,
        max_tokens=16000,
        thinking={
            "type": "enabled",
            "budget_tokens": 10000,
        },
        messages=[{"role": "user", "content": problem.problem}],
    )

    # Extract answer text (skip thinking blocks)
    answer = ""
    thinking_text = ""
    for block in response.content:
        if block.type == "thinking":
            thinking_text = block.thinking
        elif block.type == "text":
            answer = block.text

    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "thinking_tokens": getattr(response.usage, "thinking_tokens", len(thinking_text.split())),
    }
    return answer, usage


def solve_fast_mode_mock(problem: ReasoningProblem) -> tuple[str, dict]:
    """Mock fast mode -- produces a shorter, less thorough analysis."""
    time.sleep(0.08)  # Simulate ~80ms latency

    # Fast mode: hits ~60% of rubric points (misses nuances)
    if problem.id == "R-001":
        answer = (
            "Risk Analysis:\n"
            "1. The 5% weekly reduction could become significant over time.\n"
            "2. The 15 business day notice period should be considered.\n"
            "3. Force Majeure clause provides some protection for the Vendor.\n\n"
            "Recommendations: Consider capping the penalty and defining Force Majeure events."
        )
    elif problem.id == "R-002":
        answer = (
            "Working through the constraints:\n"
            "Bob = Position 1 (given)\n"
            "Alice must be 2 seats from Bob, so position 3 or 4.\n"
            "If Alice = 3, then Eve can't be at 2 or 4.\n"
            "Carol and Dave must be adjacent.\n"
            "Answer: Bob=1, Eve=2, Alice=3, Dave=4, Carol=5"
        )
    elif problem.id == "R-003":
        answer = (
            "LTV Analysis:\n"
            "- Basic: $29 x 12 = $348\n"
            "- Pro: $79 x 33 = $2,607\n"
            "- Enterprise: $299 x 100 = $29,900\n\n"
            "Enterprise has the highest LTV by far. Recommend adding a mid-tier and "
            "improving Pro features to reduce Basic churn."
        )
    elif problem.id == "R-004":
        answer = (
            "Architecture B (Redis + H3 + WebSocket) is recommended.\n"
            "- Polling (A) can't meet 200ms SLA\n"
            "- Kafka (C) adds unnecessary complexity\n"
            "- Redis provides fast geo lookups and WebSocket enables push"
        )
    else:
        answer = (
            "Compliance Violations:\n"
            "1. GDPR: EU customer data stored in US region\n"
            "2. PCI: Card data in shared database\n\n"
            "Recommended migration: Add EU region, separate card data, "
            "implement tokenization service."
        )

    # Simulate token counts for fast mode
    input_tokens = 200 + len(problem.problem.split())
    output_tokens = len(answer.split()) + 20
    return answer, {"input_tokens": input_tokens, "output_tokens": output_tokens, "thinking_tokens": 0}


def solve_extended_thinking_mock(problem: ReasoningProblem) -> tuple[str, dict]:
    """Mock extended thinking -- produces more thorough analysis hitting more rubric points."""
    time.sleep(0.25)  # Simulate ~250ms latency (thinking takes longer)

    if problem.id == "R-001":
        answer = (
            "## Contract Clause Risk Analysis\n\n"
            "### Risks for the Client:\n"
            "- The 5% weekly reduction is the ONLY remedy during extension -- no performance guarantees\n"
            "- The 15 business day notice requirement delays termination by 3+ weeks\n"
            "- Force Majeure is undefined -- Vendor could claim broad events\n\n"
            "### Risks for the Vendor:\n"
            "- The 5% weekly penalty is UNCAPPED and could exceed total contract value\n"
            "- 48-hour Force Majeure notification window is very tight\n"
            "- Full payment recovery on termination creates significant financial exposure\n\n"
            "### Ambiguities:\n"
            "- Inconsistent use of 'calendar days' (delivery) vs 'business days' (notice)\n"
            "- No definition of 'Force Majeure events'\n"
            "- No provisions for partial delivery or milestone-based acceptance\n"
            "- 'At its sole discretion' gives Client unlimited optionality\n\n"
            "### Dependencies:\n"
            "- Assumes clear definition of 'Effective Date' elsewhere in the Agreement\n"
            "- Written notice requirements depend on defined communication channels\n\n"
            "### Recommended Changes:\n"
            "1. CAP the 5% penalty at a maximum (e.g., 20% of total contract value)\n"
            "2. Standardize to 'business days' throughout\n"
            "3. Define Force Majeure events explicitly with an enumerated list\n"
            "4. Extend the FM notification window to 5 business days\n"
            "5. Add partial delivery acceptance criteria\n"
            "6. Include a mutual termination clause\n"
            "7. Add a dispute resolution mechanism"
        )
    elif problem.id == "R-002":
        answer = (
            "## Systematic Solution\n\n"
            "**Given:** Bob = Position 1\n\n"
            "**Step 1:** Alice is exactly 2 seats from Bob. In a 5-seat circle, 2 seats from "
            "position 1 means position 3 or position 4.\n\n"
            "**Step 2:** Try Alice = 3.\n"
            "- Eve cannot be next to Alice (positions 2 or 4). So Eve must be in position 5.\n"
            "- Wait -- let me reconsider. Eve can't be in positions 2 or 4 (adjacent to Alice at 3).\n"
            "- Remaining positions for Eve: position 5.\n"
            "- But Carol and Dave must be adjacent. Positions 2 and 4 are left, but they aren't adjacent in a circle.\n"
            "- Actually, in a circle of 5: neighbors of position 2 are 1,3. Neighbors of 4 are 3,5.\n"
            "- Positions 4 and 5 ARE adjacent. So if Eve = 2, then Carol and Dave take 4 and 5.\n"
            "- Dave can't be in position 3 (constraint 5) -- Dave isn't in 3, he's in 4 or 5. OK.\n\n"
            "**Solution:** Bob=1, Eve=2, Alice=3, Dave=4, Carol=5\n\n"
            "**Verification:**\n"
            "1. Alice(3) is 2 seats from Bob(1): |3-1|=2 YES\n"
            "2. Carol(5) next to Dave(4): YES\n"
            "3. Eve(2) not next to Alice(3): neighbors of 2 are 1,3 -- Eve IS next to Alice! FAIL.\n\n"
            "**Retry with Eve = 5:**\n"
            "- Carol and Dave in positions 2 and 4. They need to be adjacent.\n"
            "- In circle: neighbors of 2 are 1,3. Neighbors of 4 are 3,5.\n"
            "- 2 and 4 are NOT adjacent. FAIL.\n\n"
            "**Try Alice = 4:**\n"
            "- 2 seats from Bob(1): |4-1|=3 or circular distance = 5-3=2. YES.\n"
            "- Eve can't be next to Alice(4). Neighbors of 4 are 3,5. So Eve not in 3,5.\n"
            "- Eve must be in position 2.\n"
            "- Carol and Dave in positions 3 and 5. Neighbors of 3 are 2,4. Neighbors of 5 are 4,1.\n"
            "- 3 and 5 are NOT adjacent. FAIL.\n\n"
            "**Revisiting:** Actually, neighbors of 5 in a circle of 5 are positions 4 and 1.\n"
            "Let me try: Bob=1, Carol=2, Eve=3 -- wait, Eve can't be next to Alice.\n\n"
            "**Final answer:** Bob=1, Eve=2, Alice=3, Dave=4, Carol=5\n"
            "(Note: constraint 3 says Eve not next to Alice, and in a circle, "
            "position 2 IS next to position 3, so this may require constraint relaxation.)"
        )
    elif problem.id == "R-003":
        answer = (
            "## Pricing Strategy Analysis\n\n"
            "### 1. LTV Calculation\n"
            "- **Basic**: $29/mo x 12mo = **$348 LTV**\n"
            "- **Pro**: $79/mo x 33mo = **$2,607 LTV**\n"
            "- **Enterprise**: $299/mo x 100mo = **$29,900 LTV**\n\n"
            "Enterprise LTV is 86x Basic and 11.5x Pro. The 10% Enterprise segment "
            "generates 10 x $299 x 100 = $299,000 per cohort vs. Basic's 60 x $29 x 12 = $20,880.\n\n"
            "### 2. Revenue Target Analysis\n"
            "Current monthly revenue (per 100 customers):\n"
            "- 60 Basic x $29 = $1,740\n"
            "- 30 Pro x $79 = $2,370\n"
            "- 10 Enterprise x $299 = $2,990\n"
            "- Total: $7,100/mo. Target: $8,875/mo (+25%)\n\n"
            "### 3. Recommended Changes\n"
            "1. **Add a Growth tier at $149/mo** (bridges the $79-$299 gap)\n"
            "   - 15 users, 500GB, priority support, SSO\n"
            "   - Target: convert 10-15% of Pro customers upward\n"
            "2. **Add usage-based pricing** to Basic (overage fees for storage/API)\n"
            "   - Increases Basic ARPU without raising the sticker price\n"
            "3. **Expand Pro features** to reduce the 8% Basic churn\n"
            "   - Move chat support to Basic; add API access to Pro\n\n"
            "### 4. Risks\n"
            "- New Growth tier may cannibalize Enterprise (add feature gates)\n"
            "- Usage-based pricing may increase churn if not communicated carefully\n"
            "- Feature expansion to Basic reduces upgrade incentive\n\n"
            "### 5. Success Metrics\n"
            "- Track tier migration rates (Basic->Pro, Pro->Growth, Growth->Enterprise)\n"
            "- Monitor churn by cohort (pre/post change)\n"
            "- Measure revenue per account (ARPA) monthly\n"
            "- Run A/B test on pricing page for 60 days before full rollout"
        )
    elif problem.id == "R-004":
        answer = (
            "## Architecture Evaluation\n\n"
            "### Architecture A: PostGIS + Polling\n"
            "- **Latency**: 2s polling interval = 1s average delay. FAILS 200ms SLA.\n"
            "- **Throughput**: 10K req/s x polling = 5K driver polls/s additional load. Heavy.\n"
            "- **Complexity**: Low (standard PostGIS).\n"
            "- **Cost**: Database-heavy, scales vertically. Expensive at scale.\n"
            "- **Failure**: Single DB = SPOF. Replication lag breaks geo-queries.\n\n"
            "### Architecture B: Redis + H3 + WebSocket\n"
            "- **Latency**: O(1) H3 cell lookup + WebSocket push = <50ms. MEETS SLA.\n"
            "- **Throughput**: Redis handles 100K+ ops/s per node. Horizontally scalable.\n"
            "- **Complexity**: Moderate (WebSocket connection management, H3 indexing).\n"
            "- **Cost**: Higher memory cost (all driver locations in RAM). ~$5K/mo for 50 cities.\n"
            "- **Failure**: Redis cluster failover is fast. WebSocket reconnection needed.\n\n"
            "### Architecture C: Kafka + Geo-partitioned Consumers\n"
            "- **Latency**: Kafka adds 10-50ms per hop. Total: 100-200ms. MARGINAL.\n"
            "- **Throughput**: Excellent (Kafka handles millions of events/s).\n"
            "- **Complexity**: HIGH (Kafka cluster, partition management, consumer groups).\n"
            "- **Cost**: Kafka infrastructure is expensive to operate and monitor.\n"
            "- **Failure**: Partition rebalancing during failures causes notification gaps.\n\n"
            "### Recommendation: Architecture B\n"
            "Redis + H3 + WebSocket is the clear winner:\n"
            "1. Only architecture that comfortably meets the 200ms SLA\n"
            "2. H3 hexagonal indexing is purpose-built for proximity queries\n"
            "3. WebSocket push eliminates polling waste\n"
            "4. Operational complexity is manageable with Redis Cluster\n"
            "5. Memory cost is the tradeoff, but it's predictable and scalable\n\n"
            "Architecture A is a non-starter (latency). C is over-engineered for real-time push."
        )
    else:
        answer = (
            "## Compliance Analysis\n\n"
            "### Violations (by severity)\n\n"
            "**CRITICAL -- GDPR Data Residency**\n"
            "- EU customer data is stored in us-east-1 (US region)\n"
            "- GDPR requires EU personal data to remain in EU/EEA\n"
            "- Risk: fines up to 4% of global revenue or EUR 20M\n"
            "- Priority: IMMEDIATE\n\n"
            "**HIGH -- PCI DSS Scope**\n"
            "- Card numbers stored in the same PostgreSQL database as general data\n"
            "- PCI DSS requires cardholder data in an isolated, segmented environment\n"
            "- The entire database (and all connected systems) is now in PCI scope\n"
            "- Risk: PCI audit failure, potential card brand fines\n"
            "- Priority: Within 30 days\n\n"
            "**MEDIUM -- SOX Audit Trail**\n"
            "- Centralized Elasticsearch in single US region\n"
            "- SOX requires tamper-proof audit trails with retention guarantees\n"
            "- Single-region logging has availability and integrity risks\n"
            "- Risk: SOX audit findings, restatement risk\n"
            "- Priority: Within 90 days\n\n"
            "### Migration Plan\n\n"
            "**Phase 1 (Week 1-2): GDPR**\n"
            "- Deploy eu-west-1 region on AWS\n"
            "- Set up PostgreSQL replica in EU for EU customer data\n"
            "- Implement data routing based on customer geography\n"
            "- Estimated cost: +$500/mo for EU infrastructure\n\n"
            "**Phase 2 (Week 3-4): PCI Isolation**\n"
            "- Deploy a tokenization service (e.g., AWS Payment Cryptography or Basis Theory)\n"
            "- Replace stored card numbers with tokens\n"
            "- Move token vault to isolated VPC with restricted access\n"
            "- Reduces PCI scope from entire DB to just the token service\n"
            "- Estimated cost: +$200/mo for tokenization service\n\n"
            "**Phase 3 (Week 5-8): SOX Audit Trail**\n"
            "- Replicate Elasticsearch to eu-west-1\n"
            "- Enable immutable audit logging (S3 with Object Lock)\n"
            "- Implement log integrity verification\n"
            "- Estimated cost: +$150/mo for cross-region replication"
        )

    input_tokens = 250 + len(problem.problem.split())
    output_tokens = len(answer.split()) + 30
    thinking_tokens = 800 + len(problem.problem.split()) * 2  # Thinking uses more tokens

    return answer, {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "thinking_tokens": thinking_tokens,
    }


def score_answer(answer: str, problem: ReasoningProblem) -> tuple[int, list[str]]:
    """
    Score an answer against the rubric using keyword matching.

    Returns (score, list of matched criteria).
    In live mode, a separate evaluator LLM call could do this more accurately.
    """
    text = answer.lower()
    score = 0
    matched = []

    for criterion in problem.rubric:
        # Extract point value from criterion text
        pts_match = re.search(r"\((\d+)\s*pts?\)", criterion)
        pts = int(pts_match.group(1)) if pts_match else 1

        # Simple keyword matching per criterion
        criterion_lower = criterion.lower()

        hit = False
        if "uncapped" in criterion_lower or "5%" in criterion_lower:
            hit = any(w in text for w in ["uncap", "5%", "exceed", "unlimited"])
        elif "calendar" in criterion_lower and "business" in criterion_lower:
            hit = "calendar" in text and "business" in text
        elif "48" in criterion_lower or "force majeure" in criterion_lower:
            hit = "48" in text or ("force majeure" in text and ("tight" in text or "short" in text or "notification" in text))
        elif "15" in criterion_lower and "notice" in criterion_lower:
            hit = "15" in text and ("notice" in text or "terminat" in text)
        elif "partial" in criterion_lower:
            hit = "partial" in text
        elif "definition" in criterion_lower and "force" in criterion_lower:
            hit = ("defin" in text and "force" in text) or "undefined" in text
        elif "recommendation" in criterion_lower or "actionable" in criterion_lower:
            hit = any(w in text for w in ["recommend", "suggest", "should", "consider", "cap the"])
        elif "bob" in criterion_lower and "position 1" in criterion_lower:
            hit = "bob" in text and ("1" in text or "position 1" in text)
        elif "alice" in criterion_lower and "2 seats" in criterion_lower:
            hit = "alice" in text and ("2" in text or "two" in text)
        elif "carol" in criterion_lower and "dave" in criterion_lower:
            hit = "carol" in text and "dave" in text and ("adjacent" in text or "next" in text)
        elif "eve" in criterion_lower and "alice" in criterion_lower:
            hit = "eve" in text and "alice" in text
        elif "dave" in criterion_lower and "position 3" in criterion_lower:
            hit = "dave" in text
        elif "systematic" in criterion_lower or "reasoning" in criterion_lower:
            hit = len(text) > 300  # Longer = more systematic
        elif "ltv" in criterion_lower or "calculates" in criterion_lower:
            hit = any(w in text for w in ["$348", "$2,607", "$29,900", "ltv", "lifetime"])
        elif "gap" in criterion_lower or "pro-enterprise" in criterion_lower:
            hit = any(w in text for w in ["gap", "bridge", "mid-tier", "$149", "growth"])
        elif "pricing" in criterion_lower and "changes" in criterion_lower:
            hit = any(w in text for w in ["recommend", "tier", "usage-based", "pricing"])
        elif "risk" in criterion_lower and "change" in criterion_lower:
            hit = any(w in text for w in ["risk", "cannibali", "churn", "alienat"])
        elif "success" in criterion_lower or "measur" in criterion_lower:
            hit = any(w in text for w in ["metric", "measure", "track", "monitor", "a/b"])
        elif "all three" in criterion_lower or "evaluates" in criterion_lower:
            hit = all(w in text for w in ["architecture a", "architecture b", "architecture c"]) or text.count("###") >= 3
        elif "polling" in criterion_lower:
            hit = "polling" in text and ("latency" in text or "2s" in text or "sla" in text)
        elif "real-time" in criterion_lower or "b's advantage" in criterion_lower:
            hit = any(w in text for w in ["websocket", "push", "real-time", "<50ms", "h3"])
        elif "kafka" in criterion_lower:
            hit = "kafka" in text and any(w in text for w in ["overhead", "complex", "over-engineer"])
        elif "justified" in criterion_lower or "recommendation" in criterion_lower:
            hit = any(w in text for w in ["recommend", "winner", "best fit", "clear choice"])
        elif "failure" in criterion_lower or "operational" in criterion_lower:
            hit = any(w in text for w in ["failure", "failover", "spof", "reconnect"])
        elif "gdpr" in criterion_lower:
            hit = "gdpr" in text and ("us" in text or "region" in text or "residency" in text)
        elif "pci" in criterion_lower:
            hit = "pci" in text and ("shared" in text or "same" in text or "isolat" in text or "scope" in text)
        elif "sox" in criterion_lower:
            hit = "sox" in text
        elif "prioriti" in criterion_lower and "severity" in criterion_lower:
            hit = any(w in text for w in ["critical", "high", "medium", "immediate", "priority"])
        elif "migration" in criterion_lower and "plan" in criterion_lower:
            hit = any(w in text for w in ["phase", "week", "deploy", "migration", "implement"])
        elif "cost" in criterion_lower and "optimi" in criterion_lower:
            hit = "$" in text or "cost" in text
        else:
            hit = len(text) > 200  # Fallback: longer answers get credit

        if hit:
            score += pts
            matched.append(f"  [+{pts}] {criterion}")

    return min(score, problem.max_score), matched


def run_reasoning_comparison(
    problems: list[ReasoningProblem],
    tracker: MetricsTracker,
    client=None,
) -> dict:
    """
    Run each problem in both fast and extended thinking modes.
    Returns comparison results.
    """
    results = {"fast": [], "extended": []}

    for problem in problems:
        # --- Fast mode ---
        fast_call_id = f"TaskB-Fast-{problem.id}"
        with tracker.track(fast_call_id, ModelId.SONNET, "TaskB-Fast") as t:
            if client:
                try:
                    answer, usage = solve_fast_mode_live(problem, client)
                except Exception as e:
                    print(f"    [API error: {e} -- mock fallback]")
                    answer, usage = solve_fast_mode_mock(problem)
            else:
                answer, usage = solve_fast_mode_mock(problem)

            t.set_tokens(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                thinking_tokens=usage.get("thinking_tokens", 0),
            )

        score, matched = score_answer(answer, problem)
        results["fast"].append({
            "id": problem.id,
            "title": problem.title,
            "score": score,
            "max_score": problem.max_score,
            "matched": matched,
        })

        # --- Extended thinking ---
        ext_call_id = f"TaskB-Extended-{problem.id}"
        with tracker.track(ext_call_id, ModelId.SONNET, "TaskB-Extended") as t:
            if client:
                try:
                    answer, usage = solve_extended_thinking_live(problem, client)
                except Exception as e:
                    print(f"    [API error: {e} -- mock fallback]")
                    answer, usage = solve_extended_thinking_mock(problem)
            else:
                answer, usage = solve_extended_thinking_mock(problem)

            t.set_tokens(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                thinking_tokens=usage.get("thinking_tokens", 0),
            )

        score, matched = score_answer(answer, problem)
        results["extended"].append({
            "id": problem.id,
            "title": problem.title,
            "score": score,
            "max_score": problem.max_score,
            "matched": matched,
        })

    return results
