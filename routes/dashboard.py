"""
routes/dashboard.py — HARROW Control Centre dashboard.

Endpoints:
- GET /              — serve index.html via Jinja2
- GET /stream/{id}   — SSE stream for live terminal output
"""

import asyncio
import time
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from core.auth import require_key
from core.jobs import get_job
from core.logging import get_logs
from core.go_state import get_all_go_states
from core.hitl import get_pending_gates

router = APIRouter()

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """
    Serve the Control Centre dashboard.
    Auth via cookie (set by POST /auth).
    Falls back to login prompt if no cookie.
    """
    # Check auth via cookie (soft check — page renders either way)
    token = request.cookies.get("harrow_token", "")
    authenticated = bool(token)

    # Gather dashboard data
    go_states = get_all_go_states() if authenticated else {}
    pending_gates = get_pending_gates() if authenticated else []
    recent_logs = get_logs(limit=20) if authenticated else []

    return templates.TemplateResponse("index.html", {
        "request": request,
        "authenticated": authenticated,
        "go_states": go_states,
        "pending_gates": pending_gates,
        "recent_logs": recent_logs,
        "gate_count": len(pending_gates),
    })


@router.get("/stream/{job_id}")
async def stream_job(job_id: str, caller: str = Depends(require_key)):
    """
    SSE stream for live terminal output during long-running tasks.
    Polls job status and log entries every 1 second.
    Closes when job completes or fails.
    """
    async def event_generator():
        last_log_id = 0
        while True:
            job = get_job(job_id)
            if not job:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Job not found'})}\n\n"
                break

            # Send job status
            yield f"data: {json.dumps({'type': 'status', 'status': job['status'], 'progress': job.get('progress', '')})}\n\n"

            # Send new log entries
            logs = get_logs(job_id=job_id, limit=10)
            for log in reversed(logs):
                log_id = log.get("id", 0)
                if log_id > last_log_id:
                    last_log_id = log_id
                    yield f"data: {json.dumps({'type': 'log', 'level': log['level'], 'message': log['message'], 'timestamp': log['timestamp']})}\n\n"

            # Check if job is done
            if job["status"] in ("complete", "failed"):
                result_data = {
                    "type": "complete",
                    "status": job["status"],
                    "result": job.get("result"),
                    "error": job.get("error"),
                }
                yield f"data: {json.dumps(result_data)}\n\n"
                break

            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
