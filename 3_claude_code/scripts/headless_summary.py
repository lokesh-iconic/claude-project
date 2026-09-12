"""
headless_summary.py — Run Claude Code in headless mode (-p) and capture output.

Demonstrates programmatic usage of Claude Code inside a script or pipeline.
Claude Code's -p flag runs a single prompt without an interactive session
and prints the result to stdout, making it suitable for CI/CD, cron jobs,
or any automation workflow.

Usage:
    uv run python 3_claude_code/scripts/headless_summary.py

What it does:
    1. Runs `claude -p "..."` as a subprocess
    2. Captures the structured output
    3. Saves the result to 3_claude_code/scripts/output/headless_result.txt
    4. Prints a summary to the console
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv, find_dotenv

# Ensure .env is loaded from workspace root
load_dotenv(find_dotenv(usecwd=True), override=True)


def run_headless(prompt: str, output_format: str = "text") -> str:
    """
    Run Claude Code in headless mode with the given prompt.

    Args:
        prompt: The instruction to send to Claude Code.
        output_format: Output format — "text" (default) or "json".

    Returns:
        The raw output from Claude Code.

    Raises:
        subprocess.CalledProcessError: If Claude Code exits with a non-zero code.
    """
    cmd = ["claude", "-p", prompt]
    if output_format == "json":
        cmd.extend(["--output-format", "json"])

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,  # 2-minute timeout for safety
        env=os.environ.copy(),
    )

    if result.returncode != 0:
        print(f"[ERROR] Claude Code exited with code {result.returncode}", file=sys.stderr)
        print(f"[STDERR] {result.stderr}", file=sys.stderr)
        # Still return stdout — partial output may be useful
        return result.stdout

    return result.stdout


def save_output(content: str, output_dir: Path) -> Path:
    """Save headless output to a timestamped file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"headless_result_{timestamp}.txt"
    output_file.write_text(content, encoding="utf-8")
    return output_file


def main() -> None:
    """Run a headless Claude Code task and capture the output."""
    # Define the prompt — this could come from CLI args, a config file, etc.
    prompt = (
        "List the Python files in this project and give a one-sentence "
        "description of what each file does. Format as a markdown table."
    )

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    key_status = f"Loaded from .env ({api_key[:8]}...{api_key[-4:]})" if api_key else "Not found in .env"

    print("=" * 60)
    print("Claude Code — Headless Mode Demo")
    print(f"API Key: {key_status}")
    print("=" * 60)
    print(f"\nPrompt: {prompt}\n")
    print("Running claude -p ... (this may take a moment)\n")

    # Run in text mode
    output = run_headless(prompt)

    if not output.strip():
        print("[WARNING] No output received from Claude Code.", file=sys.stderr)
        print("Make sure 'claude' is installed and authenticated.", file=sys.stderr)
        sys.exit(1)

    # Save to file
    output_dir = Path(__file__).parent / "output"
    saved_path = save_output(output, output_dir)

    # Print results
    print("-" * 60)
    print("OUTPUT:")
    print("-" * 60)
    print(output)
    print("-" * 60)
    print(f"\nSaved to: {saved_path}")
    print(f"Output length: {len(output)} characters")

    # Also demonstrate JSON output format
    print("\n\nNow running with --output-format json ...")
    json_output = run_headless(
        "What is the project name and Python version from pyproject.toml?",
        output_format="json",
    )

    if json_output.strip():
        try:
            parsed = json.loads(json_output)
            json_file = save_output(
                json.dumps(parsed, indent=2), output_dir
            )
            print(f"JSON output saved to: {json_file}")
        except json.JSONDecodeError:
            # Not all output is valid JSON — that's fine for text responses
            print("(Response was text, not JSON — this is normal for free-form prompts)")
            text_file = save_output(json_output, output_dir)
            print(f"Text output saved to: {text_file}")


if __name__ == "__main__":
    main()
