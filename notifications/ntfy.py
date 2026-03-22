"""
notifications/ntfy.py — HARROW One-Touch Receipt via ntfy.sh.

Mobile push notification on HITL gate fire. Signed approve link.
Auto-log decision to Memory Log.

Functions:
- send_gate_notification(gate) — POST to ntfy.sh topic with gate summary
- generate_approve_url(gate_id) -> str — signed URL with HMAC + TTL (4 hours)
- GET /approve/{token} endpoint — verify HMAC, check TTL, resolve gate, redirect

Destructive gates excluded from One-Touch:
- Opt-out (-99)
- Stage 5 handoff
- Dissonance inquiry

Env vars: NTFY_TOPIC, NTFY_SECRET. If not configured, skip silently (log INFO).
All One-Touch approvals logged with resolver=one_touch_receipt.
"""

# Phase 4: implement send_gate_notification(), generate_approve_url()
