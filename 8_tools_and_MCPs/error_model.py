"""
error_model.py — Structured error format shared by all three implementations.

Every implementation (custom tool, skill, MCP server) returns errors in the
same shape so they can be compared directly.

Format:
    {
        "error": {
            "category": "not_found" | "invalid_input" | "internal_error",
            "retryable": bool,
            "description": str
        }
    }
"""

from __future__ import annotations


def make_error(category: str, description: str, retryable: bool = False) -> dict:
    """Create a structured error response."""
    return {
        "error": {
            "category": category,
            "retryable": retryable,
            "description": description,
        }
    }


def not_found(sku: str) -> dict:
    """Product not found error."""
    return make_error(
        category="not_found",
        description=f"No product found with SKU '{sku}'",
        retryable=False,
    )


def invalid_input(message: str) -> dict:
    """Invalid input error."""
    return make_error(
        category="invalid_input",
        description=message,
        retryable=False,
    )


def internal_error(message: str) -> dict:
    """Internal server error."""
    return make_error(
        category="internal_error",
        description=message,
        retryable=True,
    )


def is_error(result: dict) -> bool:
    """Check if a result is an error response."""
    return "error" in result and isinstance(result["error"], dict)
