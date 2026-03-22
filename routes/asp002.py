"""
routes/asp002.py — HARROW ASP-002 standard endpoints.

Endpoints:
- GET  /health       — alive check, version, uptime (no auth)
- GET  /info         — agent description, capabilities, tasks
- POST /run          — execute task, create job, return job_id
- GET  /status/{id}  — check job progress and result
- GET  /logs         — activity log with ?channel= ?level= ?limit= filters
- POST /stop/{id}    — gracefully stop a running job
- POST /auth         — validate API key, set session cookie

All responses: {status, agent_id, timestamp, data/error}
"""

# Phase 1: implement all ASP-002 route handlers
