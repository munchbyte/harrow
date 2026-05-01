"""
HARROW — The Resonant CMO
Chief Marketing Officer agent for Goblin Media Network / Attic Tech Solutions.
Sovereign FastAPI service. Port 8001. ASP-001/002/003 compliant.

This is the main entry point. It imports routes only — no business logic here.
"""

import time
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

from core.db import init_db
from core.logging import alog
from core.sub_agents import list_live as list_live_sub_agents
from routes.asp002 import router as asp002_router, register_task
from routes.go_gates import router as go_gates_router
from routes.hitl_routes import router as hitl_router

# Channel task handlers (Phase 2)
from channels.lead_gen import task_lead_harvest, task_ghost_audit
from channels.email import task_copy_review

# Campaign (Phase 3)
from campaign.builder import task_run_campaign
from campaign.scheduler import start_scheduler, stop_scheduler

# Channels (Phase 4)
from channels.voice import task_voice_brief
from channels.social import task_social_brief
from channels.ads import task_ads_brief
from channels.report import task_channel_report

# Dashboard + Settings (Phase 5)
from routes.dashboard import router as dashboard_router
from routes.settings import router as settings_router

# Agent metadata
AGENT_ID = "harrow"
AGENT_NAME = "HARROW — The Resonant CMO"
AGENT_VERSION = "1.0.0"
AGENT_PORT = 8001
START_TIME = time.time()


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Startup and shutdown lifecycle."""
    # Startup
    init_db()

    # Register tasks
    register_task("run_lead_harvest", task_lead_harvest, "lead_gen")
    register_task("run_ghost_audit", task_ghost_audit, "lead_gen")
    register_task("run_copy_review", task_copy_review, "email")
    register_task("run_campaign", task_run_campaign, "lead_gen")
    register_task("run_voice_brief", task_voice_brief, "voice")
    register_task("run_social_brief", task_social_brief, "social")
    register_task("run_ads_brief", task_ads_brief, "ads")
    register_task("run_channel_report", task_channel_report, None)

    # Start autonomous follow-up scheduler
    start_scheduler()

    alog("INFO", f"HARROW {AGENT_VERSION} started on port {AGENT_PORT} — 8 tasks registered, scheduler active", step="startup")
    yield
    # Shutdown
    stop_scheduler()
    alog("INFO", "HARROW shutting down", step="shutdown")


app = FastAPI(
    title=AGENT_NAME,
    version=AGENT_VERSION,
    description="CMO agent for Goblin Media Network / Attic Tech Solutions. "
                "Five channels: lead gen, email, voice, social, ads.",
    lifespan=lifespan,
)

# Wire routes
app.include_router(asp002_router)
app.include_router(go_gates_router)
app.include_router(hitl_router)

# Dashboard and settings routes (Phase 5)
app.include_router(dashboard_router)
app.include_router(settings_router)


_HEALTHY_STATUS_VALUES = {"ok", "online", "healthy", "ready", "running"}


async def _probe_sub_agent(entry: dict) -> tuple[str, str]:
    """Probe one sub-agent's /health. Returns (agent_id, 'ok'|'unreachable').

    Different sub-agents use different healthy-status conventions
    (HARROW says 'ok', Push v1.2.0 says 'online'). Any value in
    _HEALTHY_STATUS_VALUES counts as healthy.
    """
    agent_id = entry["agent_id"]
    health_fn = entry.get("health_fn")
    if health_fn is None:
        return agent_id, "unknown"
    try:
        result = await health_fn()
        if not isinstance(result, dict):
            return agent_id, "unreachable"
        status_value = (
            result.get("status")
            or result.get("data", {}).get("status")
            or ""
        )
        return agent_id, "ok" if str(status_value).lower() in _HEALTHY_STATUS_VALUES else "unreachable"
    except Exception:
        # ASP-001: a sub-agent being down must NOT make HARROW unhealthy.
        return agent_id, "unreachable"


@app.get("/health")
async def health():
    """ASP-002 health check. No auth required.

    Includes a non-blocking sub_agents block. Sub-agent failures never
    affect HARROW's own status — sovereignty per ASP-001.
    """
    sub_agent_results: dict[str, str] = {}
    live = list_live_sub_agents()
    if live:
        probes = [_probe_sub_agent(entry) for entry in live]
        results = await asyncio.gather(*probes, return_exceptions=True)
        for r in results:
            if isinstance(r, tuple):
                sub_agent_results[r[0]] = r[1]

    return {
        "status": "ok",
        "agent_id": AGENT_ID,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "data": {
            "version": AGENT_VERSION,
            "uptime_seconds": round(time.time() - START_TIME, 1),
            "sub_agents": sub_agent_results,
        },
    }
