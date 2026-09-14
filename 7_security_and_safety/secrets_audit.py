"""
secrets_audit.py -- Audit how the application stores and accesses secrets.

Scans both the vulnerable and hardened app source code to find:
  - Hardcoded API keys, passwords, and secrets
  - Plaintext credentials in string literals
  - Proper os.environ / dotenv usage

This directly addresses the assignment requirement:
  "Audit how your application currently stores and accesses API keys and
   any other secrets — move anything hardcoded or logged in plaintext to
   proper secret management."
"""

from __future__ import annotations

import os
import re


# ──────────────────────────────────────────────────────────────────────
# Patterns that indicate hardcoded secrets (bad practice)
# ──────────────────────────────────────────────────────────────────────

_HARDCODED_SECRET_PATTERNS = [
    (re.compile(r'''(?:"|')sk-ant-api\w+(?:"|')'''), "Anthropic API key hardcoded"),
    (re.compile(r'''(?:"|')sk-[a-zA-Z0-9]{20,}(?:"|')'''), "API key hardcoded"),
    (re.compile(r'''(?:"|')AKIA[0-9A-Z]{16}(?:"|')'''), "AWS access key hardcoded"),
    (re.compile(r'''(?:INTERNAL_API_KEY|DATABASE_PASSWORD|SECRET_KEY)\s*=\s*(?:"|')[^"']+(?:"|')'''),
     "Secret assigned as plaintext string literal"),
    (re.compile(r'''password\s*=\s*(?:"|')[^"']+(?:"|')''', re.IGNORECASE),
     "Password hardcoded as string literal"),
]

# Patterns that indicate proper secret management (good practice)
_PROPER_SECRET_PATTERNS = [
    (re.compile(r'''os\.environ\.get\(|os\.environ\[|os\.getenv\('''),
     "Loads secret from environment variable"),
    (re.compile(r'''load_dotenv|find_dotenv'''),
     "Uses dotenv for secret management"),
    (re.compile(r'''masked|mask|redact''', re.IGNORECASE),
     "Masks/redacts secrets before output"),
]


def _scan_file(filepath: str) -> dict:
    """
    Scan a single Python file for secret management issues.

    Returns a dict with findings for this file.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        lines = content.split("\n")

    findings = {
        "file": filepath,
        "hardcoded_secrets": [],
        "proper_management": [],
    }

    for line_num, line in enumerate(lines, 1):
        # Skip comments
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        # Check for hardcoded secrets
        for pattern, description in _HARDCODED_SECRET_PATTERNS:
            if pattern.search(line):
                findings["hardcoded_secrets"].append({
                    "line": line_num,
                    "issue": description,
                    "code": stripped[:80],
                })

        # Check for proper management
        for pattern, description in _PROPER_SECRET_PATTERNS:
            if pattern.search(line):
                findings["proper_management"].append({
                    "line": line_num,
                    "practice": description,
                    "code": stripped[:80],
                })

    return findings


def audit_directory(directory: str) -> list[dict]:
    """Scan all Python files in a directory for secret management issues."""
    results = []
    for root, _dirs, files in os.walk(directory):
        for fname in sorted(files):
            if fname.endswith(".py") and fname != "__init__.py":
                filepath = os.path.join(root, fname)
                results.append(_scan_file(filepath))
    return results


def run_full_audit() -> dict:
    """
    Run the full secrets audit: vulnerable vs hardened.

    Returns a structured report comparing both applications.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    vulnerable_dir = os.path.join(base_dir, "vulnerable_app")
    hardened_dir = os.path.join(base_dir, "hardened_app")

    vulnerable_results = audit_directory(vulnerable_dir)
    hardened_results = audit_directory(hardened_dir)

    # Count issues
    vuln_hardcoded = sum(len(r["hardcoded_secrets"]) for r in vulnerable_results)
    vuln_proper = sum(len(r["proper_management"]) for r in vulnerable_results)
    hard_hardcoded = sum(len(r["hardcoded_secrets"]) for r in hardened_results)
    hard_proper = sum(len(r["proper_management"]) for r in hardened_results)

    return {
        "vulnerable_app": {
            "files_scanned": len(vulnerable_results),
            "hardcoded_secrets_found": vuln_hardcoded,
            "proper_management_found": vuln_proper,
            "details": vulnerable_results,
        },
        "hardened_app": {
            "files_scanned": len(hardened_results),
            "hardcoded_secrets_found": hard_hardcoded,
            "proper_management_found": hard_proper,
            "details": hardened_results,
        },
        "verdict": {
            "vulnerable_has_issues": vuln_hardcoded > 0,
            "hardened_has_issues": hard_hardcoded > 0,
            "hardened_uses_proper_management": hard_proper > 0,
        },
    }
