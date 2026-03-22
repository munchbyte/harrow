"""
routes/go_gates.py — HARROW GO gate endpoints.

Endpoints:
- POST /go/{channel}      — arm a channel (email, voice, social, ads)
- POST /revoke/{channel}  — disarm a channel immediately
- GET  /go-status          — return all four channel GO states
"""

import time
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from core.auth import require_key
from core.go_state import arm_channel, revoke_channel, get_all_go_states, VALID_CHANNELS

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


@router.post("/go/{channel}")
async def go_arm(channel: str, caller: str = Depends(require_key)):
    """Arm a channel GO flag."""
    if channel not in VALID_CHANNELS:
        return _error_envelope(
            f"Invalid channel '{channel}'. Must be one of: {', '.join(sorted(VALID_CHANNELS))}"
        )
    result = arm_channel(channel, armed_by=caller)
    return _envelope(result)


@router.post("/revoke/{channel}")
async def go_revoke(channel: str, caller: str = Depends(require_key)):
    """Disarm a channel immediately."""
    if channel not in VALID_CHANNELS:
        return _error_envelope(
            f"Invalid channel '{channel}'. Must be one of: {', '.join(sorted(VALID_CHANNELS))}"
        )
    result = revoke_channel(channel)
    return _envelope(result)


@router.get("/go-status")
async def go_status(caller: str = Depends(require_key)):
    """Return all four channel GO states."""
    states = get_all_go_states()
    return _envelope(states)
