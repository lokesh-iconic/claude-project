"""
validate_setup.py — Validate the Claude Code configuration for this repository.

Checks that all configuration files exist, settings JSON is valid,
CLAUDE.md hierarchy is correct, custom commands are discoverable,
and optionally runs a headless mode test.

Usage:
    uv run python -m claude_code.validate_setup
    uv run python -m claude_code.validate_setup --headless
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# Fix Windows encoding before importing Rich
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv, find_dotenv

# Ensure .env is loaded from workspace root
load_dotenv(find_dotenv(usecwd=True))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text


console = Console(force_terminal=True, legacy_windows=False)


# All paths are relative to this file's parent directory (claude_code/)
BASE_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_file_exists(path: Path, description: str) -> bool:
    """Check if a required file exists and report the result."""
    exists = path.exists()
    status = "[green][OK][/green]" if exists else "[red][FAIL][/red]"
    console.print(f"  {status} {description}: [dim]{path.relative_to(BASE_DIR)}[/dim]")
    return exists


def check_json_valid(path: Path, description: str) -> bool:
    """Check if a JSON file is syntactically valid."""
    if not path.exists():
        console.print(f"  [red][FAIL][/red] {description}: file missing")
        return False
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        console.print(f"  [green][OK][/green] {description}: valid JSON ({len(data)} top-level keys)")
        return True
    except json.JSONDecodeError as e:
        console.print(f"  [red][FAIL][/red] {description}: invalid JSON — {e}")
        return False


def check_claude_md_content(path: Path, expected_sections: list[str]) -> bool:
    """Check that a CLAUDE.md file contains expected sections."""
    if not path.exists():
        console.print(f"  [red][FAIL][/red] CLAUDE.md missing: {path.relative_to(BASE_DIR)}")
        return False

    content = path.read_text(encoding="utf-8")
    found = []
    missing = []
    for section in expected_sections:
        if section.lower() in content.lower():
            found.append(section)
        else:
            missing.append(section)

    if missing:
        console.print(
            f"  [yellow][!][/yellow] CLAUDE.md at [dim]{path.relative_to(BASE_DIR)}[/dim]: "
            f"missing sections: {', '.join(missing)}"
        )
        return False

    console.print(
        f"  [green][OK][/green] CLAUDE.md at [dim]{path.relative_to(BASE_DIR)}[/dim]: "
        f"all {len(found)} expected sections found"
    )
    return True


def check_settings_permissions(path: Path) -> bool:
    """Check that settings.json has allow and deny rules."""
    if not path.exists():
        return False

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    permissions = data.get("permissions", {})
    allow_count = len(permissions.get("allow", []))
    deny_count = len(permissions.get("deny", []))

    if allow_count == 0 and deny_count == 0:
        console.print("  [yellow][!][/yellow] settings.json has no permission rules")
        return False

    console.print(
        f"  [green][OK][/green] settings.json: "
        f"{allow_count} allow rules, {deny_count} deny rules"
    )
    return True


def check_custom_commands(commands_dir: Path) -> bool:
    """Check that custom commands exist in .claude/commands/."""
    if not commands_dir.exists():
        console.print("  [red][FAIL][/red] No .claude/commands/ directory")
        return False

    commands = list(commands_dir.glob("*.md"))
    if not commands:
        console.print("  [yellow][!][/yellow] .claude/commands/ exists but has no .md files")
        return False

    for cmd_file in commands:
        name = cmd_file.stem
        console.print(
            f"  [green][OK][/green] Custom command: "
            f"/project:{name} <- [dim]{cmd_file.relative_to(BASE_DIR)}[/dim]"
        )
    return True


def check_env_api_key() -> bool:
    """Check that .env exists and ANTHROPIC_API_KEY is configured."""
    repo_root = BASE_DIR.parent
    env_file = repo_root / ".env"
    if not env_file.exists():
        console.print("  [yellow][!][/yellow] .env file not found at repository root")
        return False

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or api_key.startswith("sk-ant-your"):
        console.print("  [yellow][!][/yellow] .env found, but ANTHROPIC_API_KEY is placeholder or not set")
        return False

    masked = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
    console.print(f"  [green][OK][/green] ANTHROPIC_API_KEY loaded from .env: [dim]{masked}[/dim]")
    return True


def check_headless_mode() -> bool:
    """Check if Claude Code CLI is available and can run in headless mode."""
    console.print("\n[bold]Running headless mode test...[/bold]")

    env = os.environ.copy()

    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
        if result.returncode != 0:
            console.print("  [red][FAIL][/red] 'claude --version' failed")
            return False

        version = result.stdout.strip()
        console.print(f"  [green][OK][/green] Claude Code CLI: {version}")
    except FileNotFoundError:
        console.print("  [red][FAIL][/red] 'claude' not found on PATH")
        return False
    except subprocess.TimeoutExpired:
        console.print("  [red][FAIL][/red] 'claude --version' timed out")
        return False

    # Run a simple headless prompt
    console.print("  [dim]Running: claude -p 'Say hello in one sentence'[/dim]")
    try:
        result = subprocess.run(
            ["claude", "-p", "Say hello in one sentence"],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        if result.returncode == 0 and result.stdout.strip():
            output = result.stdout.strip()
            if len(output) > 100:
                output = output[:100] + "..."
            console.print(f"  [green][OK][/green] Headless response: {output}")
            return True
        else:
            console.print(f"  [yellow][!][/yellow] Headless returned code {result.returncode}")
            if result.stderr:
                console.print(f"      stderr: {result.stderr.strip()[:200]}")
            return False
    except subprocess.TimeoutExpired:
        console.print("  [yellow]![/yellow] Headless prompt timed out (60s)")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run all validation checks."""
    run_headless = "--headless" in sys.argv

    console.print(Panel(
        "[bold]Claude Code — Setup Validator[/bold]\n"
        "Checks that all configuration files are present and valid.",
        border_style="blue",
    ))

    results: dict[str, bool] = {}

    # --- 1. CLAUDE.md Hierarchy ---
    console.print("\n[bold cyan]1. CLAUDE.md Hierarchy[/bold cyan]")
    results["project_claude_md"] = check_claude_md_content(
        BASE_DIR / "CLAUDE.md",
        ["Build & Run", "Coding Standards", "Environment"],
    )
    results["directory_claude_md"] = check_claude_md_content(
        BASE_DIR / "sample_subfolder" / "CLAUDE.md",
        ["Architecture Rules", "Hooks & Subagents", "Naming Conventions"],
    )

    # --- 2. Settings ---
    console.print("\n[bold cyan]2. Settings Files[/bold cyan]")
    results["settings_exists"] = check_file_exists(
        BASE_DIR / ".claude" / "settings.json", "Shared project settings"
    )
    results["settings_valid"] = check_json_valid(
        BASE_DIR / ".claude" / "settings.json", "settings.json syntax"
    )
    results["settings_permissions"] = check_settings_permissions(
        BASE_DIR / ".claude" / "settings.json"
    )
    results["local_settings"] = check_file_exists(
        BASE_DIR / ".claude" / "settings.local.json", "Local settings (personal)"
    )

    # --- 3. Custom Commands ---
    console.print("\n[bold cyan]3. Custom Slash Commands[/bold cyan]")
    results["commands"] = check_custom_commands(BASE_DIR / ".claude" / "commands")

    # --- 4. Headless Mode Scripts ---
    console.print("\n[bold cyan]4. Headless Mode Scripts[/bold cyan]")
    results["headless_py"] = check_file_exists(
        BASE_DIR / "scripts" / "headless_summary.py", "Python headless script"
    )
    results["headless_ps1"] = check_file_exists(
        BASE_DIR / "scripts" / "headless_summary.ps1", "PowerShell headless script"
    )

    # --- 5. Memory Verification Guide ---
    console.print("\n[bold cyan]5. Memory Verification[/bold cyan]")
    results["verify_guide"] = check_file_exists(
        BASE_DIR / "verify_memory.md", "Memory verification guide"
    )

    # --- 6. Environment & API Key ---
    console.print("\n[bold cyan]6. Environment & API Key[/bold cyan]")
    results["env_api_key"] = check_env_api_key()

    # --- Optional: Headless Test ---
    if run_headless:
        results["headless_test"] = check_headless_mode()

    # --- Summary ---
    console.print()
    passed = sum(1 for v in results.values() if v)
    total = len(results)

    table = Table(title="Validation Summary", border_style="blue")
    table.add_column("Check", style="bold")
    table.add_column("Status", justify="center")

    for name, ok in results.items():
        label = name.replace("_", " ").title()
        status = "[green]PASS[/green]" if ok else "[red]FAIL[/red]"
        table.add_row(label, status)

    console.print(table)
    console.print(
        f"\n[bold]{passed}/{total} checks passed.[/bold]"
        + (" All good!" if passed == total else " Fix the failures above.")
    )

    if not run_headless:
        console.print(
            "\n[dim]Tip: run with --headless to also test claude -p[/dim]"
        )

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
