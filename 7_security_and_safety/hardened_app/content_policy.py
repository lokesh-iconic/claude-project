"""
hardened_app/content_policy.py -- Second guardrail layer (independent of injection detection).

This is a DETERMINISTIC, CODE-BASED policy checker that examines model output
for violations.  It is independent of the injection detection hook -- even if
an injection slips past the pre-processing hook, the content policy catches
dangerous output before it reaches the user.

Two independent guardrail layers means a single point of failure doesn't
compromise the whole system.
"""

from __future__ import annotations

import re


# ──────────────────────────────────────────────────────────────────────
# Policy violation patterns (all regex-based, deterministic)
# ──────────────────────────────────────────────────────────────────────

# Credential / secret patterns in output
_CREDENTIAL_PATTERNS = [
    re.compile(r"sk-ant-api\w+", re.IGNORECASE),                 # Anthropic API key
    re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE),           # OpenAI-style key
    re.compile(r"AKIA[0-9A-Z]{16}", re.IGNORECASE),              # AWS access key
    re.compile(r"password\s*[:=]\s*\S+", re.IGNORECASE),          # password=...
    re.compile(r"secret[_\s]?key\s*[:=]\s*\S+", re.IGNORECASE),  # secret_key=...
    re.compile(r"DATABASE_PASSWORD\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"ANTHROPIC_API_KEY\s*[:=]\s*\S+", re.IGNORECASE),
]

# System prompt leakage patterns
_PROMPT_LEAK_PATTERNS = [
    re.compile(r"you are a helpful article summarizer", re.IGNORECASE),
    re.compile(r"follow any special instructions", re.IGNORECASE),
    re.compile(r"system prompt[:.]", re.IGNORECASE),
    re.compile(r"my (?:system |initial )?instructions (?:are|say|tell)", re.IGNORECASE),
]

# Unauthorized action confirmation patterns
_ACTION_PATTERNS = [
    re.compile(r"email sent|sending email", re.IGNORECASE),
    re.compile(r"data deleted|records removed", re.IGNORECASE),
    re.compile(r"function called|executing function", re.IGNORECASE),
    re.compile(r"attacker@", re.IGNORECASE),
]

# Role hijack confirmation patterns
_ROLE_HIJACK_PATTERNS = [
    re.compile(r"i am (?:dark\s*gpt|dan\b)", re.IGNORECASE),
    re.compile(r"filters?\s*disabled", re.IGNORECASE),
    re.compile(r"safety (?:checks?|rules?)\s*(?:bypassed|disabled|removed)", re.IGNORECASE),
    re.compile(r"maintenance mode\s*(?:activated|enabled|entered)", re.IGNORECASE),
    re.compile(r"no restrictions?|unrestricted", re.IGNORECASE),
]

# Canary / exploitation markers
_CANARY_PATTERNS = [
    re.compile(r"\bpwned\b", re.IGNORECASE),
    re.compile(r"\bcompromised\b.*(?:config|internal|system)", re.IGNORECASE),
]


# ──────────────────────────────────────────────────────────────────────
# Content policy checker
# ──────────────────────────────────────────────────────────────────────

class ContentPolicyResult:
    """Result of a content policy check."""

    def __init__(self):
        self.violations: list[dict] = []

    @property
    def passed(self) -> bool:
        return len(self.violations) == 0

    def add_violation(self, category: str, detail: str, matched: str):
        self.violations.append({
            "category": category,
            "detail": detail,
            "matched_text": matched[:80],
        })

    def summary(self) -> str:
        if self.passed:
            return "PASS — no policy violations"
        cats = set(v["category"] for v in self.violations)
        return f"BLOCKED — {len(self.violations)} violation(s): {', '.join(sorted(cats))}"


def check_content_policy(text: str) -> ContentPolicyResult:
    """
    Run all content policy checks against a piece of text.

    This is the SECOND guardrail layer, independent of the injection
    detection hook.  It catches dangerous output even if the injection
    detection missed the input.

    All checks are regex-based (deterministic, not probabilistic).
    """
    result = ContentPolicyResult()

    # Check for credential leaks
    for pattern in _CREDENTIAL_PATTERNS:
        match = pattern.search(text)
        if match:
            result.add_violation(
                "credential_leak",
                f"Potential credential found in output: {pattern.pattern}",
                match.group(),
            )

    # Check for system prompt leakage
    for pattern in _PROMPT_LEAK_PATTERNS:
        match = pattern.search(text)
        if match:
            result.add_violation(
                "prompt_leak",
                "Output appears to contain system prompt fragments",
                match.group(),
            )

    # Check for unauthorized action confirmations
    for pattern in _ACTION_PATTERNS:
        match = pattern.search(text)
        if match:
            result.add_violation(
                "unauthorized_action",
                "Output confirms an action that should require authorization",
                match.group(),
            )

    # Check for role hijack confirmations
    for pattern in _ROLE_HIJACK_PATTERNS:
        match = pattern.search(text)
        if match:
            result.add_violation(
                "role_hijack",
                "Output confirms a role/identity change",
                match.group(),
            )

    # Check for canary markers
    for pattern in _CANARY_PATTERNS:
        match = pattern.search(text)
        if match:
            result.add_violation(
                "canary_triggered",
                "Exploitation canary string detected in output",
                match.group(),
            )

    return result
