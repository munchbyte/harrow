"""
core/log_sync.py — HARROW Log-Sync Auto (ASP-003_Sync).

This is the ONLY place for [HARROW->LOG_SYNC] writes.
Writes to the memory_log table. Append-only — no updates, no deletes.

Called automatically after:
- Successful PUSH (email send)
- HITL gate resolved
- Opt-out received
- Stage advance

Routing signal: [HARROW->LOG_SYNC] written to agent_logs on every call.
"""

# Phase 4: implement write_memory_log()
