"""
routes/asp002.py — HARROW ASP-002 standard endpoints.

Endpoints:
- GET  /health       — alive check, version, uptime (no auth)
- GET  /info         — agent description, capabilities, tasks
- POST /run          — execute task, create job, return job_id
- GET  /status/{id}  — check job progress and result
- GET  /logs         — activity log with ?channel= ?level= ?limit= filters
- POST /stop/{id}    — gracefully stop a running job
- POST /auth         — validate API key, set session cookie

All responses: {status, agent_id, timestamp, data/error}
"""

import time
import asyncio
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core.auth import require_key, validate_and_set_cookie
from core.jobs import create_job, update_job, get_job, list_jobs
from core.logging import alog, get_logs

router = APIRouter()

AGENT_ID = "harrow"
AGENT_VERSION = "1.0.0"
START_TIME = time.time()

# --- Task registry: maps task name -> (handler_func, channel) ---
# Handlers are registered here as they're built in later phases.
# Each handler signature: async handler(job_id: str, params: dict, caller: str) -> dict
_TASK_REGISTRY: dict[str, tuple] = {}


def register_task(name: str, handler, channel: Optional[str] = None) -> None:
    """Register a task handler. Called by channel modules on import."""
    _TASK_REGISTRY[name] = (handler, channel)


def _envelope(data: dict) -> dict:
    """Wrap response in ASP-002 standard envelope."""
    return {
        "status": "ok",
        "agent_id": AGENT_ID,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "data": data,
    }


def _error_envelope(message: str, status_code: int = 400) -> JSONResponse:
    """Return an ASP-002 error envelope."""
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "error",
            "agent_id": AGENT_ID,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "error": message,
        },
    )


# ── GET /info ──────────────────────────────────────────────────────────
@router.get("/info")
async def info(caller: str = Depends(require_key)):
    """Full agent description. Auth required."""
    return _envelope({
        "agent_id": AGENT_ID,
        "name": "HARROW — The Resonant CMO",
        "description": "Chief Marketing Officer agent for Goblin Media Network / Attic Tech Solutions. "
                       "Five channels: lead gen, email, voice, social, ads. "
                       "7-stage Campaign Builder. Voss copy techniques. ASP-001/002/003 compliant.",
        "version": AGENT_VERSION,
        "capabilities": ["lead_harvest", "ghost_audit", "copy_generation", "five_gate_check",
                         "voss_compliance", "voice_briefs", "social_briefs", "ads_briefs",
                         "campaign_builder", "autonomous_followup"],
        "tasks": list(_TASK_REGISTRY.keys()) if _TASK_REGISTRY else [
            "run_lead_harvest", "run_ghost_audit", "run_copy_review",
            "run_voice_brief", "run_social_brief", "run_ads_brief",
            "run_channel_report", "run_campaign",
        ],
    })


# ── POST /run ──────────────────────────────────────────────────────────
class RunRequest(BaseModel):
    task: str
    params: dict = {}
    caller: str = "adrian"


@router.post("/run")
async def run_task(body: RunRequest, auth_caller: str = Depends(require_key)):
    """Execute a task. Creates a job. Returns immediately with job_id."""
    task_name = body.task
    caller = body.caller

    # Check if task is registered
    if task_name not in _TASK_REGISTRY:
        available = list(_TASK_REGISTRY.keys())
        if not available:
            # Phase 1 scaffold — no tasks registered yet
            alog("WARN", f"Task '{task_name}' requested but no tasks registered yet (Phase 1 scaffold)",
                 caller=caller, step="run_validate")
            return _error_envelope(
                f"Task '{task_name}' not available. No task handlers registered yet — build in progress.",
                status_code=501,
            )
        return _error_envelope(
            f"Unknown task '{task_name}'. Available: {', '.join(available)}"
        )

    handler, channel = _TASK_REGISTRY[task_name]
    job_id = create_job(task=task_name, caller=caller, channel=channel)

    # Run handler in background
    async def _run():
        try:
            result = await handler(job_id, body.params, caller)
            update_job(job_id, status="complete", result=result)
        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            update_job(job_id, status="failed", error=error_msg)
            alog("ERROR", f"Task {task_name} failed: {error_msg}. To resolve this: check logs for job {job_id}",
                 job_id=job_id, caller=caller, channel=channel, step="run_execute")

    asyncio.create_task(_run())

    return _envelope({"job_id": job_id, "task": task_name, "status": "running"})


# ── GET /status/{job_id} ──────────────────────────────────────────────
@router.get("/status/{job_id}")
async def job_status(job_id: str, caller: str = Depends(require_key)):
    """Check a running or completed job."""
    job = get_job(job_id)
    if not job:
        return _error_envelope(f"Job {job_id} not found", status_code=404)
    return _envelope(job)


# ── GET /logs ──────────────────────────────────────────────────────────
@router.get("/logs")
async def logs(
    channel: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    job_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    caller: str = Depends(require_key),
):
    """Activity log with filters."""
    entries = get_logs(channel=channel, level=level, job_id=job_id, limit=limit)
    return _envelope({"entries": entries})


# ── POST /stop/{job_id} ───────────────────────────────────────────────
@router.post("/stop/{job_id}")
async def stop_job(job_id: str, caller: str = Depends(require_key)):
    """Gracefully stop a running job."""
    job = get_job(job_id)
    if not job:
        return _error_envelope(f"Job {job_id} not found", status_code=404)
    if job["status"] != "running":
        return _error_envelope(f"Job {job_id} is not running (status: {job['status']})")

    update_job(job_id, status="failed", error="Stopped by user")
    alog("WARN", f"Job stopped by user", job_id=job_id, caller=caller, step="job_stop")
    return _envelope({"job_id": job_id, "status": "failed", "message": "Stopped by user"})


# ── POST /auth ─────────────────────────────────────────────────────────
class AuthRequest(BaseModel):
    token: str


@router.post("/auth")
async def auth(body: AuthRequest):
    """Validate API key. Set session cookie. No auth required."""
    valid = await validate_and_set_cookie(body.token)
    if not valid:
        return _error_envelope("Invalid API key", status_code=401)

    response = JSONResponse(content=_envelope({"authenticated": True}))
    response.set_cookie(
        key="harrow_token",
        value=body.token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=86400 * 7,  # 7 days
    )
    alog("INFO", "Dashboard authenticated", caller="adrian", step="auth")
    return response
