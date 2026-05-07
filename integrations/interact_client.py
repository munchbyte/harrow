"""
integrations/interact_client.py — HARROW client for Interact CRM (Tier-3 sub-agent).

Interact CRM is HARROW's Tier-3 CRM sub-agent (port 8003). Same VPS, internal
calls only. Mirrors integrations/push_client.py — the two clients are deliberate
near-copies rather than sharing a base class (no premature abstraction; refactor
when there's a third agent).

Contract (Interact v2.0-dev, confirmed via /openapi discovery 2026-05-07):
- GET  /health           — liveness, X-API-Key required (deviation from ASP-002)
- GET  /info             — identity + capabilities, X-API-Key required
- POST /run              — dispatch a job, X-API-Key (returns 202 + RunResponse)
- GET  /status/{job_id}  — poll job state, X-API-Key
- GET  /logs             — fetch ASP-003 logs, X-API-Key
- POST /stop/{job_id}    — cancel job, X-API-Key

Env:
- INTERACT_AGENT_URL  (Interact v2.0-dev binds to its Tailscale interface only;
                       use the Tailscale IP, e.g. http://100.109.24.65:8003,
                       NOT localhost — even on the same VPS)
- INTERACT_API_KEY    (required on EVERY endpoint including /health — Interact's
                       auth middleware deviates from ASP-002 §4.1 here)

Conventions (same as push_client.py):
- Async public functions wrap sync `requests` calls.
- Every call logs via core.logging.alog with channel=interact_crm.
- One timeout retry; no retry on 4xx/5xx.
- Non-2xx raises InteractClientError with body context.
- Plain-English error messages ending with 'To resolve this:' per ASP-003.

Public API:
- health() / info() / dispatch() / status() / logs() / stop()  — generic ASP-002 surface
- send_reply_received() / send_advance_stage() / send_log_interaction()
                                              — typed [HARROW-CRM] signal wrappers
"""

import os
import asyncio
from typing import Any, Optional

import requests

from core.logging import alog


DEFAULT_TIMEOUT = 10.0
HEALTH_TIMEOUT = 2.0
TARGET = "interact_crm"

# Interact v2.0-dev does NOT enforce a caller enum (RunRequest.caller is a free
# string with default "human"). Convention: HARROW always identifies as 'harrow'.
HARROW_CALLER = "harrow"


class InteractClientError(RuntimeError):
    """Raised when Interact CRM returns a non-2xx response or is unreachable."""

    def __init__(self, message: str, *, status_code: Optional[int] = None, body: Optional[str] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def _base_url() -> str:
    """Interact CRM Tailscale URL. Trailing slash stripped."""
    url = os.environ.get("INTERACT_AGENT_URL", "")
    if not url:
        raise InteractClientError(
            "INTERACT_AGENT_URL not set. To resolve this: add "
            "INTERACT_AGENT_URL=http://100.109.24.65:8003 to HARROW's .env "
            "(Tailscale IP — Interact does not listen on localhost)"
        )
    return url.rstrip("/")


def _api_key() -> str:
    """Interact CRM API key. Empty string if not configured."""
    return os.environ.get("INTERACT_API_KEY", "")


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
    """Synchronous HTTP request to Interact. One timeout retry, no retry on non-2xx."""
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
                    f"Interact CRM {method} {path} OK ({resp.status_code})",
                    job_id=job_id, channel=TARGET, step=step,
                    action=f"{method.lower()}_{path}", outcome=f"http_{resp.status_code}",
                )
                try:
                    return resp.json()
                except ValueError:
                    return {"raw": resp.text}

            body_text = (resp.text or "")[:500]
            alog(
                "ERROR",
                f"Interact CRM {method} {path} returned HTTP {resp.status_code}. "
                f"To resolve this: check Interact logs and verify INTERACT_API_KEY",
                job_id=job_id, channel=TARGET, step=step,
                action=f"{method.lower()}_{path}", outcome=f"http_{resp.status_code}",
            )
            raise InteractClientError(
                f"Interact CRM {method} {path} -> HTTP {resp.status_code}",
                status_code=resp.status_code,
                body=body_text,
            )

        except requests.Timeout as e:
            last_error = e
            attempt += 1
            if attempt < 2:
                alog(
                    "WARN",
                    f"Interact CRM {method} {path} timed out after {timeout}s, retrying once",
                    job_id=job_id, channel=TARGET, step=step,
                )
                continue

        except requests.ConnectionError as e:
            alog(
                "ERROR",
                f"Interact CRM unreachable at {url}: {e}. "
                f"To resolve this: confirm INTERACT_AGENT_URL uses the Tailscale IP "
                f"(http://100.109.24.65:8003, NOT localhost — Interact binds to tailscale0 only) "
                f"and that Interact's systemd service is running on the VPS",
                job_id=job_id, channel=TARGET, step=step,
                action=f"{method.lower()}_{path}", outcome="unreachable",
            )
            raise InteractClientError(f"Interact CRM unreachable: {e}") from e

    alog(
        "ERROR",
        f"Interact CRM {method} {path} timed out after retry. "
        f"To resolve this: check Interact CRM process and network",
        job_id=job_id, channel=TARGET, step=step,
        action=f"{method.lower()}_{path}", outcome="timeout",
    )
    raise InteractClientError(f"Interact CRM timeout after retry: {last_error}") from last_error


# ── ASP-002 contract surface ────────────────────────────────────────────


async def health(timeout: float = HEALTH_TIMEOUT) -> dict:
    """GET /health — Interact liveness check. Fast timeout (default 2s).

    Interact v2.0-dev's auth middleware requires X-API-Key on every endpoint
    including /health (deviation from ASP-002 §4.1, accepted per ASP-001).
    """
    return await asyncio.to_thread(
        _request, "GET", "/health",
        auth=True, timeout=timeout, step="interact_health",
    )


