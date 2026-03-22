"""
routes/settings.py — HARROW Settings endpoints.

Endpoints:
- POST /settings/key/test          — test API key against target service
- POST /settings/key/update        — update key in .env, trigger restart
- GET  /settings/channel/{channel} — return current channel config
- POST /settings/channel/{channel} — update channel config
- GET  /settings/agent-info        — version, uptime, capabilities, registry SQL
"""

import os
import time
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

import requests
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core.auth import require_key
from core.db import get_db
from core.logging import alog
from core.go_state import VALID_CHANNELS

router = APIRouter(prefix="/settings")

AGENT_ID = "harrow"
AGENT_VERSION = "1.0.0"
START_TIME = time.time()


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


# --- Key testing functions ---

_KEY_TESTS = {
    "OUTSCRAPER_API_KEY": {
        "url": "https://api.app.outscraper.com/maps/search-v3",
        "method": "GET",
        "params": {"query": "test", "limit": 1, "async": False},
        "header_key": "X-API-KEY",
    },
    "FIRECRAWL_API_KEY": {
        "url": "https://api.firecrawl.dev/v1/scrape",
        "method": "POST",
        "json": {"url": "https://example.com", "formats": ["markdown"]},
        "header_prefix": "Bearer ",
    },
    "ANTHROPIC_API_KEY": {
        "test_type": "anthropic",
    },
    "VAPI_API_KEY": {
        "url": "https://api.vapi.ai/assistant",
        "method": "GET",
        "header_prefix": "Bearer ",
    },
}


def _test_key(key_name: str) -> dict:
    """Test an API key against its target service. Returns {result, detail}."""
    value = os.environ.get(key_name, "")
    if not value:
        return {"result": "FAIL", "detail": f"{key_name} not set in environment"}

    test_config = _KEY_TESTS.get(key_name)
    if not test_config:
        return {"result": "UNKNOWN", "detail": f"No test defined for {key_name}"}

    # Special case: Anthropic
    if test_config.get("test_type") == "anthropic":
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=value, timeout=10.0)
            # Simple model list check
            resp = client.messages.create(
                model="claude-haiku-4-5-20250315",
                max_tokens=10,
                messages=[{"role": "user", "content": "Say OK"}],
            )
            return {"result": "PASS", "detail": f"Anthropic API responding ({resp.usage.input_tokens} tokens)"}
        except Exception as e:
            return {"result": "FAIL", "detail": str(e)}

    # HTTP-based tests
    try:
        headers = {}
        if "header_key" in test_config:
            headers[test_config["header_key"]] = value
        elif "header_prefix" in test_config:
            headers["Authorization"] = f"{test_config['header_prefix']}{value}"

        method = test_config.get("method", "GET")
        if method == "GET":
            resp = requests.get(
                test_config["url"],
                headers=headers,
                params=test_config.get("params"),
                timeout=10,
            )
        else:
            resp = requests.post(
                test_config["url"],
                headers=headers,
                json=test_config.get("json"),
                timeout=10,
            )

        if resp.status_code < 400:
            return {"result": "PASS", "detail": f"HTTP {resp.status_code}"}
        elif resp.status_code in (401, 403):
            return {"result": "FAIL", "detail": f"Authentication failed (HTTP {resp.status_code})"}
        else:
            return {"result": "WARN", "detail": f"HTTP {resp.status_code} — key may be valid but service returned error"}

    except requests.Timeout:
        return {"result": "WARN", "detail": "Request timed out — service may be slow"}
    except Exception as e:
        return {"result": "FAIL", "detail": str(e)}


# ── POST /settings/key/test ───────────────────────────────────────────

class KeyTestRequest(BaseModel):
    key_name: str


@router.post("/key/test")
async def test_key(body: KeyTestRequest, caller: str = Depends(require_key)):
    """Test an API key against its target service."""
    result = _test_key(body.key_name)
    alog("INFO", f"Key test: {body.key_name} -> {result['result']}",
         caller=caller, step="settings_key_test")
    return _envelope({"key_name": body.key_name, **result})


# ── POST /settings/key/update ─────────────────────────────────────────

class KeyUpdateRequest(BaseModel):
    key_name: str
    value: str


