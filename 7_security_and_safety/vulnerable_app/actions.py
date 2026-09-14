"""
vulnerable_app/actions.py -- Sensitive actions with NO auth or secrets management.

DELIBERATELY VULNERABLE:
  - API key hardcoded as a plaintext string
  - send_email() and delete_user_data() execute without identity/auth checks
  - No audit logging of action attempts

This exists to DEMONSTRATE the anti-pattern, not as a pattern to follow.
"""

from __future__ import annotations


# ── VULNERABILITY: Hardcoded API key in plaintext ────────────────────
INTERNAL_API_KEY = "sk-ant-api03-FAKE_HARDCODED_KEY_12345_DO_NOT_USE"
DATABASE_PASSWORD = "admin_password_plaintext_bad"
# Any tool reading this source file or logs can extract these secrets.


def send_email(recipient: str, subject: str, body: str) -> dict:
    """
    Send an email -- NO AUTHENTICATION REQUIRED.

    Anyone (including an injected prompt) can trigger this action.
    No identity check, no permission check, no audit trail.
    """
    # In a real app this would actually send an email.
    # The vulnerability is that there's NO check on who is calling this.
    return {
        "status": "sent",
        "recipient": recipient,
        "subject": subject,
        "body_preview": body[:100],
        "auth_required": False,  # ← the problem
        "auth_performed": False,
    }


def delete_user_data(user_id: str) -> dict:
    """
    Delete a user's data -- NO AUTHENTICATION REQUIRED.

    Destructive action with zero access control.
    """
    return {
        "status": "deleted",
        "user_id": user_id,
        "records_removed": 42,  # simulated
        "auth_required": False,
        "auth_performed": False,
    }


def get_system_config() -> dict:
    """
    Return internal system configuration -- NO ACCESS CONTROL.

    Exposes secrets in plaintext because they're hardcoded above.
    """
    return {
        "api_key": INTERNAL_API_KEY,       # ← leaked
        "db_password": DATABASE_PASSWORD,   # ← leaked
        "model": "claude-sonnet-4-20250514",
        "mode": "vulnerable",
    }
