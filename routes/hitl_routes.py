"""
routes/hitl_routes.py — HARROW HITL gate endpoints.

Endpoints:
- GET  /gates              — list HITL gates (default: pending only)
- POST /gates/{id}/resolve — approve a gate, job resumes
- GET  /approve/{token}    — One-Touch Receipt signed URL approval (Phase 4)
"""

import time
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from core.auth import require_key
from core.hitl import resolve_gate, get_all_gates

router = APIRouter()

AGENT_ID = "harrow"


def _envelope(data: dict) -> dict:
    return {
        "status": "ok",
        "agent_id": AGENT_ID,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "data": data,
    }


def _error_envelope(message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "error",
            "agent_id": AGENT_ID,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "error": message,
        },
    )


@router.get("/gates")
async def list_gates(
    status: Optional[str] = Query("pending"),
    limit: int = Query(50, ge=1, le=500),
    caller: str = Depends(require_key),
):
    """List HITL gates. Default: pending only."""
    gates = get_all_gates(status=status, limit=limit)
    return _envelope({"gates": gates})


@router.post("/gates/{gate_id}/resolve")
async def resolve(gate_id: int, caller: str = Depends(require_key)):
    """Approve a HITL gate. Job resumes."""
    gate = resolve_gate(gate_id, resolved_by=caller)
    if not gate:
        return _error_envelope(
            f"Gate {gate_id} not found or already resolved", status_code=404
        )
    return _envelope(gate)


# Phase 4: GET /approve/{token} — One-Touch Receipt signed URL approval
