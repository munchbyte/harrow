"""
core/log_sync.py — HARROW Log-Sync Auto (ASP-003_Sync).

This is the ONLY place for [HARROW->LOG_SYNC] writes.
Writes to the memory_log table. Append-only — no updates, no deletes.

Called automatically after:
- Successful PUSH (email send)
- HITL gate resolved
- Opt-out received
- Stage advance

Routing signal: [HARROW->LOG_SYNC] written to agent_logs on every call.
"""

import json
from datetime import datetime, timezone
from typing import Optional, Any
from core.db import get_db
from core.logging import alog


def write_memory_log(
    event_type: str,
    *,
    job_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    channel: Optional[str] = None,
    detail: Optional[Any] = None,
) -> int:
    """
    Write one entry to the memory_log table. Returns the row ID.
    Append-only — no updates, no deletes.

    Also writes routing signal [HARROW->LOG_SYNC] to agent_logs.
    """
    now = datetime.now(timezone.utc).isoformat()
    detail_json = json.dumps(detail) if detail is not None else None

    with get_db() as db:
        cursor = db.execute(
            """INSERT INTO memory_log (event_type, job_id, lead_id, channel, detail, logged_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (event_type, job_id, lead_id, channel, detail_json, now),
        )
        row_id = cursor.lastrowid

    # Routing signal
    alog(
        "INFO",
        f"[HARROW->LOG_SYNC] {event_type} logged (id={row_id})",
        job_id=job_id,
        channel=channel,
        step="log_sync",
        action="write_memory_log",
        outcome=f"memory_log_{row_id}",
    )

    return row_id


def get_memory_log(
    *,
    event_type: Optional[str] = None,
    lead_id: Optional[str] = None,
    channel: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Query memory_log with optional filters. Most recent first."""
    clauses: list[str] = []
    params: list = []

    if event_type:
        clauses.append("event_type = ?")
        params.append(event_type)
    if lead_id:
        clauses.append("lead_id = ?")
        params.append(lead_id)
    if channel:
        clauses.append("channel = ?")
        params.append(channel)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM memory_log {where} ORDER BY id DESC LIMIT ?"
    params.append(limit)

    with get_db() as db:
        rows = db.execute(sql, params).fetchall()
    return [dict(r) for r in rows]
