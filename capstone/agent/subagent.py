"""
agent/subagent.py — Specialist subagent for complex/ambiguous support queries.

WHY A SUBAGENT?
================
Some customer queries are ambiguous or span multiple categories:
  - "I want to cancel but I also need to export my data" (account + technical)
  - "Nothing works, fix this" (general — needs triage)
  - Non-English queries needing intent classification

The specialist subagent has:
  1. A RICHER PROMPT with few-shot examples of tricky cases
  2. NARROWER SCOPE — only classifies intent, doesn't draft responses
  3. COST CONTROL — only invoked when the main agent detects ambiguity
  4. INDEPENDENT EVALUATION — can be tested/optimized separately

In the Claude Agent SDK:
    worker = AgentDefinition(
        description="Complex query specialist",
        prompt=SPECIALIST_PROMPT,
        model="sonnet",
    )
"""

from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True), override=True)


SPECIALIST_PROMPT = """\
You are a SPECIALIST support query analyst for COMPLEX customer messages that
don't clearly map to a single intent or require deeper understanding.

## Intent Categories
- order_inquiry: Order status, tracking, delivery questions
- account_management: Account settings, plan changes, billing, cancellation
- product_question: Product info, compatibility, warranty, specs
- complaint: Dissatisfaction, escalation requests, demands for manager
- technical_issue: Product defects, software bugs, compatibility problems
- general: Truly uncategorizable or requires human judgment

## Decision Process
1. List ALL intents the customer message touches
2. Identify the PRIMARY intent (what does the customer most need right now?)
3. Assign priority based on urgency signals
4. Recommend whether to escalate to human

## Few-Shot Examples

### Example 1: Multi-intent
Message: "I ordered a keyboard last week but haven't received it, and also
my account still shows the old plan even though I upgraded."
Analysis:
- Intents: order_inquiry (missing delivery), account_management (plan not updated)
- Primary: order_inquiry (time-sensitive)
- Priority: high (customer waiting for product)
- Escalate: no (tools can resolve both)

### Example 2: Complaint with vague details
Message: "Nothing works. I'm paying $30/month and everything is broken."
Analysis:
- Intents: complaint (frustration), technical_issue (vague), account_management (subscription value)
- Primary: complaint (needs empathy first, then triage)
- Priority: high (frustrated customer)
- Escalate: yes (vague complaint, needs human judgment)

Return a JSON object with:
- "primary_intent": one of the categories above
- "all_intents": list of all detected intents
- "priority": "low", "medium", "high", or "urgent"
- "reasoning": your chain-of-thought analysis (2-3 sentences)
- "should_escalate": boolean
- "escalation_reason": string or null

Return ONLY valid JSON. No other text."""


def run_specialist(
    message: str,
    context: str = "",
    client=None,
) -> dict:
    """
    Run the specialist subagent on a complex customer message.

    Args:
        message: The customer's message
        context: Additional context (prior conversation, etc.)
        client: Anthropic client (None for mock mode)

    Returns:
        dict with intent analysis fields
    """
    if client is not None:
        try:
            user_content = f"Customer message: {message}"
            if context:
                user_content += f"\n\nConversation context: {context}"

            response = client.messages.create(
                model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
                max_tokens=500,
                system=SPECIALIST_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
            return json.loads(response.content[0].text)
        except Exception as e:
            print(f"    [Notice: Specialist subagent API error ({e}) — using mock]")

    # ── Mock mode ──
    msg = message.lower()

    # Detect all intents
    intents = []
    if any(w in msg for w in ["order", "delivery", "tracking", "ship", "arrived"]):
        intents.append("order_inquiry")
    if any(w in msg for w in ["account", "cancel", "upgrade", "plan", "billing", "subscript"]):
        intents.append("account_management")
    if any(w in msg for w in ["product", "warranty", "compat", "spec", "feature"]):
        intents.append("product_question")
    if any(w in msg for w in ["frustrat", "angry", "terrible", "worst", "manager", "complain", "nothing works"]):
        intents.append("complaint")
    if any(w in msg for w in ["bug", "error", "crash", "broken", "defect", "not working"]):
        intents.append("technical_issue")

    if not intents:
        intents = ["general"]

    primary = intents[0]

    # Priority
    priority = "medium"
    if any(w in msg for w in ["urgent", "asap", "immediately", "frustrated", "angry"]):
        priority = "urgent"
    elif any(w in msg for w in ["complaint", "broken", "nothing works"]):
        priority = "high"

    # Escalation
    should_escalate = (
        "complaint" in intents
        or len(intents) >= 3
        or any(w in msg for w in ["manager", "human", "real person", "supervisor"])
    )

    reasoning = (
        f"Specialist analysis: message touches {len(intents)} intent(s): {', '.join(intents)}. "
        f"Primary intent is '{primary}'. "
        f"{'Escalation recommended due to complaint or complexity.' if should_escalate else 'Can be resolved with available tools.'}"
    )

    return {
        "primary_intent": primary,
        "all_intents": intents,
        "priority": priority,
        "reasoning": reasoning,
        "should_escalate": should_escalate,
        "escalation_reason": "Complex multi-intent query or customer complaint" if should_escalate else None,
    }
