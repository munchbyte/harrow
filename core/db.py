"""
core/db.py — HARROW database layer.

This is the ONLY place for sqlite3 calls. All other files import from here.
Database: state/harrow.db — auto-created on first run.

Tables: jobs, agent_logs, go_state, hitl_gates, campaigns, campaign_steps,
        copy_outputs, rejection_log, memory_log, settings
"""

# Phase 1: implement init_db(), get_db(), all table creation, helper functions
