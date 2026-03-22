"""
core/go_state.py — HARROW GO flag manager.

Per-channel GO state: email, voice, social, ads.
Each channel has an independent armed/revoked state.
State persisted in SQLite go_state table. Survives server restarts.
"""

# Phase 1: implement arm_channel(), revoke_channel(), is_armed(), get_all_go_states()
