"""
core/logging.py — HARROW structured logging.

All logs go through alog(). Never use print().
Writes to agent_logs table. ASP-003 compliant.
Levels: INFO, WARN, ERROR, GATE.
Every ERROR entry must end with 'To resolve this:'.
Every GATE entry must end with 'To approve: [exact instruction]'.
"""

# Phase 1: implement alog(), get_logs()
