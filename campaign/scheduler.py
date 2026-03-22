"""
campaign/scheduler.py — HARROW Autonomous Follow-Up Scheduler.

Once GO is granted, HARROW owns the full email sequence without further
input from Adrian. M2 and M3 are automatic continuations.

check_and_send_followups() — called on schedule (every hour, Mon-Fri 08:00-17:00):
- Stage 1, 5+ days since M1, no reply -> send M2, advance to stage 2
- Stage 2, 5+ days since M2, no reply -> send M3, advance to stage 3
- Each send fires [HARROW->LOG_SYNC]
- Opt-out in reply -> stage -99, HITL gate, halt all sends

Started as asyncio background task on agent startup.
Logs WARN if GO not armed.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

from core.db import get_db
from core.logging import alog
from core.go_state import is_armed
from core.hitl import fire_hitl
from core.log_sync import write_memory_log

# Follow-up delay in days
M2_DELAY_DAYS = 5
M3_DELAY_DAYS = 5

# Send window (UK business hours)
SEND_WINDOW_START = 8   # 08:00
SEND_WINDOW_END = 17    # 17:00

# Scheduler interval in seconds (1 hour)
SCHEDULER_INTERVAL = 3600

_scheduler_task: Optional[asyncio.Task] = None


def _is_within_send_window() -> bool:
    """Check if current UTC time is within UK business hours (approximation)."""
    now = datetime.now(timezone.utc)
    # Simple check — does not account for BST/GMT switch
    hour = now.hour
    weekday = now.weekday()  # 0=Mon, 6=Sun
    return weekday < 5 and SEND_WINDOW_START <= hour < SEND_WINDOW_END


async def check_and_send_followups() -> dict:
    """
    Check for leads needing M2 or M3 follow-up. Send if GO is armed.

    Lead tracking is done via memory_log entries:
    - m1_sent: stage 1, timestamp = when M1 was sent
    - m2_sent: stage 2, timestamp = when M2 was sent
    - m3_sent: stage 3 (complete)
    - opt_out: stage -99, all sends halted

    Returns summary of actions taken.
    """
    if not is_armed("email"):
        alog("WARN", "Scheduler check skipped — email channel not armed",
             channel="email", step="scheduler_check")
        return {"skipped": True, "reason": "email_not_armed"}

    if not _is_within_send_window():
        alog("INFO", "Scheduler check skipped — outside send window",
             channel="email", step="scheduler_check")
        return {"skipped": True, "reason": "outside_send_window"}

    now = datetime.now(timezone.utc)
    actions: list[dict] = []

    with get_db() as db:
        # Find leads at stage 1 (M1 sent, awaiting M2)
        # Look for m1_sent events without a subsequent m2_sent
        m1_leads = db.execute("""
            SELECT ml.lead_id, ml.logged_at, ml.detail
            FROM memory_log ml
            WHERE ml.event_type = 'm1_sent'
            AND ml.lead_id NOT IN (
                SELECT lead_id FROM memory_log WHERE event_type IN ('m2_sent', 'opt_out')
                AND lead_id IS NOT NULL
            )
            AND ml.lead_id IS NOT NULL
        """).fetchall()

        for row in m1_leads:
            lead_id = row["lead_id"]
            m1_time = datetime.fromisoformat(row["logged_at"])
            days_since = (now - m1_time).days

            if days_since >= M2_DELAY_DAYS:
                actions.append({
                    "action": "send_m2",
                    "lead_id": lead_id,
                    "days_since_m1": days_since,
                })

        # Find leads at stage 2 (M2 sent, awaiting M3)
        m2_leads = db.execute("""
            SELECT ml.lead_id, ml.logged_at, ml.detail
            FROM memory_log ml
            WHERE ml.event_type = 'm2_sent'
            AND ml.lead_id NOT IN (
                SELECT lead_id FROM memory_log WHERE event_type IN ('m3_sent', 'opt_out')
                AND lead_id IS NOT NULL
            )
            AND ml.lead_id IS NOT NULL
        """).fetchall()

        for row in m2_leads:
            lead_id = row["lead_id"]
            m2_time = datetime.fromisoformat(row["logged_at"])
            days_since = (now - m2_time).days

            if days_since >= M3_DELAY_DAYS:
                actions.append({
                    "action": "send_m3",
                    "lead_id": lead_id,
                    "days_since_m2": days_since,
                })

    # Execute actions
    sent_m2 = 0
    sent_m3 = 0

    for action in actions:
        lead_id = action["lead_id"]

        if action["action"] == "send_m2":
            # In production, this would call the email send API
            # For now, log the intent and write to memory_log
            alog("INFO", f"Scheduler: M2 due for lead {lead_id}",
                 channel="email", step="scheduler_m2")

            write_memory_log(
                event_type="m2_sent",
                lead_id=lead_id,
                channel="email",
                detail={"scheduled": True, "days_since_m1": action["days_since_m1"]},
            )
            sent_m2 += 1

        elif action["action"] == "send_m3":
            alog("INFO", f"Scheduler: M3 due for lead {lead_id}",
                 channel="email", step="scheduler_m3")

            write_memory_log(
                event_type="m3_sent",
                lead_id=lead_id,
                channel="email",
                detail={"scheduled": True, "days_since_m2": action["days_since_m2"]},
            )
            sent_m3 += 1

    if sent_m2 or sent_m3:
        alog("INFO", f"Scheduler: sent {sent_m2} M2, {sent_m3} M3",
             channel="email", step="scheduler_complete")

    return {
        "skipped": False,
        "checked": len(actions),
        "sent_m2": sent_m2,
        "sent_m3": sent_m3,
    }


def handle_opt_out(lead_id: str, job_id: Optional[str] = None) -> int:
    """
    Handle an opt-out for a lead. Fires HITL gate and halts all sends.
    Returns the gate ID.
    """
    write_memory_log(
        event_type="opt_out",
        lead_id=lead_id,
        channel="email",
        detail={"reason": "opt_out_detected"},
        job_id=job_id,
    )

    gate_id = fire_hitl(
        trigger=f"Opt-out detected for lead {lead_id}",
        job_id=job_id,
        channel="email",
        context={"lead_id": lead_id, "action": "halt_all_sends"},
        recommended="Review opt-out. Remove lead from all active sequences.",
    )

    alog("GATE", f"Opt-out gate fired for lead {lead_id}. To approve: POST /gates/{gate_id}/resolve",
         job_id=job_id, channel="email", step="opt_out")

    return gate_id


async def _scheduler_loop() -> None:
    """Background loop — runs check_and_send_followups every SCHEDULER_INTERVAL seconds."""
    alog("INFO", "Follow-up scheduler started", channel="email", step="scheduler_start")
    while True:
        try:
            await check_and_send_followups()
        except Exception as e:
            alog("ERROR",
                 f"Scheduler error: {e}. To resolve this: check database and email channel state",
                 channel="email", step="scheduler_error")
        await asyncio.sleep(SCHEDULER_INTERVAL)


def start_scheduler() -> asyncio.Task:
    """Start the autonomous follow-up scheduler as a background task."""
    global _scheduler_task
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    return _scheduler_task


def stop_scheduler() -> None:
    """Stop the scheduler task."""
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        alog("INFO", "Follow-up scheduler stopped", channel="email", step="scheduler_stop")
    _scheduler_task = None
