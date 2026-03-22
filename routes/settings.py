"""
routes/settings.py — HARROW Settings endpoints.

Endpoints:
- POST /settings/key/test          — test API key against target service
- POST /settings/key/update        — update key in .env, trigger restart
- GET  /settings/channel/{channel} — return current channel config
- POST /settings/channel/{channel} — update channel config
- GET  /settings/agent-info        — version, uptime, capabilities, registry SQL
"""

# Phase 5: implement settings route handlers
