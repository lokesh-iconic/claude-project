"""
hardened_app/hooks.py -- Deterministic guardrail hooks for injection defense.

Two independent hooks, both CODE-BASED (regex/keyword), not prompt-based:

  1. PRE-PROCESSING: Injection Detection Hook
     Scans untrusted input for injection patterns BEFORE it reaches the model.
     Deterministic — uses regex patterns, not model judgment.

  2. POST-PROCESSING: Output Sanitization Hook
     Checks model output via content_policy.py before it reaches the user.
     Even if an injection slips past pre-processing, this catches the result.

The key distinction: these are DETERMINISTIC (code-enforced) guardrails,
not PROBABILISTIC (prompt-based) ones. A prompt-based defense says
"don't follow injected instructions" and hopes the model listens. A
code-based hook uses regex patterns that ALWAYS fire, regardless of what
the model decides to do.
"""

from __future__ import annotations

import re

from hardened_app.content_policy import check_content_policy


# ──────────────────────────────────────────────────────────────────────
# Pre-processing: Injection detection patterns
# ──────────────────────────────────────────────────────────────────────

# Each pattern is (compiled_regex, category, description)
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
        re.compile(r"disregard\s+(?:your|the)\s+(?:original|summarization|previous)", re.IGNORECASE),
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

    # Delimiter escape attempts
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


def pre_process_hook(article_text: str) -> dict:
    """
    Pre-processing guardrail hook -- DETERMINISTIC injection detection.

    Scans the untrusted input for known injection patterns using regex.
    This runs BEFORE the content reaches the model.

    Key property: this is CODE, not a prompt instruction. It fires the
    same way every time regardless of model behavior.

    Returns:
        {
            "allowed": bool,
            "reason": str,
            "detections": [{"category": str, "description": str, "matched": str}],
            "sanitized_text": str,
        }
    """
    detections: list[dict] = []

    for pattern, category, description in _INJECTION_PATTERNS:
        match = pattern.search(article_text)
        if match:
            detections.append({
                "category": category,
                "description": description,
                "matched_text": match.group()[:60],
            })

    if detections:
        # Block the request -- injection detected
        categories = sorted(set(d["category"] for d in detections))
        return {
            "allowed": False,
            "reason": f"Injection detected: {', '.join(categories)}",
            "detections": detections,
            "sanitized_text": "",
        }

    return {
        "allowed": True,
        "reason": "No injection patterns detected",
        "detections": [],
        "sanitized_text": article_text,
    }


def post_process_hook(response_text: str) -> dict:
    """
    Post-processing guardrail hook -- DETERMINISTIC output sanitization.

    Even if an injection somehow bypasses pre-processing (e.g., a novel
    technique not in our pattern list), this hook checks the MODEL OUTPUT
    for policy violations before it reaches the user.

    Uses the content_policy module (second independent guardrail layer).

    Returns:
        {
            "allowed": bool,
            "reason": str,
            "violations": list,
            "sanitized_response": str,
        }
    """
    policy_result = check_content_policy(response_text)

    if not policy_result.passed:
        return {
            "allowed": False,
            "reason": policy_result.summary(),
            "violations": policy_result.violations,
            "sanitized_response": (
                '{"summary": "Content blocked by security policy.", '
                '"key_points": ["The submitted content triggered a security guardrail."], '
                '"sentiment": "neutral", "category": "other"}'
            ),
        }

    return {
        "allowed": True,
        "reason": "Output passed content policy check",
        "violations": [],
        "sanitized_response": response_text,
    }
