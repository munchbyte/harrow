"""
integrations/push_client.py — HARROW client for Push CMS (Tier-3 sub-agent).

Push CMS is HARROW's content sub-agent (port 8004). HARROW dispatches
content briefs to Push for end-to-end drafting and publishing.

Contract (ASP-002):
- GET  /health           — liveness, no auth
- GET  /info             — identity + capabilities, no auth
- POST /run              — dispatch a job, X-API-Key
- GET  /status/{job_id}  — poll job state, X-API-Key
- GET  /logs             — fetch ASP-003 logs, X-API-Key
- POST /stop/{job_id}    — cancel job, X-API-Key

Env:
- PUSH_CMS_AGENT_URL  (preferred; falls back to PUSH_CMS_URL)
- PUSH_CMS_API_KEY

Conventions followed (see engine/claude_client.py for the parallel pattern):
- Async public functions wrap sync `requests` calls.
- Every call logs via core.logging.alog with caller=harrow, channel=push_cms.
- One timeout retry; no retry on 4xx/5xx.
- Non-2xx raises PushClientError with body context (no swallowing).
- Plain-English error messages ending with 'To resolve this:' per ASP-003.
"""

import os
import asyncio
from typing import Any, Optional

import requests

from core.logging import alog


DEFAULT_TIMEOUT = 10.0
HEALTH_TIMEOUT = 2.0   # /health is called from HARROW's own /health — must be fast
TARGET = "push_cms"


