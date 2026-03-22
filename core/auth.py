"""
core/auth.py — HARROW authentication.

Provides require_key() FastAPI dependency.
Checks X-API-Key header OR harrow_token session cookie.
If HARROW_API_KEY env var is blank, open access (dev mode) with WARN log.
Applied to every endpoint except GET /health and POST /auth.
"""

import os
import hmac
from fastapi import Request, HTTPException
from core.logging import alog


def _get_api_key() -> str:
    """Return the configured API key from env. Empty string = dev mode."""
    return os.environ.get("HARROW_API_KEY", "")


def _constant_time_compare(a: str, b: str) -> bool:
    """Timing-safe string comparison."""
    return hmac.compare_digest(a.encode(), b.encode())


async def require_key(request: Request) -> str:
    """
    FastAPI dependency — validates auth on every protected endpoint.

    Checks in order:
    1. X-API-Key header
    2. harrow_token cookie

    If HARROW_API_KEY env is blank, allows all requests (dev mode) with WARN.
    Returns the caller identifier string.
    """
    expected = _get_api_key()

    # Dev mode — no key configured
    if not expected:
        alog("WARN", "No HARROW_API_KEY set — running in open dev mode", step="auth")
        return "dev"

    # Check header first
    header_key = request.headers.get("X-API-Key", "")
    if header_key and _constant_time_compare(header_key, expected):
        return "adrian"

    # Check cookie
    cookie_key = request.cookies.get("harrow_token", "")
    if cookie_key and _constant_time_compare(cookie_key, expected):
        return "adrian"

    raise HTTPException(status_code=401, detail="Invalid or missing API key")


async def validate_and_set_cookie(token: str) -> bool:
    """Check token against HARROW_API_KEY. Returns True if valid."""
    expected = _get_api_key()
    if not expected:
        return True  # Dev mode
    return _constant_time_compare(token, expected)
