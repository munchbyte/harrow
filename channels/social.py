"""
channels/social.py — HARROW Social Channel.

Generates content briefs via Claude Sonnet. PAC-Receipt Loop applied.
Anti-Hype constraint in system prompt.
Routes to Push CMS Agent via [HARROW->PUSH_CMS] task.
Fires HITL gate before routing — publishing is irreversible.

Task: task_social_brief(job_id, params, caller)
Params: platform, content_type, topic, sector
"""

import json
from typing import Optional

from core.logging import alog
from core.jobs import update_job
from core.hitl import fire_hitl
from core.go_state import is_armed
from engine.claude_client import call_claude_json
from engine.five_gate import append_sovereignty_footer

_SOCIAL_BRIEF_PROMPT = """You are HARROW, CMO agent for Goblin Media Network.
Generate a social media content brief following the PAC-Receipt Loop.

PLATFORM: {platform}
CONTENT TYPE: {content_type}
TOPIC: {topic}
TARGET SECTOR: {sector}

PAC-RECEIPT LOOP:
P — Problem: Name a specific operational failure the target SME faces
A — Agitate: Show the cost of the Black Box — what they cannot audit
C — Solve: How GMN/ATS addresses this — Engine and Dashboard together
R — Receipt: What verifiable proof can be offered

ANTI-HYPE CONSTRAINT — NEVER use: revolutionary, game-changer, disruptive, passive income,
set-and-forget, automated wealth, explosive growth, 10x, unlock your potential, the secret to,
the one thing, the hack.

TONE: Late-Night FM DJ. Calm, measured, no urgency. No exclamation marks.

Return ONLY valid JSON:
{{
  "platform": "{platform}",
  "content_type": "{content_type}",
  "headline": "Attention-grabbing headline (under 10 words)",
  "body": "Main content (under 200 words for posts, under 100 for stories)",
  "cta": "Call to action — calibrated question using How or What",
  "hashtags": ["tag1", "tag2", "tag3"],
  "pac_breakdown": {{
    "problem": "The specific friction named",
    "agitate": "The cost of inaction",
    "solve": "The GMN/ATS solution",
    "receipt": "The verifiable proof offered"
  }},
  "engine_layer": "What the system actually does (technical truth)",
  "dashboard_layer": "What the SME owner experiences (human result)",
  "push_cms_routing": {{
    "action": "schedule_post",
    "platform": "{platform}",
    "content_type": "{content_type}"
  }}
}}"""


async def task_social_brief(job_id: str, params: dict, caller: str) -> dict:
    """
    Generate a social content brief. Fires HITL gate — publishing is irreversible.
    """
    platform = params.get("platform", "linkedin")
    content_type = params.get("content_type", "post")
    topic = params.get("topic")
    sector = params.get("sector", "service SMEs")

    if not topic:
        raise ValueError("Missing required param: topic")

    update_job(job_id, progress=f"Generating {platform} {content_type} brief...")

    prompt = _SOCIAL_BRIEF_PROMPT.format(
        platform=platform,
        content_type=content_type,
        topic=topic,
        sector=sector,
    )

    try:
        brief = await call_claude_json(
            prompt,
            model="claude-sonnet-4-6-20250514",
            system="You are HARROW, CMO agent. Generate social content briefs. Return valid JSON only.",
            max_tokens=1536,
            job_id=job_id,
            step="social_brief_gen",
        )
    except Exception as e:
        alog("ERROR", f"Social brief generation failed: {e}. To resolve this: check Claude API",
             job_id=job_id, channel="social", step="social_brief_gen")
        raise

    # Append Sovereignty Footer to body
    if "body" in brief:
        brief["body"] = append_sovereignty_footer(brief["body"])

    brief["topic"] = topic

    # Check GO state
    if not is_armed("social"):
        alog("WARN", "Social channel not armed — brief generated but cannot publish",
             job_id=job_id, channel="social", step="social_go_check")

    # Fire HITL gate — publishing is irreversible
    gate_id = fire_hitl(
        trigger=f"Social {content_type} for {platform}: {topic}",
        job_id=job_id,
        channel="social",
        context={"platform": platform, "content_type": content_type, "topic": topic},
        recommended="Review content brief. Approve to route to Push CMS Agent for publishing.",
    )
    brief["hitl_gate_id"] = gate_id

    # Log routing signal (actual Push CMS call happens after gate approval)
    alog("INFO",
         f"[HARROW->PUSH_CMS] Social brief generated, gate {gate_id} pending. "
         f"To approve: POST /gates/{gate_id}/resolve",
         job_id=job_id, channel="social", step="social_route")

    return brief
