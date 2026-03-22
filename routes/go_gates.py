"""
routes/go_gates.py — HARROW GO gate endpoints.

Endpoints:
- POST /go/{channel}      — arm a channel (email, voice, social, ads)
- POST /revoke/{channel}  — disarm a channel immediately
- GET  /go-status          — return all four channel GO states
"""

# Phase 1: implement go_gate route handlers