@router.post("/key/update")
async def update_key(body: KeyUpdateRequest, caller: str = Depends(require_key)):
    """Update an API key in .env. Updates runtime env immediately."""
    # Validate key name
    valid_keys = {
        "OUTSCRAPER_API_KEY", "FIRECRAWL_API_KEY", "ANTHROPIC_API_KEY",
        "VAPI_API_KEY", "PUSH_CMS_API_KEY", "PUSH_CMS_AGENT_URL",
        "NTFY_TOPIC", "NTFY_SECRET", "GOOGLE_SHEETS_ID",
    }
    if body.key_name not in valid_keys:
        return _error_envelope(f"Invalid key name. Valid keys: {', '.join(sorted(valid_keys))}")

    # Update runtime env
    os.environ[body.key_name] = body.value

    # Update .env file
    env_path = Path(__file__).parent.parent / ".env"
    try:
        if env_path.exists():
            lines = env_path.read_text().splitlines()
            found = False
            for i, line in enumerate(lines):
                if line.startswith(f"{body.key_name}="):
                    lines[i] = f"{body.key_name}={body.value}"
                    found = True
                    break
            if not found:
                lines.append(f"{body.key_name}={body.value}")
            env_path.write_text("\n".join(lines) + "\n")
        else:
            env_path.write_text(f"{body.key_name}={body.value}\n")
    except Exception as e:
        alog("ERROR", f"Failed to write .env: {e}. To resolve this: check file permissions",
             step="settings_key_update")
        # Runtime env is still updated even if file write fails

    alog("INFO", f"Key updated: {body.key_name}", caller=caller, step="settings_key_update")
    return _envelope({"key_name": body.key_name, "updated": True})


# ── GET /settings/channel/{channel} ───────────────────────────────────

@router.get("/channel/{channel}")
async def get_channel_config(channel: str, caller: str = Depends(require_key)):
    """Return current config for a channel."""
    if channel not in VALID_CHANNELS and channel != "lead_gen":
        return _error_envelope(f"Invalid channel: {channel}")

    with get_db() as db:
        rows = db.execute(
            "SELECT key, value, updated_at FROM settings WHERE channel = ? OR channel IS NULL ORDER BY key",
            (channel,),
        ).fetchall()

    config = {}
    for row in rows:
        config[row["key"]] = {"value": row["value"], "updated_at": row["updated_at"]}

    # Add defaults if not in DB
    defaults = {
        "email": {"send_window_start": "08:00", "send_window_end": "17:00", "m2_delay_days": "5", "m3_delay_days": "5"},
        "voice": {"default_script_type": "inbound"},
        "social": {"default_platform": "linkedin"},
        "ads": {"budget_ceiling_gbp": "2000"},
        "lead_gen": {"default_limit": "20", "dry_run": "true"},
    }
    for key, val in defaults.get(channel, {}).items():
        if key not in config:
            config[key] = {"value": val, "updated_at": None, "is_default": True}

    return _envelope(config)


# ── POST /settings/channel/{channel} ──────────────────────────────────

@router.post("/channel/{channel}")
async def update_channel_config(channel: str, request_body: dict, caller: str = Depends(require_key)):
    """Update channel config. Accepts arbitrary key-value pairs."""
    if channel not in VALID_CHANNELS and channel != "lead_gen":
        return _error_envelope(f"Invalid channel: {channel}")

    now = datetime.now(timezone.utc).isoformat()
    updated_keys = []

    with get_db() as db:
        for key, value in request_body.items():
            db.execute(
                """INSERT INTO settings (key, value, channel, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(key, channel) DO UPDATE SET value = ?, updated_at = ?""",
                (key, str(value), channel, now, str(value), now),
            )
            updated_keys.append(key)

    alog("INFO", f"Channel {channel} config updated: {', '.join(updated_keys)}",
         caller=caller, channel=channel, step="settings_channel_update")

    return _envelope({"channel": channel, "updated_keys": updated_keys})


# ── GET /settings/agent-info ──────────────────────────────────────────

@router.get("/agent-info")
async def agent_info(caller: str = Depends(require_key)):
    """Return version, uptime, capabilities, registry SQL."""
    registry_path = Path(__file__).parent.parent / "registry_entry.sql"
    registry_sql = ""
    if registry_path.exists():
        registry_sql = registry_path.read_text(encoding="utf-8")

    return _envelope({
        "version": AGENT_VERSION,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "port": 8001,
        "capabilities": [
            "lead_harvest", "ghost_audit", "copy_generation", "five_gate_check",
            "voss_compliance", "voice_briefs", "social_briefs", "ads_briefs",
            "campaign_builder", "autonomous_followup", "one_touch_receipt",
        ],
        "registry_sql": registry_sql,
    })
