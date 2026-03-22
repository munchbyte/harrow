"""
channels/social.py — HARROW Social Channel.

Generates content briefs via Claude Sonnet. PAC-Receipt Loop applied.
Anti-Hype constraint in system prompt.
Routes to Push CMS Agent via [HARROW->PUSH_CMS] task.
Fires HITL gate before routing — publishing is irreversible.

Task: task_social_brief(job_id, params, caller)
Params: platform, content_type, topic, sector
"""

# Phase 4: implement task_social_brief()
