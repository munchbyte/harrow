"""
core/logging.py — HARROW structured logging.

All logs go through alog(). Never use print().
Writes to agent_logs table. ASP-003 compliant.
Levels: INFO, WARN, ERROR, GATE.
Every ERROR entry must end with 'To resolve this:'.
Every GATE entry must end with 'To approve: [exact instruction]'.
"""

from datetime import datetime, timezone
from typing import Optional
from core.db import get_db


def alog(
    level: str,
    message: str,
    *,
    job_id: Optional[str] = None,
    caller: Optional[str] = None,
    step: Optional[str] = None,
    action: Optional[str] = None,
    outcome: Optional[str] = None,
    channel: Optional[str] = None,
) -> None:
    """Write one structured log entry to agent_logs. Never raises."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            db.execute(
                """INSERT INTO agent_logs
                   (timestamp, level, agent_id, job_id, caller, step, message, action, outcome, channel)
                   VALUES (?, ?, 'harrow', ?, ?, ?, ?, ?, ?, ?)""",
                (now, level.upper(), job_id, caller, step, message, action, outcome, channel),
            )
    except Exception:
        # Last resort — logging must never crash the agent
        pass


def get_logs(
    *,
    channel: Optional[str] = None,
    level: Optional[str] = None,
    job_id: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Query agent_logs with optional filters. Returns list of dicts."""
    clauses: list[str] = []
    params: list = []
    if channel:
        clauses.append("channel = ?")
        params.append(channel)
    if level:
        clauses.append("level = ?")
        params.append(level.upper())
    if job_id:
        clauses.append("job_id = ?")
        params.append(job_id)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM agent_logs {where} ORDER BY id DESC LIMIT ?"
    params.append(limit)

    with get_db() as db:
        rows = db.execute(sql, params).fetchall()
    return [dict(r) for r in rows]
