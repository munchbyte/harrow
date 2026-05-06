"""
core/sub_agents.py — HARROW sub-agent registry.

Static map of every sub-agent HARROW knows about. Used by /health to report
sub-agent reachability and by future routing logic to look up the right client.

Each entry:
- agent_id        — stable identifier
- name            — human-readable
- tier            — ASP-002 tier (3 = sub-agent under HARROW)
- url_env         — env var holding the internal URL
- key_env         — env var holding the API key
- public_url      — public URL for reference (not used for internal calls)
- status          — 'live' | 'planned' | 'deprecated'
- live_since      — ISO date the sub-agent went live
- tasks           — list of task names HARROW can dispatch via POST /run
- primary_task    — the most common task HARROW dispatches
- health_fn       — async callable returning the agent's /health response
"""

from typing import Awaitable, Callable, Optional

from integrations import push_client, interact_client


SubAgentHealthFn = Callable[[], Awaitable[dict]]


SUB_AGENTS: dict[str, dict] = {
    "push_cms": {
        "agent_id": "push_cms",
        "name": "Push CMS",
        "tier": 3,
        "parent": "harrow",
        "url_env": "PUSH_CMS_AGENT_URL",
        "key_env": "PUSH_CMS_API_KEY",
        "public_url": "https://push.goblinmedia.net",
        "status": "live",
        "live_since": "2026-05-01",
        "primary_task": "publish_content_brief",
        "tasks": [
            "publish_content_brief",
            "run_draft",
            "run_carousel_brief",
            "run_metrics_sync",
            "run_archive",
        ],
        "health_fn": push_client.health,
    },
    "interact_crm": {
        "agent_id": "interact_crm",
        "name": "Interact CRM",
        "tier": 3,
        "parent": "harrow",
        "url_env": "INTERACT_AGENT_URL",
        "key_env": "INTERACT_API_KEY",
        "public_url": None,        # internal-only until otherwise confirmed
        "status": "wiring",        # promote to 'live' after smoke discovery passes
        "live_since": None,        # set once smoke proves the wiring
        "primary_task": None,      # to be discovered via /info
        "tasks": [],               # populated after first successful /info call
        "health_fn": interact_client.health,
    },
}


def get(agent_id: str) -> Optional[dict]:
    """Return the registry entry for agent_id, or None."""
    return SUB_AGENTS.get(agent_id)


def list_live() -> list[dict]:
    """Return all sub-agents with status='live'."""
    return [a for a in SUB_AGENTS.values() if a.get("status") == "live"]
