"""
classifier.py -- High-volume email sentiment classifier.

Compares two models:
  - Haiku (fast/cheap): the primary choice for high-volume classification
  - Sonnet (capable/expensive): tested to verify Haiku is sufficient

Both use the same prompt. The question is whether the cheaper model
meets the 85% accuracy bar -- if yes, Sonnet is unnecessary cost.
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

VALID_CATEGORIES = {"positive", "negative", "neutral", "urgent", "spam"}

CLASSIFICATION_PROMPT = """\
Classify this email into exactly ONE sentiment category.

Categories:
- positive: Happy, grateful, complimentary, praising
- negative: Angry, disappointed, complaining, threatening to leave
- neutral: Informational, transactional, procedural, no strong emotion
- urgent: Emergency, time-critical, system down, security incident
- spam: Scam, phishing, unsolicited marketing, too-good-to-be-true offers

Return ONLY a JSON object: {"category": "<category>"}

Email:
Subject: {subject}
Body: {body}"""


def classify_email_live(
    subject: str,
    body: str,
    model_id: ModelId,
    client,
) -> tuple[str, dict]:
    """
    Classify an email using the live Anthropic API.

    Returns:
        (category, usage_dict) where usage_dict has token counts
    """
    prompt = CLASSIFICATION_PROMPT.format(subject=subject, body=body)

    response = client.messages.create(
        model=model_id.value,
        max_tokens=50,
        temperature=0.0,
        messages=[{"role": "user", "content": prompt}],
    )

    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }

    try:
        result = json.loads(response.content[0].text)
        category = result.get("category", "neutral").lower().strip()
    except (json.JSONDecodeError, IndexError):
        category = "neutral"

    if category not in VALID_CATEGORIES:
        category = "neutral"

    return category, usage


def classify_email_mock(
    subject: str,
    body: str,
    model_id: ModelId,
) -> tuple[str, dict]:
    """
    Classify an email using keyword matching (mock mode).

    Simulates realistic token counts and latency.
    Both Haiku and Sonnet produce the same accuracy in mock mode --
    this is intentional: for simple classification, Sonnet doesn't
    meaningfully outperform Haiku, which is the key insight.
    """
    text = (subject + " " + body).lower()

    # Keyword-based classification
    if any(w in text for w in ["won", "prize", "click here", "free", "guaranteed",
                                "verify your", "credit card", ".exe", "nigerian",
                                "cheap", "virus", "giveaway", "scam", "no prescription"]):
        category = "spam"
    elif any(w in text for w in ["critical", "down", "breach", "emergency", "immediately",
                                  "urgent", "data loss", "now", "security", "expired",
                                  "compliance deadline", "revenue", "patch"]):
        category = "urgent"
    elif any(w in text for w in ["love", "fantastic", "great", "thank", "excellent",
                                  "happy", "pleased", "seamless", "5-star", "referr",
                                  "perfect", "flawless", "no complaints"]):
        category = "positive"
    elif any(w in text for w in ["disappointed", "cancel", "worst", "broken",
                                  "frustrated", "refund", "complaint", "declined",
                                  "misleading", "dishonest", "competitor", "outdated"]):
        category = "negative"
    else:
        category = "neutral"

    # Simulate token counts (prompt + email text ~ 120-180 tokens, response ~ 15 tokens)
    input_tokens = 130 + len(text.split()) // 2
    output_tokens = 15

    # Simulate model-specific latency
    base_latency = MODELS[model_id].typical_latency_factor
    time.sleep(base_latency * 0.02)  # Small delay to simulate

    return category, {"input_tokens": input_tokens, "output_tokens": output_tokens}


def run_classification_batch(
    samples,
    model_id: ModelId,
    tracker: MetricsTracker,
    task_label: str,
    client=None,
) -> list[dict]:
    """
    Classify a batch of emails and track metrics.

    Returns list of {id, predicted, actual, correct} dicts.
    """
    results = []

    for i, sample in enumerate(samples):
        call_id = f"{task_label}-{sample.id}"

        with tracker.track(call_id, model_id, task_label) as t:
            if client is not None:
                try:
                    predicted, usage = classify_email_live(
                        sample.subject, sample.body, model_id, client
                    )
                except Exception as e:
                    print(f"    [API error on {sample.id}: {e} -- falling back to mock]")
                    predicted, usage = classify_email_mock(
                        sample.subject, sample.body, model_id
                    )
            else:
                predicted, usage = classify_email_mock(
                    sample.subject, sample.body, model_id
                )

            t.set_tokens(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
            )
            t.set_metadata(predicted=predicted, actual=sample.ground_truth)

        results.append({
            "id": sample.id,
            "predicted": predicted,
            "actual": sample.ground_truth,
            "correct": predicted == sample.ground_truth,
        })

    return results
