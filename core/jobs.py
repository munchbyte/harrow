"""
core/jobs.py — HARROW job manager.

Creates, updates, and queries job records in the jobs table.
Every /run call creates a job. Background tasks update progress and result.
"""

import uuid
import json
from datetime import datetime, timezone
from typing import Optional, Any
from core.db import get_db
from core.logging import alog


def create_job(task: str, caller: str, channel: Optional[str] = None) -> str:
    """Create a new job record. Returns job_id (UUID)."""
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        db.execute(
            """INSERT INTO jobs (job_id, task, caller, status, channel, created_at)
               VALUES (?, ?, ?, 'running', ?, ?)""",
            (job_id, task, caller, channel, now),
        )
    alog("INFO", f"Job created: {task}", job_id=job_id, caller=caller, channel=channel, step="job_create")
    return job_id


def update_job(
    job_id: str,
    *,
    status: Optional[str] = None,
    progress: Optional[str] = None,
    result: Optional[Any] = None,
    error: Optional[str] = None,
) -> None:
    """Update a job's status, progress, result, or error."""
    now = datetime.now(timezone.utc).isoformat()
    sets: list[str] = ["updated_at = ?"]
    params: list = [now]

    if status is not None:
        sets.append("status = ?")
        params.append(status)
    if progress is not None:
        sets.append("progress = ?")
        params.append(progress)
    if result is not None:
        sets.append("result = ?")
        params.append(json.dumps(result) if not isinstance(result, str) else result)
    if error is not None:
        sets.append("error = ?")
        params.append(error)

    params.append(job_id)
    sql = f"UPDATE jobs SET {', '.join(sets)} WHERE job_id = ?"

    with get_db() as db:
        db.execute(sql, params)


def get_job(job_id: str) -> Optional[dict]:
    """Return a single job as dict, or None if not found."""
    with get_db() as db:
        row = db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    return dict(row) if row else None


def list_jobs(
    *,
    status: Optional[str] = None,
    channel: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """List jobs with optional filters. Most recent first."""
    clauses: list[str] = []
    params: list = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if channel:
        clauses.append("channel = ?")
        params.append(channel)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM jobs {where} ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with get_db() as db:
        rows = db.execute(sql, params).fetchall()
    return [dict(r) for r in rows]