class PushClientError(RuntimeError):
    """Raised when Push CMS returns a non-2xx response or is unreachable."""

    def __init__(self, message: str, *, status_code: Optional[int] = None, body: Optional[str] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def _base_url() -> str:
    """Push CMS internal URL. Trailing slash stripped."""
    url = os.environ.get("PUSH_CMS_AGENT_URL") or os.environ.get("PUSH_CMS_URL", "")
    if not url:
        raise PushClientError(
            "PUSH_CMS_AGENT_URL not set. To resolve this: add PUSH_CMS_AGENT_URL=http://localhost:8004 to HARROW's .env"
        )
    return url.rstrip("/")


def _api_key() -> str:
    """Push CMS API key. Empty string if not configured."""
    return os.environ.get("PUSH_CMS_API_KEY", "")


def _auth_headers() -> dict:
    """Build X-API-Key header. Empty dict if no key."""
    key = _api_key()
    return {"X-API-Key": key} if key else {}


def _request(
    method: str,
    path: str,
    *,
    auth: bool = True,
    json_body: Optional[dict] = None,
    timeout: float = DEFAULT_TIMEOUT,
    step: str,
    job_id: Optional[str] = None,
) -> dict:
    """
    Synchronous HTTP request to Push. Used by every public async wrapper.

    Auth headers applied when auth=True. One timeout retry. No retry on 4xx/5xx.
    Non-2xx raises PushClientError. Logs every call.
    """
    url = f"{_base_url()}{path}"
    headers = _auth_headers() if auth else {}

    attempt = 0
    last_error: Optional[Exception] = None

    while attempt < 2:
        try:
            resp = requests.request(
                method=method.upper(),
                url=url,
                headers=headers,
                json=json_body,
                timeout=timeout,
            )

            if 200 <= resp.status_code < 300:
                alog(
                    "INFO",
                    f"Push CMS {method} {path} OK ({resp.status_code})",
                    job_id=job_id, channel=TARGET, step=step,
                    action=f"{method.lower()}_{path}", outcome=f"http_{resp.status_code}",
                )
                try:
                    return resp.json()
                except ValueError:
                    return {"raw": resp.text}

            # Non-2xx — no retry
            body_text = (resp.text or "")[:500]
            alog(
                "ERROR",
                f"Push CMS {method} {path} returned HTTP {resp.status_code}. "
                f"To resolve this: check Push logs (ssh root@31.97.59.80 'sudo -u push pm2 logs push_api --lines 30 --nostream') "
                f"and verify PUSH_CMS_API_KEY",
                job_id=job_id, channel=TARGET, step=step,
                action=f"{method.lower()}_{path}", outcome=f"http_{resp.status_code}",
            )
            raise PushClientError(
                f"Push CMS {method} {path} -> HTTP {resp.status_code}",
                status_code=resp.status_code,
                body=body_text,
            )

        except requests.Timeout as e:
            last_error = e
            attempt += 1
            if attempt < 2:
                alog(
                    "WARN",
                    f"Push CMS {method} {path} timed out after {timeout}s, retrying once",
                    job_id=job_id, channel=TARGET, step=step,
                )
                continue

        except requests.ConnectionError as e:
            # No retry on connection errors — Push is down or URL is wrong
            alog(
                "ERROR",
                f"Push CMS unreachable at {url}: {e}. "
                f"To resolve this: verify PUSH_CMS_AGENT_URL and that push_api systemd service is running on the VPS",
                job_id=job_id, channel=TARGET, step=step,
                action=f"{method.lower()}_{path}", outcome="unreachable",
            )
            raise PushClientError(f"Push CMS unreachable: {e}") from e

    # Exhausted retries
    alog(
        "ERROR",
        f"Push CMS {method} {path} timed out after retry. "
        f"To resolve this: check Push CMS process and network",
        job_id=job_id, channel=TARGET, step=step,
        action=f"{method.lower()}_{path}", outcome="timeout",
    )
    raise PushClientError(f"Push CMS timeout after retry: {last_error}") from last_error


# ── ASP-002 contract surface ────────────────────────────────────────────


async def health(timeout: float = HEALTH_TIMEOUT) -> dict:
    """GET /health — Push liveness check. No auth. Fast timeout (default 2s)."""
    return await asyncio.to_thread(
        _request, "GET", "/health",
        auth=False, timeout=timeout, step="push_health",
    )


async def info(timeout: float = DEFAULT_TIMEOUT) -> dict:
    """GET /info — Push identity and capabilities. No auth."""
    return await asyncio.to_thread(
        _request, "GET", "/info",
        auth=False, timeout=timeout, step="push_info",
    )


async def dispatch(
    task: str,
    params: Optional[dict] = None,
    *,
    caller: str = "harrow",
    timeout: float = DEFAULT_TIMEOUT,
    job_id: Optional[str] = None,
) -> dict:
    """
    POST /run — dispatch a task to Push CMS.

    Returns the Push response (typically {job_id, ...}). Raises PushClientError
    on non-2xx. The caller field is recorded in Push's logs for traceability.
    """
    payload: dict[str, Any] = {
        "task": task,
        "params": params or {},
        "caller": caller,
    }
    alog(
        "INFO",
        f"Dispatching task '{task}' to Push CMS (caller={caller})",
        job_id=job_id, channel=TARGET, step="push_dispatch",
        action=f"dispatch_{task}", outcome="sending",
    )
    return await asyncio.to_thread(
        _request, "POST", "/run",
        auth=True, json_body=payload, timeout=timeout,
        step="push_dispatch", job_id=job_id,
    )


async def status(push_job_id: str, *, timeout: float = DEFAULT_TIMEOUT, job_id: Optional[str] = None) -> dict:
    """GET /status/{job_id} — poll a Push job."""
    return await asyncio.to_thread(
        _request, "GET", f"/status/{push_job_id}",
        auth=True, timeout=timeout, step="push_status", job_id=job_id,
    )


async def logs(limit: int = 50, *, timeout: float = DEFAULT_TIMEOUT) -> list:
    """GET /logs — fetch Push activity log. Returns the entries list."""
    result = await asyncio.to_thread(
        _request, "GET", f"/logs?limit={int(limit)}",
        auth=True, timeout=timeout, step="push_logs",
    )
    # Push returns the standard ASP-002 envelope: {status, agent_id, timestamp, data: {...}}
    data = result.get("data", result)
    if isinstance(data, dict) and "entries" in data:
        return data["entries"]
    if isinstance(data, list):
        return data
    return []


async def stop(push_job_id: str, *, timeout: float = DEFAULT_TIMEOUT, job_id: Optional[str] = None) -> dict:
    """POST /stop/{job_id} — cancel a running Push job."""
    return await asyncio.to_thread(
        _request, "POST", f"/stop/{push_job_id}",
        auth=True, timeout=timeout, step="push_stop", job_id=job_id,
    )
