"""
core/hitl.py — HARROW HITL gate manager.

This is the ONLY place to fire HITL gates. Never inline gate logic.
Gates pause jobs at irreversible actions until human approval.

Hard stop conditions:
1. Stage 4/5 pipeline action
2. Outbound voice call brief
3. Social content publish
4. Paid ad campaign brief
5. New copy template — first live use
6. Reply with pricing/legal language
7. Enterprise tooling on site
8. Opt-out detected
9. 3-Failure Gate (DissonanceInquiry)

Also implements 3-Failure Gate tracking:
- track_rejection(output_type, job_id)
- On 3rd rejection: fire_dissonance_inquiry()
"""

import json
from datetime import datetime, timezone
from typing import Optional
from core.db import get_db
from core.logging import alog


def fire_hitl(
    trigger: str,
    *,
    job_id: Optional[str] = None,
    channel: Optional[str] = None,
    context: Optional[dict] = None,
    recommended: Optional[str] = None,
) -> int:
    """
    Fire a HITL gate. Returns gate ID.
    The calling task should pause until this gate is resolved.
    """
    now = datetime.now(timezone.utc).isoformat()
    context_json = json.dumps(context) if context else None
    with get_db() as db:
        cursor = db.execute(
            """INSERT INTO hitl_gates
               (job_id, channel, trigger, context, recommended, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
            (job_id, channel, trigger, context_json, recommended, now),
        )
        gate_id = cursor.lastrowid

    alog(
        "GATE",
        f"HITL gate fired: {trigger}. To approve: POST /gates/{gate_id}/resolve",
        job_id=job_id, channel=channel, step="hitl_fire",
        action="fire_gate", outcome=f"gate_{gate_id}_pending",
    )
    return gate_id


def resolve_gate(gate_id: int, resolved_by: str = "adrian") -> Optional[dict]:
    """
    Resolve a pending HITL gate. Returns the resolved gate dict,
    or None if not found or already resolved.
    """
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM hitl_gates WHERE id = ? AND status = 'pending'",
            (gate_id,),
        ).fetchone()
        if not row:
            return None
        db.execute(
            "UPDATE hitl_gates SET status = 'resolved', resolved_at = ?, resolved_by = ? WHERE id = ?",
            (now, resolved_by, gate_id),
        )
        updated = db.execute("SELECT * FROM hitl_gates WHERE id = ?", (gate_id,)).fetchone()

    gate = dict(updated)
    alog(
        "GATE",
        f"HITL gate resolved: {gate['trigger']} by {resolved_by}",
        job_id=gate.get("job_id"), channel=gate.get("channel"),
        step="hitl_resolve", action="resolve_gate",
        outcome=f"gate_{gate_id}_resolved",
    )
    return gate


def get_pending_gates(channel: Optional[str] = None) -> list[dict]:
    """Return all pending HITL gates, optionally filtered by channel."""
    clauses = ["status = 'pending'"]
    params: list = []
    if channel:
        clauses.append("channel = ?")
        params.append(channel)

    where = f"WHERE {' AND '.join(clauses)}"
    with get_db() as db:
        rows = db.execute(
            f"SELECT * FROM hitl_gates {where} ORDER BY created_at ASC", params
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_gates(status: Optional[str] = None, limit: int = 50) -> list[dict]:
    """Return gates with optional status filter."""
    clauses: list[str] = []
    params: list = []
    if status:
        clauses.append("status = ?")
        params.append(status)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM hitl_gates {where} ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with get_db() as db:
        rows = db.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def track_rejection(output_type: str, job_id: Optional[str] = None) -> int:
    """
    Record a rejection. Returns the new failure_count for this output_type.
    If count reaches 3, caller should fire_dissonance_inquiry().
    """
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        row = db.execute(
            "SELECT MAX(failure_count) as cnt FROM rejection_log WHERE output_type = ?",
            (output_type,),
        ).fetchone()
        current = row["cnt"] if row and row["cnt"] else 0
        new_count = current + 1
        db.execute(
            "INSERT INTO rejection_log (output_type, job_id, rejected_at, failure_count) VALUES (?, ?, ?, ?)",
            (output_type, job_id, now, new_count),
        )

    alog(
        "WARN", f"Rejection #{new_count} for {output_type}",
        job_id=job_id, step="rejection_track",
        action="track_rejection", outcome=f"count_{new_count}",
    )
    return new_count


def fire_dissonance_inquiry(output_type: str, job_id: Optional[str] = None) -> int:
    """
    3-Failure Gate — fires when an output_type has been rejected 3 times.
    Returns the gate ID. This gate has special handling — no One-Touch.
    """
    return fire_hitl(
        trigger=f"DissonanceInquiry: {output_type} rejected 3 times",
        job_id=job_id,
        context={"output_type": output_type, "failure_count": 3},
        recommended=f"Review and revise the {output_type} generation prompt or parameters. "
                     "Three consecutive rejections suggest a systemic issue.",
    )
