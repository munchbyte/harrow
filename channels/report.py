"""
channels/report.py — HARROW Channel Report.

Generates a cross-channel status report:
- Per-channel GO state
- Pending HITL gates
- Recent job activity
- Memory log summary
- Campaign status

Task: task_channel_report(job_id, params, caller)
"""

from core.logging import alog, get_logs
from core.jobs import update_job, list_jobs
from core.go_state import get_all_go_states
from core.hitl import get_pending_gates, get_all_gates
from core.log_sync import get_memory_log
from core.db import get_db


async def task_channel_report(job_id: str, params: dict, caller: str) -> dict:
    """Generate a cross-channel status report."""
    update_job(job_id, progress="Generating channel report...")

    # GO states
    go_states = get_all_go_states()

    # Pending gates
    pending = get_pending_gates()

    # Recent jobs per channel
    channels = ["lead_gen", "email", "voice", "social", "ads"]
    jobs_by_channel = {}
    for ch in channels:
        jobs = list_jobs(channel=ch, limit=5)
        jobs_by_channel[ch] = {
            "total": len(jobs),
            "running": len([j for j in jobs if j["status"] == "running"]),
            "complete": len([j for j in jobs if j["status"] == "complete"]),
            "failed": len([j for j in jobs if j["status"] == "failed"]),
        }

    # Memory log summary
    with get_db() as db:
        m1_count = db.execute("SELECT COUNT(*) as c FROM memory_log WHERE event_type = 'm1_sent'").fetchone()["c"]
        m2_count = db.execute("SELECT COUNT(*) as c FROM memory_log WHERE event_type = 'm2_sent'").fetchone()["c"]
        m3_count = db.execute("SELECT COUNT(*) as c FROM memory_log WHERE event_type = 'm3_sent'").fetchone()["c"]
        opt_outs = db.execute("SELECT COUNT(*) as c FROM memory_log WHERE event_type = 'opt_out'").fetchone()["c"]

    # Active campaigns
    with get_db() as db:
        campaigns = db.execute(
            "SELECT id, name, status, created_at FROM campaigns ORDER BY id DESC LIMIT 5"
        ).fetchall()

    campaign_list = [dict(c) for c in campaigns]

    # Error count (last 24h)
    error_logs = get_logs(level="ERROR", limit=100)

    report = {
        "go_states": go_states,
        "pending_gates": len(pending),
        "gates_detail": [
            {"id": g["id"], "trigger": g["trigger"], "channel": g.get("channel")}
            for g in pending[:10]
        ],
        "jobs_by_channel": jobs_by_channel,
        "email_pipeline": {
            "m1_sent": m1_count,
            "m2_sent": m2_count,
            "m3_sent": m3_count,
            "opt_outs": opt_outs,
        },
        "recent_campaigns": campaign_list,
        "error_count_recent": len(error_logs),
    }

    alog("INFO", "Channel report generated", job_id=job_id, caller=caller, step="channel_report")
    return report
