"""
shared.py — Shared types, constants, and formatting rules.

This is an unmodified copy of 1_agents_and_workflows/shared.py, used by both
the broken_app and fixed_app versions in this diagnostic exercise.
"""

from __future__ import annotations

import re
from enum import Enum
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class Category(str, Enum):
    """Valid ticket categories."""
    BILLING = "billing"
    TECHNICAL = "technical"
    ACCOUNT = "account"
    FEATURE_REQUEST = "feature_request"
    GENERAL = "general"


class Priority(str, Enum):
    """Ticket priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Team(str, Enum):
    """Valid routing targets."""
    BILLING = "billing"
    ENGINEERING = "engineering"
    ACCOUNT_MGMT = "account_mgmt"
    PRODUCT = "product"
    GENERAL_SUPPORT = "general_support"


# Category → default team mapping (used by workflow; agent may override)
CATEGORY_TO_TEAM: dict[Category, Team] = {
    Category.BILLING: Team.BILLING,
    Category.TECHNICAL: Team.ENGINEERING,
    Category.ACCOUNT: Team.ACCOUNT_MGMT,
    Category.FEATURE_REQUEST: Team.PRODUCT,
    Category.GENERAL: Team.GENERAL_SUPPORT,
}


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class ClassificationResult(BaseModel):
    """Output of the classify step."""
    category: Category
    priority: Priority
    confidence: float = Field(ge=0.0, le=1.0, description="Model confidence 0-1")
    reasoning: str = Field(description="Brief explanation of classification logic")
    is_ambiguous: bool = Field(
        default=False,
        description="True when the ticket doesn't clearly fit one category",
    )


class RoutingResult(BaseModel):
    """Output of the route step."""
    team: Team
    escalate: bool = Field(default=False, description="Whether to escalate to a senior agent")
    routing_reason: str = Field(description="Why this team was chosen")


class DraftResponse(BaseModel):
    """Output of the draft-response step."""
    subject_line: str
    body: str
    internal_notes: str = Field(default="", description="Notes visible only to the support team")


class TicketResult(BaseModel):
    """Combined output for one ticket through the full pipeline."""
    ticket_id: str
    classification: ClassificationResult
    routing: RoutingResult
    draft: DraftResponse
    system: str = Field(description="'workflow' or 'agent'")


# ---------------------------------------------------------------------------
# Formatting Rules — enforced deterministically by the hook / post-processor
# ---------------------------------------------------------------------------

FORMATTING_RULES = {
    "greeting_prefix": "Hi",
    "sign_off": "Best regards,\nSupport Team",
    "max_paragraph_words": 80,
    "required_sections": ["greeting", "body", "sign_off"],
}


def enforce_formatting(draft: DraftResponse, customer_name: str = "there") -> DraftResponse:
    """
    Apply FORMATTING_RULES deterministically to a draft response.

    This is the function called by:
      - The workflow's post-processing step
      - The agent's PreToolUse hook (via hooks.py)

    It guarantees structural compliance regardless of what the model produced.
    """
    body = draft.body.strip()

    # 1. Ensure greeting
    greeting = f"{FORMATTING_RULES['greeting_prefix']} {customer_name},"
    if not body.lower().startswith(FORMATTING_RULES["greeting_prefix"].lower()):
        body = f"{greeting}\n\n{body}"

    # 2. Enforce max paragraph length
    paragraphs = body.split("\n\n")
    trimmed = []
    for para in paragraphs:
        words = para.split()
        if len(words) > FORMATTING_RULES["max_paragraph_words"]:
            # Break into chunks
            chunks = []
            for i in range(0, len(words), FORMATTING_RULES["max_paragraph_words"]):
                chunks.append(" ".join(words[i:i + FORMATTING_RULES["max_paragraph_words"]]))
            trimmed.extend(chunks)
        else:
            trimmed.append(para)
    body = "\n\n".join(trimmed)

    # 3. Ensure sign-off
    sign_off = FORMATTING_RULES["sign_off"]
    if sign_off.splitlines()[-1].strip() not in body:
        body = f"{body}\n\n{sign_off}"

    # 4. Clean up excess whitespace
    body = re.sub(r"\n{3,}", "\n\n", body)

    return DraftResponse(
        subject_line=draft.subject_line,
        body=body,
        internal_notes=draft.internal_notes,
    )
