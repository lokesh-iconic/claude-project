"""
security/secrets_audit.py — Audit and verify secret storage practices.

Checks that:
1. API keys are stored in .env (not hardcoded in source)
2. .env is listed in .gitignore
3. No secrets appear in capstone source files
4. Environment variables are loaded via python-dotenv

Run directly:
    uv run python capstone/security/secrets_audit.py
"""

from __future__ import annotations

import os
import re
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAPSTONE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Secret patterns to search for in source code
_SECRET_PATTERNS = [
    (re.compile(r"sk-ant-api\w{20,}"), "Anthropic API key"),
    (re.compile(r"sk-[a-zA-Z0-9]{20,}"), "OpenAI-style API key"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key"),
    (re.compile(r'(?:password|secret_key|api_key)\s*=\s*["\'][^"\']{8,}["\']'), "Hardcoded credential"),
]

# Files to scan (Python source only, exclude this audit script)
_SCAN_EXTENSIONS = {".py", ".yaml", ".yml", ".toml", ".json", ".md"}
_SKIP_FILES = {"secrets_audit.py", "payloads.py", ".env"}  # Don't flag ourselves or test payloads


def check_env_file_exists() -> tuple[bool, str]:
    """Check that a .env file exists at the project root."""
    env_path = os.path.join(PROJECT_ROOT, ".env")
    if os.path.exists(env_path):
        return True, f"✓ .env file exists at {env_path}"
    return False, f"✗ No .env file found at {env_path}"


def check_gitignore_includes_env() -> tuple[bool, str]:
    """Check that .gitignore includes .env."""
    gitignore_path = os.path.join(PROJECT_ROOT, ".gitignore")
    if not os.path.exists(gitignore_path):
        return False, "✗ No .gitignore file found"

    with open(gitignore_path, "r", encoding="utf-8") as f:
        content = f.read()

    if ".env" in content:
        return True, "✓ .gitignore includes .env"
    return False, "✗ .gitignore does NOT include .env — secrets may be committed!"


def check_env_has_api_key() -> tuple[bool, str]:
    """Check that .env contains ANTHROPIC_API_KEY."""
    env_path = os.path.join(PROJECT_ROOT, ".env")
    if not os.path.exists(env_path):
        return False, "✗ No .env file to check"

    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "ANTHROPIC_API_KEY" in content:
        return True, "✓ .env contains ANTHROPIC_API_KEY"
    return False, "✗ .env does not contain ANTHROPIC_API_KEY"


def scan_source_for_secrets() -> tuple[bool, list[str]]:
    """Scan capstone source files for hardcoded secrets."""
    findings = []

    for root, dirs, files in os.walk(CAPSTONE_ROOT):
        # Skip __pycache__, .git, .venv
        dirs[:] = [d for d in dirs if d not in {"__pycache__", ".git", ".venv", "node_modules"}]

        for filename in files:
            if filename in _SKIP_FILES:
                continue

            ext = os.path.splitext(filename)[1]
            if ext not in _SCAN_EXTENSIONS:
                continue

            filepath = os.path.join(root, filename)
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception:
                continue

            for pattern, description in _SECRET_PATTERNS:
                matches = pattern.findall(content)
                for match in matches:
                    rel_path = os.path.relpath(filepath, PROJECT_ROOT)
                    findings.append(f"  ✗ {description} found in {rel_path}: '{match[:30]}...'")

    if not findings:
        return True, ["  ✓ No hardcoded secrets found in capstone source files"]
    return False, findings


def check_dotenv_usage() -> tuple[bool, str]:
    """Check that capstone code uses python-dotenv for loading secrets."""
    orchestrator_path = os.path.join(CAPSTONE_ROOT, "agent", "orchestrator.py")
    if not os.path.exists(orchestrator_path):
        return True, "✓ Orchestrator not yet created (will verify at runtime)"

    with open(orchestrator_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "load_dotenv" in content or "dotenv" in content:
        return True, "✓ Orchestrator uses python-dotenv for loading secrets"
    return False, "✗ Orchestrator does not use python-dotenv — secrets loaded insecurely"


def run_audit() -> bool:
    """Run the full secrets audit. Returns True if all checks pass."""
    print("\n" + "=" * 60)
    print("  SECRETS AUDIT — Capstone Support Assistant")
    print("=" * 60 + "\n")

    all_passed = True
    checks = [
        ("1. .env file exists", check_env_file_exists()),
        ("2. .gitignore includes .env", check_gitignore_includes_env()),
        ("3. .env contains ANTHROPIC_API_KEY", check_env_has_api_key()),
        ("4. python-dotenv usage", check_dotenv_usage()),
    ]

    for name, (passed, detail) in checks:
        print(f"  {name}")
        if isinstance(detail, list):
            for line in detail:
                print(f"    {line}")
        else:
            print(f"    {detail}")
        if not passed:
            all_passed = False
        print()

    # Source code scan
    print("  5. Source code secret scan")
    scan_passed, scan_details = scan_source_for_secrets()
    for line in scan_details:
        print(f"    {line}")
    if not scan_passed:
        all_passed = False
    print()

    # Summary
    status = "✓ ALL CHECKS PASSED" if all_passed else "✗ SOME CHECKS FAILED"
    print(f"  {'-' * 50}")
    print(f"  {status}")
    print(f"  {'=' * 60}\n")

    return all_passed


if __name__ == "__main__":
    passed = run_audit()
    sys.exit(0 if passed else 1)
