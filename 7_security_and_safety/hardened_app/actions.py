"""
hardened_app/actions.py -- Sensitive actions WITH identity/access validation.

Every action that has real consequences requires:
  1. A valid user token mapping to an authorized user
  2. The user having the specific permission for that action
  3. An audit log entry for every attempt (success or failure)

API keys are loaded from environment variables, never hardcoded.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone


# ──────────────────────────────────────────────────────────────────────
# Secrets management -- loaded from environment, never hardcoded
# ──────────────────────────────────────────────────────────────────────

def _get_api_key() -> str:
    """
    Load API key from environment variable.

    NEVER hardcode secrets in source code. Use os.environ / dotenv.
    If the key isn't set, return a placeholder (mock mode).
    """
    return os.environ.get("ANTHROPIC_API_KEY", "NOT_SET")


# ──────────────────────────────────────────────────────────────────────
# Identity / access validation
# ──────────────────────────────────────────────────────────────────────

# Simulated user registry (in production: JWT validation, OAuth, etc.)
_AUTHORIZED_USERS: dict[str, dict] = {
    "token_admin_001": {
        "user_id": "admin@company.com",
        "role": "admin",
        "permissions": {"send_email", "delete_user_data", "view_config"},
    },
    "token_user_042": {
        "user_id": "analyst@company.com",
        "role": "analyst",
        "permissions": {"send_email"},  # can send email, but NOT delete data
    },
}

# Audit log (in production: persistent storage)
_audit_log: list[dict] = []


def _validate_identity(user_token: str | None) -> dict | None:
    """
    Validate a user token and return the user record.

    Returns None if the token is invalid or missing.
    """
    if not user_token:
        return None
    return _AUTHORIZED_USERS.get(user_token)


def _check_permission(user: dict, required_permission: str) -> bool:
    """Check whether a user has a specific permission."""
    return required_permission in user.get("permissions", set())


def _audit(action: str, user_token: str | None, user: dict | None,
           authorized: bool, detail: str):
    """
    Log every action attempt -- successful or blocked.

    In production this goes to a secure, append-only audit store.
    Secrets are NEVER included in audit entries.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "user_id": user["user_id"] if user else "UNKNOWN",
        "role": user["role"] if user else "NONE",
        "authorized": authorized,
        "detail": detail,
        # NOTE: we log that a token was provided, NOT the token itself
        "token_provided": user_token is not None,
    }
    _audit_log.append(entry)
    return entry


# ──────────────────────────────────────────────────────────────────────
# Secured actions
# ──────────────────────────────────────────────────────────────────────

def send_email(recipient: str, subject: str, body: str,
               user_token: str | None = None) -> dict:
    """
    Send an email -- REQUIRES AUTHENTICATION AND AUTHORIZATION.

    Steps:
    1. Validate the user token
    2. Check 'send_email' permission
    3. Audit the attempt
    4. Execute only if authorized
    """
    user = _validate_identity(user_token)

    if user is None:
        audit_entry = _audit("send_email", user_token, None, False,
                             f"Blocked: invalid or missing token. recipient={recipient}")
        return {
            "status": "blocked",
            "reason": "Authentication required — valid user token not provided",
            "auth_required": True,
            "auth_performed": True,
            "audit": audit_entry,
        }

    if not _check_permission(user, "send_email"):
        audit_entry = _audit("send_email", user_token, user, False,
                             f"Blocked: insufficient permissions. recipient={recipient}")
        return {
            "status": "blocked",
            "reason": f"User '{user['user_id']}' lacks 'send_email' permission",
            "auth_required": True,
            "auth_performed": True,
            "audit": audit_entry,
        }

    # Authorized -- execute
    audit_entry = _audit("send_email", user_token, user, True,
                         f"Email sent to {recipient}")
    return {
        "status": "sent",
        "recipient": recipient,
        "subject": subject,
        "body_preview": body[:100],
        "sent_by": user["user_id"],
        "auth_required": True,
        "auth_performed": True,
        "audit": audit_entry,
    }


def delete_user_data(user_id: str,
                     user_token: str | None = None) -> dict:
    """
    Delete a user's data -- REQUIRES ADMIN AUTHENTICATION.

    Only users with 'delete_user_data' permission (typically admins)
    can execute this destructive action.
    """
    user = _validate_identity(user_token)

    if user is None:
        audit_entry = _audit("delete_user_data", user_token, None, False,
                             f"Blocked: invalid or missing token. target={user_id}")
        return {
            "status": "blocked",
            "reason": "Authentication required — valid user token not provided",
            "auth_required": True,
            "auth_performed": True,
            "audit": audit_entry,
        }

    if not _check_permission(user, "delete_user_data"):
        audit_entry = _audit("delete_user_data", user_token, user, False,
                             f"Blocked: insufficient permissions. target={user_id}")
        return {
            "status": "blocked",
            "reason": f"User '{user['user_id']}' lacks 'delete_user_data' permission",
            "auth_required": True,
            "auth_performed": True,
            "audit": audit_entry,
        }

    # Authorized -- execute
    audit_entry = _audit("delete_user_data", user_token, user, True,
                         f"Data deleted for user {user_id}")
    return {
        "status": "deleted",
        "user_id": user_id,
        "records_removed": 42,
        "deleted_by": user["user_id"],
        "auth_required": True,
        "auth_performed": True,
        "audit": audit_entry,
    }


def get_system_config(user_token: str | None = None) -> dict:
    """
    Return system configuration -- REQUIRES ADMIN AUTH.

    Even when authorized, API keys are masked in the response.
    """
    user = _validate_identity(user_token)

    if user is None or not _check_permission(user, "view_config"):
        _audit("get_system_config", user_token, user, False,
               "Blocked: authentication or permission failure")
        return {
            "status": "blocked",
            "reason": "Authentication and 'view_config' permission required",
        }

    # Authorized -- but keys are MASKED, never exposed in full
    api_key = _get_api_key()
    masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"

    _audit("get_system_config", user_token, user, True,
           "Config retrieved (secrets masked)")
    return {
        "api_key": masked_key,         # ← masked, not plaintext
        "model": os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
        "mode": "hardened",
        "retrieved_by": user["user_id"],
    }


def get_audit_log() -> list[dict]:
    """Return the full audit log (for inspection/testing)."""
    return list(_audit_log)


def clear_audit_log():
    """Clear the audit log (for testing only)."""
    _audit_log.clear()
