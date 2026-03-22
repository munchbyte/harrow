"""
HARROW — The Resonant CMO
Chief Marketing Officer agent for Goblin Media Network / Attic Tech Solutions.
Sovereign FastAPI service. Port 8001. ASP-001/002/003 compliant.

This is the main entry point. It imports routes only — no business logic here.
"""

import time
from contextlib import asynccontextmanager
from fastapi import FastAPI

from core.db import init_db
from core.logging import alog
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

    # Start autonomous follow-up scheduler
    start_scheduler()

    alog("INFO", f"HARROW {AGENT_VERSION} started on port {AGENT_PORT} — 7 tasks registered, scheduler active", step="startup")
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

# Phase 5: dashboard and settings routes
# from routes.dashboard import router as dashboard_router
# from routes.settings import router as settings_router
# app.include_router(dashboard_router)
# app.include_router(settings_router)


@app.get("/health")
async def health():
    """ASP-002 health check. No auth required."""
    return {
        "status": "ok",
        "agent_id": AGENT_ID,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "data": {
            "version": AGENT_VERSION,
            "uptime_seconds": round(time.time() - START_TIME, 1),
        },
    }
