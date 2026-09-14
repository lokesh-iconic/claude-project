"""
summarizer.py -- Long-document summarization with prompt caching.

Demonstrates the cost difference between:
  - First call (cache write): full input cost + cache write cost
  - Subsequent calls (cache read): reduced cost via cached system prompt
  - Baseline (no cache): full cost every time
"""

from __future__ import annotations

import json
import os
import sys
import time

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True), override=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import ModelId, MODELS
from tracker import MetricsTracker
from task_c_summarization.documents import Document


SUMMARIZE_SYSTEM_PROMPT = """\
You are a document analyst. When given a document and a question, provide a clear, \
concise answer based solely on the document content. Include specific numbers, dates, \
and details from the document to support your answer."""

SUMMARIZE_USER_PROMPT = "Summarize this document in 3-4 paragraphs, highlighting the key findings, decisions, and action items."


def summarize_live_cached(
    document: Document,
    question: str,
    client,
) -> tuple[str, dict]:
    """Summarize with prompt caching enabled (live mode)."""
    response = client.messages.create(
        model=ModelId.SONNET.value,
        max_tokens=1024,
        system=[
            {"type": "text", "text": SUMMARIZE_SYSTEM_PROMPT},
            {
                "type": "text",
                "text": f"DOCUMENT:\n\n{document.content}",
                "cache_control": {"type": "ephemeral"},
            },
        ],
        messages=[{"role": "user", "content": question}],
    )

    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cache_write_tokens": getattr(response.usage, "cache_creation_input_tokens", 0),
        "cache_read_tokens": getattr(response.usage, "cache_read_input_tokens", 0),
    }

    return response.content[0].text, usage


def summarize_live_uncached(
    document: Document,
    question: str,
    client,
) -> tuple[str, dict]:
    """Summarize WITHOUT prompt caching (baseline)."""
    response = client.messages.create(
        model=ModelId.SONNET.value,
        max_tokens=1024,
        system=f"{SUMMARIZE_SYSTEM_PROMPT}\n\nDOCUMENT:\n\n{document.content}",
        messages=[{"role": "user", "content": question}],
    )

    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cache_write_tokens": 0,
        "cache_read_tokens": 0,
    }

    return response.content[0].text, usage


