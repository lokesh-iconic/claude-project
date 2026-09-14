"""
structured_output.py -- Response schema and defensive parser.

The parser handles:
1. Valid JSON → parsed directly
2. JSON inside markdown fences → extracted then parsed
3. Partial/malformed JSON → attempt repair
4. Complete garbage → safe fallback (never crashes)

Key principle: code NEVER assumes the response is well-formed.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class AssistantResponse:
    """Structured response from the assistant."""
    summary: str
    details: str
    sources: list[str]
    confidence: str  # "high", "medium", or "low"
    follow_up: Optional[str] = None
    parse_error: Optional[str] = None  # Non-None if parsing had issues
    raw_text: Optional[str] = None     # Original text if parsing failed

    VALID_CONFIDENCE = {"high", "medium", "low"}

    def is_valid(self) -> bool:
        """Check if this response passed all validation rules."""
        return (
            self.parse_error is None
            and self.confidence in self.VALID_CONFIDENCE
            and len(self.summary.split()) <= 55  # Allow small margin
            and len(self.summary) > 0
            and len(self.details) > 0
        )

    def summary_word_count(self) -> int:
        """Count words in the summary."""
        return len(self.summary.split())

    def format_compliance(self) -> dict:
        """Check compliance with each format rule."""
        return {
            "has_summary": len(self.summary) > 0,
            "summary_under_50_words": self.summary_word_count() <= 50,
            "has_details": len(self.details) > 0,
            "has_sources_list": isinstance(self.sources, list),
            "valid_confidence": self.confidence in self.VALID_CONFIDENCE,
            "has_follow_up": self.follow_up is not None,
            "no_parse_error": self.parse_error is None,
        }


def _make_fallback(raw_text: str, error: str) -> AssistantResponse:
    """Create a safe fallback response when parsing fails."""
    # Try to extract SOMETHING useful from the raw text
    summary = raw_text[:200].strip() if raw_text else "Unable to parse response"

    return AssistantResponse(
        summary=summary,
        details=raw_text or "No content available",
        sources=[],
        confidence="low",
        follow_up=None,
        parse_error=error,
        raw_text=raw_text,
    )


def _extract_json_from_markdown(text: str) -> Optional[str]:
    """Extract JSON from markdown code fences."""
    # Try ```json ... ``` first
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def _try_repair_json(text: str) -> Optional[str]:
    """Attempt to repair common JSON issues."""
    repaired = text.strip()

    # Remove trailing commas before closing braces/brackets
    repaired = re.sub(r",\s*([}\]])", r"\1", repaired)

    # Add missing closing brace
    open_braces = repaired.count("{") - repaired.count("}")
    if open_braces > 0:
        repaired += "}" * open_braces

    # Add missing closing bracket
    open_brackets = repaired.count("[") - repaired.count("]")
    if open_brackets > 0:
        repaired += "]" * open_brackets

    # Try to find JSON object in the text
    brace_start = repaired.find("{")
    if brace_start >= 0:
        repaired = repaired[brace_start:]

    return repaired


def _validate_and_normalize(data: dict) -> AssistantResponse:
    """Validate a parsed dict and normalize field values."""
    errors = []

    # Extract fields with defaults
    summary = str(data.get("summary", "")).strip()
    details = str(data.get("details", "")).strip()
    sources = data.get("sources", [])
    confidence = str(data.get("confidence", "low")).strip().lower()
    follow_up = data.get("follow_up")

    # Validate summary
    if not summary:
        summary = "No summary provided"
        errors.append("missing summary")

    # Validate details
    if not details:
        details = "No details provided"
        errors.append("missing details")

    # Validate sources is a list
    if not isinstance(sources, list):
        sources = [str(sources)] if sources else []
        errors.append("sources was not a list")

    # Ensure all sources are strings
    sources = [str(s) for s in sources]

    # Validate confidence
    if confidence not in AssistantResponse.VALID_CONFIDENCE:
        errors.append(f"invalid confidence '{confidence}', defaulting to 'low'")
        confidence = "low"

    # Validate follow_up
    if follow_up is not None:
        follow_up = str(follow_up).strip()
        if follow_up.lower() == "null" or follow_up == "":
            follow_up = None

    parse_error = "; ".join(errors) if errors else None

    return AssistantResponse(
        summary=summary,
        details=details,
        sources=sources,
        confidence=confidence,
        follow_up=follow_up,
        parse_error=parse_error,
    )


def parse_response(raw_text: str) -> AssistantResponse:
    """
    Defensively parse an assistant response.

    Handles: valid JSON, markdown-wrapped JSON, partial JSON,
    and complete garbage. NEVER crashes. NEVER silently produces
    wrong data -- errors are always flagged in parse_error.
    """
    if not raw_text or not raw_text.strip():
        return _make_fallback(raw_text or "", "empty response")

    text = raw_text.strip()

    # --- Strategy 1: Direct JSON parse ---
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return _validate_and_normalize(data)
        else:
            return _make_fallback(text, f"JSON parsed but was {type(data).__name__}, not object")
    except json.JSONDecodeError:
        pass

    # --- Strategy 2: Extract from markdown fences ---
    extracted = _extract_json_from_markdown(text)
    if extracted:
        try:
            data = json.loads(extracted)
            if isinstance(data, dict):
                result = _validate_and_normalize(data)
                if result.parse_error:
                    result.parse_error = f"extracted from markdown; {result.parse_error}"
                else:
                    result.parse_error = "extracted from markdown fences"
                return result
        except json.JSONDecodeError:
            pass

    # --- Strategy 3: Try to repair ---
    repaired = _try_repair_json(text)
    if repaired and repaired != text:
        try:
            data = json.loads(repaired)
            if isinstance(data, dict):
                result = _validate_and_normalize(data)
                error_msg = "JSON was repaired (malformed original)"
                if result.parse_error:
                    result.parse_error = f"{error_msg}; {result.parse_error}"
                else:
                    result.parse_error = error_msg
                return result
        except json.JSONDecodeError:
            pass

    # --- Strategy 4: Fallback ---
    return _make_fallback(text, "could not parse as JSON")
