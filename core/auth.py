"""
core/auth.py — HARROW authentication.

Provides require_key() FastAPI dependency.
Checks X-API-Key header OR harrow_token session cookie.
If HARROW_API_KEY env var is blank, open access (dev mode) with WARN log.
Applied to every endpoint except GET /health and POST /auth.
"""

# Phase 1: implement require_key(), validate_token(), set_session_cookie()
