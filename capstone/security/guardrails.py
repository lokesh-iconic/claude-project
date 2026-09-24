"""
security/guardrails.py — Dual-layer guardrails for the support assistant.

Adapted from Domain 7's hardened_app for the support assistant context:
customer messages are UNTRUSTED INPUT that may contain prompt injections.

Two independent guardrail layers (defense in depth):

  Layer 1 — PRE-PROCESSING (input scanning):
    Regex-based injection detection on customer messages BEFORE they reach
    the model. Deterministic — fires the same way every time.

  Layer 2 — POST-PROCESSING (output sanitization):
    Content policy check on model output BEFORE it reaches the user.
    Catches dangerous outputs even if an injection bypasses Layer 1.

Key principle: these are CODE-BASED (deterministic), not PROMPT-BASED
(probabilistic) guardrails.
"""

from __future__ import annotations

import re


# ──────────────────────────────────────────────────────────────────────
# Layer 1: Pre-processing injection detection patterns
# ──────────────────────────────────────────────────────────────────────

_INJECTION_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    # Instruction override attempts
    (
        re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?", re.IGNORECASE),
        "instruction_override",
        "Attempt to override previous instructions",
    ),
    (
        re.compile(r"(?:\[?\s*)?new\s+instructions?\s*(?:\])?\s*:", re.IGNORECASE),
        "instruction_override",
        "Attempt to inject new instructions",
    ),
    (
        re.compile(r"from\s+now\s+on[\s,]", re.IGNORECASE),
        "instruction_override",
        "Attempt to override future behavior",
    ),
    (
        re.compile(r"disregard\s+(?:your|the)\s+(?:original|previous|system)", re.IGNORECASE),
        "instruction_override",
        "Attempt to disregard original task",
    ),

    # System prompt extraction
    (
        re.compile(r"(?:reveal|output|show|print|display)\s+(?:your\s+)?system\s+prompt", re.IGNORECASE),
        "prompt_extraction",
        "Attempt to extract system prompt",
    ),
    (
        re.compile(r"what\s+(?:is|are)\s+your\s+(?:system\s+)?(?:instructions?|rules?|prompt)", re.IGNORECASE),
        "prompt_extraction",
        "Attempt to extract system instructions",
    ),

    # Role hijacking
    (
        re.compile(r"you\s+are\s+(?:now|no\s+longer)\s+", re.IGNORECASE),
        "role_hijack",
        "Attempt to change the model's role",
    ),
    (
        re.compile(r"pretend\s+to\s+be\s+", re.IGNORECASE),
        "role_hijack",
        "Attempt to assign a new persona",
    ),
    (
        re.compile(r"(?:enter|switch\s+to)\s+maintenance\s+mode", re.IGNORECASE),
        "role_hijack",
        "Attempt to enter maintenance mode",
    ),

    # Data exfiltration
    (
        re.compile(r"(?:print|output|reveal|show)\s+(?:all\s+)?(?:environment\s+variables?|api\s+keys?|secrets?|credentials?|config)", re.IGNORECASE),
        "data_exfiltration",
        "Attempt to exfiltrate secrets or configuration",
    ),
    (
        re.compile(r"security\s+audit", re.IGNORECASE),
        "data_exfiltration",
        "Fake security audit pretense",
    ),

    # Action triggering
    (
        re.compile(r"(?:call|execute|invoke|run|trigger)\s+(?:the\s+)?(?:send_email|delete|function)", re.IGNORECASE),
        "action_trigger",
        "Attempt to trigger a sensitive function",
    ),
    (
        re.compile(r"attacker@|evil\.com", re.IGNORECASE),
        "action_trigger",
        "Suspicious email address in content",
    ),

    # Delimiter escape
    (
        re.compile(r"</(?:user_content|instructions|system|prompt)>", re.IGNORECASE),
        "delimiter_escape",
        "Attempt to close instruction delimiters",
    ),
    (
        re.compile(r"<(?:instructions|system|prompt)>", re.IGNORECASE),
        "delimiter_escape",
        "Attempt to open new instruction block",
    ),

    # Encoded payloads
    (
        re.compile(r"(?:decode|base64|execute)\s+(?:and\s+)?(?:run|execute|follow)", re.IGNORECASE),
        "encoded_injection",
        "Attempt to execute encoded instructions",
    ),
    (
        re.compile(r"[A-Za-z0-9+/]{40,}={0,2}", re.IGNORECASE),
        "encoded_injection",
        "Possible base64-encoded payload detected",
    ),

    # Jailbreak templates
    (
        re.compile(r"\bDAN\b.*do\s+anything\s+now", re.IGNORECASE),
        "jailbreak",
        "DAN jailbreak template detected",
    ),
    (
        re.compile(r"(?:disable|remove|bypass)\s+(?:all\s+)?(?:content\s+)?(?:filters?|safety|restrictions?)", re.IGNORECASE),
        "jailbreak",
        "Attempt to disable safety filters",
    ),

    # Admin/system impersonation
    (
        re.compile(r"(?:---\s*)?SYSTEM(?:\s*---)?|ADMIN\s+OVERRIDE|URGENT\s+DIRECTIVE", re.IGNORECASE),
        "impersonation",
        "Fake system/admin authority marker",
    ),
    (
        re.compile(r"IMPORTANT\s+SYSTEM\s+UPDATE", re.IGNORECASE),
        "impersonation",
        "Fake system update marker",
    ),
]


