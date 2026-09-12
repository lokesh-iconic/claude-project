"""
app/config.py -- Configuration loader.

Reads config.yaml for model version pinning and prompt versioning.
Environment variables override YAML values for deployment flexibility.

Design decision: YAML over .env because prompt versioning requires
nested structures that flat env vars can't express cleanly. The API key
still comes from env (security best practice -- never commit secrets).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))

# ---------------------------------------------------------------------------
# Load config.yaml
# ---------------------------------------------------------------------------

_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


def _load_yaml() -> dict[str, Any]:
    """Load the YAML configuration file."""
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


_config = _load_yaml()


# ---------------------------------------------------------------------------
# Public Config Accessors
# ---------------------------------------------------------------------------

def get_model_name() -> str:
    """Get the pinned model name. Never an alias that could silently change."""
    return (
        os.getenv("CLAUDE_MODEL")
        or os.getenv("ANTHROPIC_MODEL")
        or _config.get("model", {}).get("name", "claude-3-5-sonnet-20241022")
    )


def get_max_tokens() -> int:
    return int(os.getenv(
        "CLAUDE_MAX_TOKENS",
        _config.get("model", {}).get("max_tokens", 2048),
    ))


def get_temperature() -> float:
    return float(os.getenv(
        "CLAUDE_TEMPERATURE",
        _config.get("model", {}).get("temperature", 0.2),
    ))


def get_system_prompt() -> str:
    """
    Get the active system prompt version.

    The active version is selected by config.yaml's prompts.active_version key.
    This means switching prompts is a config change (tracked in git), not a code change.
    """
    prompts = _config.get("prompts", {})
    active_key = prompts.get("active_version", "system_v2")
    prompt_entry = prompts.get(active_key, {})

    if isinstance(prompt_entry, dict):
        return prompt_entry.get("text", "You are a document analyst.")
    return str(prompt_entry)


def get_session_config() -> dict:
    """Get session lifecycle configuration."""
    defaults = {
        "max_history_tokens": 50000,
        "summarize_threshold": 40000,
        "idle_timeout_minutes": 30,
    }
    return {**defaults, **_config.get("session", {})}


def get_cache_config() -> dict:
    """Get prompt caching configuration."""
    defaults = {
        "enabled": True,
        "type": "ephemeral",
        "min_document_length": 500,
    }
    return {**defaults, **_config.get("cache", {})}


def get_api_key() -> str | None:
    """
    Get the Anthropic API key from environment.
    Returns None if not set or placeholder.
    """
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key or key.startswith("sk-ant-your"):
        return None
    return key


def is_mock_mode() -> bool:
    """True if no valid API key is configured."""
    return get_api_key() is None
