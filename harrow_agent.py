"""
HARROW — The Resonant CMO
Chief Marketing Officer agent for Goblin Media Network / Attic Tech Solutions.
Sovereign FastAPI service. Port 8001. ASP-001/002/003 compliant.

This is the main entry point. It imports routes only — no business logic here.
"""

import time
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Agent metadata
AGENT_ID = "harrow"
AGENT_NAME = "HARROW — The Resonant CMO"
AGENT_VERSION = "1.0.0"
AGENT_PORT = 8001
START_TIME = time.time()

app = FastAPI(
    title=AGENT_NAME,
    version=AGENT_VERSION,
    description="CMO agent for Goblin Media Network / Attic Tech Solutions. "
                "Five channels: lead gen, email, voice, social, ads.",
)


@app.on_event("startup")
async def startup():
    """Initialise database and log startup."""
    # Phase 1: init_db(), start scheduler, log startup
    pass


# --- Route imports (wired in Phase 1) ---
# from routes.asp002 import router as asp002_router
# from routes.go_gates import router as go_gates_router
# from routes.hitl_routes import router as hitl_router
# from routes.dashboard import router as dashboard_router
# from routes.settings import router as settings_router
#
# app.include_router(asp002_router)
# app.include_router(go_gates_router)
# app.include_router(hitl_router)
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


@app.get("/")
async def root():
    """Scaffold placeholder — replaced by dashboard route in Phase 5."""
    return {
        "status": "ok",
        "agent_id": AGENT_ID,
        "message": "HARROW scaffold only. Dashboard not yet built.",
    }
