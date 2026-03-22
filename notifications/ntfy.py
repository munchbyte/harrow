"""
notifications/ntfy.py — HARROW One-Touch Receipt via ntfy.sh.

Mobile push notification on HITL gate fire. Signed approve link.
Auto-log decision to Memory Log.

Functions:
- send_gate_notification(gate) — POST to ntfy.sh topic with gate summary
- generate_approve_url(gate_id) -> str — signed URL with HMAC + TTL (4 hours)
- verify_approve_token(token) -> (gate_id, valid) — check HMAC and TTL

Destructive gates excluded from One-Touch:
- Opt-out (-99)
- Stage 5 handoff
- Dissonance inquiry

Env vars: NTFY_TOPIC, NTFY_SECRET. If not configured, skip silently (log INFO).
All One-Touch approvals logged with resolver=one_touch_receipt.
"""

import os
import time
import hmac
import hashlib
import base64
import json
from typing import Optional, Tuple

import requests

from core.logging import alog
from core.log_sync import write_memory_log

# TTL for approve URLs (4 hours)
APPROVE_TTL_SECONDS = 4 * 60 * 60

# Destructive gate triggers that should NOT get One-Touch
_DESTRUCTIVE_TRIGGERS = [
    "opt-out",
    "opt_out",
    "dissonanceinquiry",
    "stage 5 handoff",
]

# Base URL for approve links
_BASE_URL = os.environ.get("HARROW_BASE_URL", "https://harrow.attic-tech.co.uk")


def _get_ntfy_config() -> Tuple[str, str]:
    """Return (topic, secret). Empty strings if not configured."""
    return (
        os.environ.get("NTFY_TOPIC", ""),
        os.environ.get("NTFY_SECRET", ""),
    )


def _is_destructive(trigger: str) -> bool:
    """Check if a gate trigger is destructive (no One-Touch allowed)."""
    lower = trigger.lower()
    return any(dt in lower for dt in _DESTRUCTIVE_TRIGGERS)


def generate_approve_url(gate_id: int) -> str:
    """
    Generate a signed approve URL with HMAC + TTL.
    Token format: base64(gate_id:expiry:signature)
    """
    _, secret = _get_ntfy_config()
    if not secret:
        secret = os.environ.get("HARROW_API_KEY", "fallback-key")

    expiry = int(time.time()) + APPROVE_TTL_SECONDS
    payload = f"{gate_id}:{expiry}"
    signature = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()[:16]

    token = base64.urlsafe_b64encode(
        f"{payload}:{signature}".encode()
    ).decode().rstrip("=")

    return f"{_BASE_URL}/approve/{token}"


def verify_approve_token(token: str) -> Tuple[Optional[int], bool]:
    """
    Verify a signed approve token. Returns (gate_id, is_valid).
    Returns (None, False) if invalid or expired.
    """
    _, secret = _get_ntfy_config()
    if not secret:
        secret = os.environ.get("HARROW_API_KEY", "fallback-key")

    try:
        # Add back padding
        padded = token + "=" * (4 - len(token) % 4)
        decoded = base64.urlsafe_b64decode(padded).decode()
        parts = decoded.split(":")
        if len(parts) != 3:
            return None, False

        gate_id = int(parts[0])
        expiry = int(parts[1])
        signature = parts[2]

        # Check expiry
        if time.time() > expiry:
            alog("WARN", f"Approve token expired for gate {gate_id}",
                 step="one_touch_verify")
            return gate_id, False

        # Verify signature
        payload = f"{gate_id}:{expiry}"
        expected = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()[:16]

        if not hmac.compare_digest(signature, expected):
            alog("WARN", f"Invalid approve token signature for gate {gate_id}",
                 step="one_touch_verify")
            return gate_id, False

        return gate_id, True

    except Exception as e:
        alog("WARN", f"Failed to verify approve token: {e}",
             step="one_touch_verify")
        return None, False


def send_gate_notification(gate: dict) -> bool:
    """
    Send a push notification via ntfy.sh for a HITL gate.
    Returns True if sent, False if skipped or failed.

    Destructive gates are excluded from One-Touch.
    If NTFY_TOPIC not configured, skips silently.
    """
    topic, secret = _get_ntfy_config()
    if not topic:
        alog("INFO", "ntfy.sh not configured — skipping gate notification",
             step="ntfy_send")
        return False

    trigger = gate.get("trigger", "")
    gate_id = gate.get("id")

    # Skip destructive gates
    if _is_destructive(trigger):
        alog("INFO", f"Destructive gate {gate_id} — One-Touch excluded",
             step="ntfy_send")
        return False

    # Build notification
    channel = gate.get("channel", "unknown")
    recommended = gate.get("recommended", "Review and approve.")

    # Generate approve URL
    approve_url = generate_approve_url(gate_id)

    title = f"HARROW Gate #{gate_id} [{channel}]"
    message = (
        f"{trigger}\n\n"
        f"Recommended: {recommended}\n\n"
        f"One-Touch Approve:\n{approve_url}"
    )

    try:
        headers = {"Title": title, "Priority": "high", "Tags": "clipboard,harrow"}
        if secret:
            headers["Authorization"] = f"Bearer {secret}"

        # Add click action for the approve URL
        headers["Click"] = approve_url
        headers["Actions"] = f"http, Approve, {approve_url}, clear=true"

        resp = requests.post(
            f"https://ntfy.sh/{topic}",
            data=message.encode("utf-8"),
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()

        alog("INFO", f"Gate notification sent for gate {gate_id}",
             channel=channel, step="ntfy_send",
             action="send_notification", outcome="sent")

        # Log the notification in memory_log
        write_memory_log(
            event_type="gate_notified",
            channel=channel,
            detail={"gate_id": gate_id, "trigger": trigger, "approve_url": approve_url},
        )

        return True

    except requests.Timeout:
        alog("WARN", f"ntfy.sh timeout for gate {gate_id}",
             step="ntfy_send")
        return False
    except Exception as e:
        alog("ERROR", f"ntfy.sh notification failed: {e}. To resolve this: check NTFY_TOPIC and NTFY_SECRET",
             step="ntfy_send")
        return False