async def info(timeout: float = DEFAULT_TIMEOUT) -> dict:
    """GET /info — Interact identity and capabilities. Auth required (see health())."""
    return await asyncio.to_thread(
        _request, "GET", "/info",
        auth=True, timeout=timeout, step="interact_info",
    )


async def dispatch(
    task: str,
    params: Optional[dict] = None,
    *,
    caller: str = HARROW_CALLER,
    caller_label: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
    job_id: Optional[str] = None,
) -> dict:
    """
    POST /run — dispatch a task to Interact CRM.

    Interact accepts any caller string (no enum enforced). Convention is
    caller='harrow'; use caller_label for free-form trace tags
    (e.g. 'harrow_smoke', 'campaign_42').

    Returns Interact's RunResponse. Raises InteractClientError on non-2xx.
    """
    payload: dict[str, Any] = {
        "task": task,
        "params": params or {},
        "caller": caller,
    }
    if caller_label:
        payload["caller_label"] = caller_label

    label_str = f", label={caller_label}" if caller_label else ""
    alog(
        "INFO",
        f"Dispatching task '{task}' to Interact CRM (caller={caller}{label_str})",
        job_id=job_id, channel=TARGET, step="interact_dispatch",
        action=f"dispatch_{task}", outcome="sending",
    )
    return await asyncio.to_thread(
        _request, "POST", "/run",
        auth=True, json_body=payload, timeout=timeout,
        step="interact_dispatch", job_id=job_id,
    )


async def status(interact_job_id: str, *, timeout: float = DEFAULT_TIMEOUT, job_id: Optional[str] = None) -> dict:
    """GET /status/{job_id} — poll an Interact job."""
    return await asyncio.to_thread(
        _request, "GET", f"/status/{interact_job_id}",
        auth=True, timeout=timeout, step="interact_status", job_id=job_id,
    )


async def logs(limit: int = 50, *, timeout: float = DEFAULT_TIMEOUT) -> list:
    """GET /logs — fetch Interact activity log. Returns the entries list."""
    result = await asyncio.to_thread(
        _request, "GET", f"/logs?limit={int(limit)}",
        auth=True, timeout=timeout, step="interact_logs",
    )
    data = result.get("data", result)
    if isinstance(data, dict) and "entries" in data:
        return data["entries"]
    if isinstance(data, list):
        return data
    return []


async def stop(interact_job_id: str, *, timeout: float = DEFAULT_TIMEOUT, job_id: Optional[str] = None) -> dict:
    """POST /stop/{job_id} — cancel a running Interact job."""
    return await asyncio.to_thread(
        _request, "POST", f"/stop/{interact_job_id}",
        auth=True, timeout=timeout, step="interact_stop", job_id=job_id,
    )


# ── [HARROW-CRM] signal wrappers ────────────────────────────────────────
#
# Three named convenience functions on top of dispatch(). These encode the
# Interact v2.0 CRM contract for the signals HARROW emits during outreach,
# pipeline progression, and activity logging. Use these in calling code
# rather than dispatch() directly — the typed signatures document the
# contract and catch missing params before the wire call.


async def send_reply_received(
    lead_id: str,
    contact_email: str,
    reply_text: str,
    stage: str,
    *,
    caller_label: Optional[str] = None,
    job_id: Optional[str] = None,
) -> dict:
    """
    Signal: a reply was received from a lead. Dispatches task='reply_received'.

    Interact uses this to attach the inbound message to the contact, advance
    the activity layer, and (if the stage warrants) fire a HITL gate for
    Adrian to triage.

    Params shape sent to Interact:
        {lead_id, contact_email, reply_text, stage}
    """
    return await dispatch(
        "reply_received",
        {
            "lead_id": lead_id,
            "contact_email": contact_email,
            "reply_text": reply_text,
            "stage": stage,
        },
        caller_label=caller_label,
        job_id=job_id,
    )


async def send_advance_stage(
    lead_id: str,
    new_stage: str,
    trigger: str,
    channel: str,
    *,
    caller_label: Optional[str] = None,
    job_id: Optional[str] = None,
) -> dict:
    """
    Signal: a lead has progressed to a new pipeline stage. Dispatches
    task='advance_stage'.

    Interact uses this to update the deal in its pipeline board, append an
    activity record, and recompute pipeline value.

    Params shape sent to Interact:
        {lead_id, new_stage, trigger, channel}
    """
    return await dispatch(
        "advance_stage",
        {
            "lead_id": lead_id,
            "new_stage": new_stage,
            "trigger": trigger,
            "channel": channel,
        },
        caller_label=caller_label,
        job_id=job_id,
    )


async def send_log_interaction(
    lead_id: str,
    interaction_type: str,
    template: str,
    sent_at: str,
    *,
    caller_label: Optional[str] = None,
    job_id: Optional[str] = None,
) -> dict:
    """
    Signal: HARROW sent an outbound interaction (email, voice brief, ad).
    Dispatches task='log_interaction'.

    Interact uses this to write an entry to the activity layer for the
    contact — auditable proof the touchpoint happened.

    Params shape sent to Interact:
        {lead_id, interaction_type, template, sent_at}
    sent_at should be ISO-8601 (e.g. "2026-05-07T14:32:00Z").
    """
    return await dispatch(
        "log_interaction",
        {
            "lead_id": lead_id,
            "interaction_type": interaction_type,
            "template": template,
            "sent_at": sent_at,
        },
        caller_label=caller_label,
        job_id=job_id,
    )
