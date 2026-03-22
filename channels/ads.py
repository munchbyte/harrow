"""
channels/ads.py — HARROW Paid Ads Channel.

Generates ad campaign briefs via Claude Sonnet.
Budget hard ceiling check. HITL gate fires before returning — always.

Output: audience, ad_copy (headline1, headline2, description, CTA),
KPIs, engine_layer, dashboard_layer.

Task: task_ads_brief(job_id, params, caller)
Params: platform, campaign_type, objective, target_sector, monthly_budget_gbp
"""

import json
from typing import Optional

from core.logging import alog
from core.jobs import update_job
from core.hitl import fire_hitl
from core.go_state import is_armed
from engine.claude_client import call_claude_json
from engine.five_gate import append_sovereignty_footer

# Budget hard ceiling — any campaign above this requires extra review
BUDGET_HARD_CEILING_GBP = 2000

_ADS_BRIEF_PROMPT = """You are HARROW, CMO agent for Goblin Media Network.
Generate a paid advertising campaign brief.

PLATFORM: {platform}
CAMPAIGN TYPE: {campaign_type}
OBJECTIVE: {objective}
TARGET SECTOR: {sector}
MONTHLY BUDGET: {budget_gbp} GBP

CONSTRAINTS:
- UK market only (Wales, South West, South East priority)
- Service SMEs: hospitality, health & wellness, professional services, trades
- Conservative spend approach — diligence over volume
- No hype language

Return ONLY valid JSON:
{{
  "platform": "{platform}",
  "campaign_type": "{campaign_type}",
  "objective": "{objective}",
  "monthly_budget_gbp": {budget_gbp},
  "audience": {{
    "location": "Geographic targeting",
    "demographics": "Age, interests, behaviours",
    "exclusions": "Who to exclude"
  }},
  "ad_copy": {{
    "headline1": "Primary headline (30 chars max)",
    "headline2": "Secondary headline (30 chars max)",
    "description": "Ad description (90 chars max)",
    "cta": "Call to action"
  }},
  "kpis": {{
    "target_cpc": "Target cost per click in GBP",
    "target_ctr": "Target click-through rate",
    "target_conversions": "Expected monthly conversions",
    "target_cpa": "Target cost per acquisition in GBP"
  }},
  "budget_allocation": {{
    "daily_spend": "Daily budget in GBP",
    "testing_budget": "A/B testing allocation percentage",
    "scaling_threshold": "When to increase spend"
  }},
  "engine_layer": "What the ad system actually does (technical truth)",
  "dashboard_layer": "What the SME owner sees and controls (human result)",
  "review_schedule": "When to review performance (e.g. weekly, fortnightly)"
}}"""


async def task_ads_brief(job_id: str, params: dict, caller: str) -> dict:
    """
    Generate an ad campaign brief. HITL gate fires always — ads spend money.
    Budget above hard ceiling triggers extra warning.
    """
    platform = params.get("platform", "google_ads")
    campaign_type = params.get("campaign_type", "search")
    objective = params.get("objective")
    sector = params.get("sector", params.get("target_sector", "service SMEs"))
    budget_gbp = params.get("monthly_budget_gbp", params.get("budget_gbp", 0))

    if not objective:
        raise ValueError("Missing required param: objective")
    if not budget_gbp or budget_gbp <= 0:
        raise ValueError("Missing or invalid param: monthly_budget_gbp (must be > 0)")

    update_job(job_id, progress=f"Generating {platform} {campaign_type} brief ({budget_gbp} GBP/mo)...")

    # Budget ceiling check
    budget_warning = None
    if budget_gbp > BUDGET_HARD_CEILING_GBP:
        budget_warning = (
            f"Budget {budget_gbp} GBP exceeds hard ceiling of {BUDGET_HARD_CEILING_GBP} GBP. "
            f"Extra scrutiny required."
        )
        alog("WARN", budget_warning, job_id=job_id, channel="ads", step="ads_budget_check")

    prompt = _ADS_BRIEF_PROMPT.format(
        platform=platform,
        campaign_type=campaign_type,
        objective=objective,
        sector=sector,
        budget_gbp=budget_gbp,
    )

    try:
        brief = await call_claude_json(
            prompt,
            model="claude-sonnet-4-6-20250514",
            system="You are HARROW, CMO agent. Generate ad campaign briefs. Return valid JSON only.",
            max_tokens=1536,
            job_id=job_id,
            step="ads_brief_gen",
        )
    except Exception as e:
        alog("ERROR", f"Ads brief generation failed: {e}. To resolve this: check Claude API",
             job_id=job_id, channel="ads", step="ads_brief_gen")
        raise

    # Append Sovereignty Footer to description
    if "ad_copy" in brief and "description" in brief["ad_copy"]:
        # Don't append to ad copy itself (character limit), but to the brief
        pass

    if budget_warning:
        brief["budget_warning"] = budget_warning

    # Check GO state
    if not is_armed("ads"):
        alog("WARN", "Ads channel not armed — brief generated but cannot deploy",
             job_id=job_id, channel="ads", step="ads_go_check")

    # HITL gate fires ALWAYS for ads — spending money is irreversible
    trigger = f"Ads brief: {platform} {campaign_type} — {budget_gbp} GBP/mo"
    if budget_warning:
        trigger += " [OVER BUDGET CEILING]"

    gate_id = fire_hitl(
        trigger=trigger,
        job_id=job_id,
        channel="ads",
        context={
            "platform": platform,
            "campaign_type": campaign_type,
            "objective": objective,
            "monthly_budget_gbp": budget_gbp,
            "over_ceiling": budget_gbp > BUDGET_HARD_CEILING_GBP,
        },
        recommended="Review ad brief, targeting, and budget allocation before deploying.",
    )
    brief["hitl_gate_id"] = gate_id

    alog("INFO", f"Ads brief generated, gate {gate_id} pending. To approve: POST /gates/{gate_id}/resolve",
         job_id=job_id, channel="ads", step="ads_brief_complete")

    return brief