def summarize_mock(
    document: Document,
    question: str,
    call_number: int,
    use_cache: bool = True,
) -> tuple[str, dict]:
    """
    Mock summarization with realistic token simulation.

    call_number: 1 = first call (cache write), 2+ = subsequent (cache read)
    """
    # Simulate latency
    if call_number == 1:
        time.sleep(0.12)  # First call is slower (cache write)
    else:
        time.sleep(0.06)  # Subsequent calls are faster (cache read)

    # Approximate token counts
    doc_tokens = document.word_count * 4 // 3  # ~1.33 tokens per word
    prompt_tokens = 50  # System prompt + question

    if use_cache:
        if call_number == 1:
            # First call: write document to cache
            usage = {
                "input_tokens": prompt_tokens,
                "output_tokens": 250,
                "cache_write_tokens": doc_tokens,
                "cache_read_tokens": 0,
            }
        else:
            # Subsequent calls: read from cache
            usage = {
                "input_tokens": prompt_tokens,
                "output_tokens": 200,
                "cache_write_tokens": 0,
                "cache_read_tokens": doc_tokens,
            }
    else:
        # No caching: full input every time
        usage = {
            "input_tokens": prompt_tokens + doc_tokens,
            "output_tokens": 250,
            "cache_write_tokens": 0,
            "cache_read_tokens": 0,
        }

    # Generate mock summary based on document
    if document.id == "DOC-001":
        if "risk" in question.lower():
            answer = (
                "The Q3 2025 report identifies five key risks: (1) Mid-Market churn acceleration "
                "that could spread to Enterprise, (2) competitive pressure from AnalyticsRival's "
                "$100M fundraise, (3) infrastructure costs growing faster than revenue, (4) key "
                "person risk with 3 senior engineers owning critical components, and (5) EU AI Act "
                "regulatory requirements impacting predictive analytics features."
            )
        elif "revenue" in question.lower():
            answer = (
                "Q3 2025 revenue was $47.2 million, representing 23% year-over-year growth compared "
                "to $38.4 million in Q3 2024. Enterprise led with $28.3M (+31% YoY), Mid-Market "
                "contributed $13.1M (+18% YoY), and Self-Serve added $5.8M (+8% YoY)."
            )
        else:
            answer = (
                "Acme Corporation's Q3 2025 was a significant inflection point with $47.2M revenue "
                "(+23% YoY) driven by Enterprise expansion and Analytics Pro launch. The Enterprise "
                "segment added 47 logos with ACV increasing to $142K. However, growth compressed "
                "operating margins from 18% to 14% due to Analytics Pro launch costs, infrastructure "
                "spending, and engineering headcount expansion.\n\n"
                "Product highlights include Analytics Pro's successful launch ($2.4M bookings, 4.6/5 G2 rating) "
                "and platform reliability improving to 99.97% uptime. API performance saw major gains with "
                "P50 latency dropping from 145ms to 98ms.\n\n"
                "Key concerns include Mid-Market churn rising to 4.1%, self-serve growth decelerating, and "
                "competitive pressure from AnalyticsRival. Q4 priorities focus on closing the Analytics Pro "
                "performance gap and preparing for Series C fundraise."
            )
    elif document.id == "DOC-002":
        if "budget" in question.lower() or "savings" in question.lower() or "cost" in question.lower():
            answer = (
                "The total migration budget is $2,120,000 spread across four phases. Current annual "
                "on-premises cost is $4,800,000, while projected annual AWS cost post-optimization is "
                "$3,200,000, yielding annual savings of $1,600,000 (33% reduction). Break-even is "
                "expected at month 16."
            )
        elif "gcp" in question.lower() or "rejected" in question.lower():
            answer = (
                "GCP was rejected despite scoring well on ML/AI capabilities and pricing. The primary "
                "reasons were: (1) the team's existing AWS expertise (12 of 15 engineers hold AWS certs), "
                "(2) more mature migration tooling on AWS, and (3) an estimated $320,000 in additional "
                "training costs for GCP adoption."
            )
        else:
            answer = (
                "MegaCorp is migrating from two on-premises data centers to AWS over 18 months using a "
                "phased 'lift-and-shift then optimize' approach. The migration is driven by capacity "
                "planning challenges (12-16 week hardware lead times), 35% average utilization, inadequate "
                "DR capabilities, and difficulty hiring.\n\n"
                "The $2.12M migration spans four phases: Foundation (Landing Zone, networking, IAM), "
                "non-critical workload migration, production migration with parallel operations, and "
                "optimization. Expected annual savings are $1.6M (33% reduction) with break-even at month 16.\n\n"
                "Key risks include data migration (48TB), performance differences, cost overruns, and team "
                "burnout. GCP and multi-cloud alternatives were evaluated but rejected in favor of AWS "
                "due to team expertise and tooling maturity."
            )
    else:
        if "core hours" in question.lower():
            answer = (
                "All employees must be available during core hours: 10:00 AM to 3:00 PM in their "
                "designated time zone, regardless of work arrangement type."
            )
        elif "violation" in question.lower() or "third" in question.lower():
            answer = (
                "On the third policy violation, remote work privileges are revoked for a minimum of "
                "6 months. The progression is: first offense (verbal warning and coaching), second "
                "offense (written warning with 30-day remediation plan), third offense (revocation). "
                "Severe violations like security breaches can result in immediate revocation and "
                "potential termination."
            )
        else:
            answer = (
                "TechVentures Inc.'s Remote and Hybrid Work Policy (v3.2) establishes three work "
                "arrangement types: Fully Remote, Hybrid (A/B/C tiers), and Office-Based. Eligibility "
                "requires completion of the 90-day probationary period, 'Meets Expectations' rating, "
                "and no active PIPs.\n\n"
                "The policy mandates core hours (10 AM - 3 PM), VPN usage for all work, WPA3 Wi-Fi "
                "encryption, and prohibits local storage of sensitive data. The company provides equipment "
                "(laptop, monitor, peripherals) and stipends ($500 setup, $75/month remote, $50/month hybrid).\n\n"
                "Performance is measured by outcomes, not presence. Regular check-ins include weekly 1:1s, "
                "bi-weekly team meetings, and quarterly reviews. Violations follow a three-strike system "
                "with escalating consequences from verbal warning to privilege revocation."
            )

    return answer, usage


def run_caching_comparison(
    document: Document,
    questions: list[str],
    tracker: MetricsTracker,
    client=None,
) -> dict:
    """
    Run summarization with and without caching, measuring the cost difference.

    Returns metrics for cached vs uncached runs.
    """
    all_questions = [SUMMARIZE_USER_PROMPT] + questions

    # --- With caching ---
    for i, question in enumerate(all_questions):
        call_id = f"TaskC-Cached-{document.id}-Q{i}"
        call_number = i + 1

        with tracker.track(call_id, ModelId.SONNET, f"TaskC-Cached-{document.id}") as t:
            if client:
                try:
                    answer, usage = summarize_live_cached(document, question, client)
                except Exception as e:
                    print(f"    [API error: {e} -- mock fallback]")
                    answer, usage = summarize_mock(document, question, call_number, use_cache=True)
            else:
                answer, usage = summarize_mock(document, question, call_number, use_cache=True)

            t.set_tokens(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                cache_write_tokens=usage.get("cache_write_tokens", 0),
                cache_read_tokens=usage.get("cache_read_tokens", 0),
            )

    # --- Without caching (baseline) ---
    for i, question in enumerate(all_questions):
        call_id = f"TaskC-NoCach-{document.id}-Q{i}"

        with tracker.track(call_id, ModelId.SONNET, f"TaskC-NoCache-{document.id}") as t:
            if client:
                try:
                    answer, usage = summarize_live_uncached(document, question, client)
                except Exception as e:
                    print(f"    [API error: {e} -- mock fallback]")
                    answer, usage = summarize_mock(document, question, i + 1, use_cache=False)
            else:
                answer, usage = summarize_mock(document, question, i + 1, use_cache=False)

            t.set_tokens(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                cache_write_tokens=usage.get("cache_write_tokens", 0),
                cache_read_tokens=usage.get("cache_read_tokens", 0),
            )

    return {}
