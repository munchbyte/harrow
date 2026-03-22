"""
core/go_state.py — HARROW GO flag manager.

Per-channel GO state: email, voice, social, ads.
Each channel has an independent armed/revoked state.
State persisted in SQLite go_state table. Survives server restarts.
"""

from datetime import datetime, timezone
from typing import Optional
from core.db import get_db
from core.logging import alog

VALID_CHANNELS = {"email", "voice", "social", "ads"}


def _validate_channel(channel: str) -> None:
    """Raise ValueError if channel is not one of the four valid channels."""
    if channel not in VALID_CHANNELS:
        raise ValueError(
            f"Invalid channel '{channel}'. Must be one of: {', '.join(sorted(VALID_CHANNELS))}"
        )


def arm_channel(channel: str, armed_by: str = "adrian") -> dict:
    """Arm a channel GO flag. Returns new state."""
    _validate_channel(channel)
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        db.execute(
            "UPDATE go_state SET armed = 1, armed_at = ?, armed_by = ? WHERE channel = ?",
            (now, armed_by, channel),
        )
    alog(
        "INFO", f"GO armed: {channel}",
        caller=armed_by, channel=channel, step="go_arm",
        action=f"arm_{channel}", outcome="armed",
    )
    return {"channel": channel, "armed": True, "armed_at": now, "armed_by": armed_by}


def revoke_channel(channel: str) -> dict:
    """Revoke a channel GO flag immediately. Returns new state."""
    _validate_channel(channel)
    with get_db() as db:
        db.execute(
            "UPDATE go_state SET armed = 0, armed_at = NULL, armed_by = NULL WHERE channel = ?",
            (channel,),
        )
    alog(
        "WARN", f"GO revoked: {channel}",
        channel=channel, step="go_revoke",
        action=f"revoke_{channel}", outcome="revoked",
    )
    return {"channel": channel, "armed": False}


def is_armed(channel: str) -> bool:
    """Check if a channel is currently armed."""
    _validate_channel(channel)
    with get_db() as db:
        row = db.execute("SELECT armed FROM go_state WHERE channel = ?", (channel,)).fetchone()
    return bool(row and row["armed"])


def get_all_go_states() -> dict:
    """Return all four channel GO states as a dict."""
    with get_db() as db:
        rows = db.execute("SELECT * FROM go_state ORDER BY channel").fetchall()
    result = {}
    for row in rows:
        r = dict(row)
        result[r["channel"]] = {
            "armed": bool(r["armed"]),
            "armed_at": r["armed_at"],
            "armed_by": r["armed_by"],
        }
    return result