# ──────────────────────────────────────────────────────────────────────
# Layer 2: Post-processing content policy patterns
# ──────────────────────────────────────────────────────────────────────

_CREDENTIAL_PATTERNS = [
    re.compile(r"sk-ant-api\w+", re.IGNORECASE),
    re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE),
    re.compile(r"AKIA[0-9A-Z]{16}", re.IGNORECASE),
    re.compile(r"password\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"secret[_\s]?key\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"ANTHROPIC_API_KEY\s*[:=]\s*\S+", re.IGNORECASE),
]

_PROMPT_LEAK_PATTERNS = [
    re.compile(r"you are a (?:professional )?customer support assistant", re.IGNORECASE),
    re.compile(r"system prompt[:.]\s", re.IGNORECASE),
    re.compile(r"my (?:system |initial )?instructions (?:are|say|tell)", re.IGNORECASE),
]

_ROLE_HIJACK_PATTERNS = [
    re.compile(r"i am (?:dark\s*gpt|dan\b)", re.IGNORECASE),
    re.compile(r"filters?\s*disabled", re.IGNORECASE),
    re.compile(r"safety (?:checks?|rules?)\s*(?:bypassed|disabled|removed)", re.IGNORECASE),
    re.compile(r"maintenance mode\s*(?:activated|enabled|entered)", re.IGNORECASE),
]

_CANARY_PATTERNS = [
    re.compile(r"\bpwned\b", re.IGNORECASE),
    re.compile(r"\bcompromised\b.*(?:config|internal|system)", re.IGNORECASE),
]


# ──────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────

def pre_process_check(user_message: str) -> dict:
    """
    Layer 1: Scan user message for injection patterns BEFORE model sees it.

    Returns:
        {
            "allowed": bool,
            "reason": str,
            "detections": [{"category", "description", "matched_text"}],
        }
    """
    detections = []

    for pattern, category, description in _INJECTION_PATTERNS:
        match = pattern.search(user_message)
        if match:
            detections.append({
                "category": category,
                "description": description,
                "matched_text": match.group()[:60],
            })

    if detections:
        categories = sorted(set(d["category"] for d in detections))
        return {
            "allowed": False,
            "reason": f"Injection detected: {', '.join(categories)}",
            "detections": detections,
        }

    return {
        "allowed": True,
        "reason": "No injection patterns detected",
        "detections": [],
    }


def post_process_check(response_text: str) -> dict:
    """
    Layer 2: Check model output for policy violations BEFORE user sees it.

    Returns:
        {
            "allowed": bool,
            "reason": str,
            "violations": [{"category", "detail", "matched_text"}],
            "sanitized_response": str,
        }
    """
    violations = []

    # Check credentials
    for pattern in _CREDENTIAL_PATTERNS:
        match = pattern.search(response_text)
        if match:
            violations.append({
                "category": "credential_leak",
                "detail": f"Potential credential in output: {pattern.pattern}",
                "matched_text": match.group()[:80],
            })

    # Check prompt leaks
    for pattern in _PROMPT_LEAK_PATTERNS:
        match = pattern.search(response_text)
        if match:
            violations.append({
                "category": "prompt_leak",
                "detail": "Output contains system prompt fragments",
                "matched_text": match.group()[:80],
            })

    # Check role hijack
    for pattern in _ROLE_HIJACK_PATTERNS:
        match = pattern.search(response_text)
        if match:
            violations.append({
                "category": "role_hijack",
                "detail": "Output confirms role/identity change",
                "matched_text": match.group()[:80],
            })

    # Check canaries
    for pattern in _CANARY_PATTERNS:
        match = pattern.search(response_text)
        if match:
            violations.append({
                "category": "canary_triggered",
                "detail": "Exploitation canary detected in output",
                "matched_text": match.group()[:80],
            })

    if violations:
        cats = sorted(set(v["category"] for v in violations))
        return {
            "allowed": False,
            "reason": f"BLOCKED — {len(violations)} violation(s): {', '.join(cats)}",
            "violations": violations,
            "sanitized_response": (
                "I'm sorry, but I'm unable to process that request. "
                "If you have a support question, please rephrase it and I'll be happy to help."
            ),
        }

    return {
        "allowed": True,
        "reason": "Output passed content policy",
        "violations": [],
        "sanitized_response": response_text,
    }
