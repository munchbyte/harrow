"""
channels/voice.py — HARROW Voice Channel.

Generates Vapi voice agent briefs via Claude Sonnet.
Outbound script type fires HITL gate before returning brief.

Output includes: agent_name, greeting, key_messages, qualifying_question,
objection_handling, close, vapi_system_prompt.
Sovereignty Footer appended to vapi_system_prompt.

Task: task_voice_brief(job_id, params, caller)
Params: business_name, leak_type, leak_label, script_type (inbound/outbound), lead_id
"""

import json
from typing import Optional

from core.logging import alog
from core.jobs import update_job
from core.hitl import fire_hitl
from core.go_state import is_armed
from engine.claude_client import call_claude_json
from engine.five_gate import append_sovereignty_footer
from engine.liability import get_liability_context

_VOICE_BRIEF_PROMPT = """You are HARROW, CMO agent. Generate a Vapi voice agent brief for the following scenario.

BUSINESS: {business_name}
SECTOR: {sector}
LEAK TYPE: {leak_type}
LEAK LABEL: {leak_label}
SCRIPT TYPE: {script_type}
LIABILITY CONTEXT: {liability_context}

Generate a voice agent brief. The tone should be Late-Night FM DJ: calm, warm, deliberate.
No exclamation marks. No urgency language. The agent represents Goblin Media Network.

Return ONLY valid JSON:
{{
  "agent_name": "A short, professional agent name",
  "greeting": "The opening greeting (15-25 words)",
  "key_messages": ["message 1", "message 2", "message 3"],
  "qualifying_question": "A calibrated question using How or What",
  "objection_handling": {{
    "too_busy": "Response to 'I'm too busy'",
    "not_interested": "Response to 'Not interested'",
    "already_have_someone": "Response to 'We already have a marketing agency'"
  }},
  "close": "The closing statement — offer something verifiable, give permission to say no",
  "vapi_system_prompt": "Full system prompt for the Vapi agent (100-200 words)"
}}"""


async def task_voice_brief(job_id: str, params: dict, caller: str) -> dict:
    """
    Generate a Vapi voice agent brief.
    Outbound scripts fire HITL gate. Inbound scripts return directly.
    """
    business_name = params.get("business_name")
    if not business_name:
        raise ValueError("Missing required param: business_name")

    leak_type = params.get("leak_type", "CONTACT")
    leak_label = params.get("leak_label", "slow response to enquiries")
    script_type = params.get("script_type", "inbound")
    sector = params.get("sector", "service business")
    lead_id = params.get("lead_id")

    update_job(job_id, progress=f"Generating {script_type} voice brief for {business_name}...")

    # Build liability context
    lead_data = {
        "name": business_name,
        "category": sector,
        "leak_type": leak_type,
        "leak_label": leak_label,
    }
    liability_context = get_liability_context(lead_data)

    # Generate brief via Claude
    prompt = _VOICE_BRIEF_PROMPT.format(
        business_name=business_name,
        sector=sector,
        leak_type=leak_type,
        leak_label=leak_label,
        script_type=script_type,
        liability_context=liability_context,
    )

    try:
        brief = await call_claude_json(
            prompt,
            model="claude-sonnet-4-6-20250514",
            system="You are HARROW, CMO agent. Generate voice agent briefs. Return valid JSON only.",
            max_tokens=1536,
            job_id=job_id,
            step="voice_brief_gen",
        )
    except Exception as e:
        alog("ERROR", f"Voice brief generation failed: {e}. To resolve this: check Claude API",
             job_id=job_id, channel="voice", step="voice_brief_gen")
        raise

    # Append Sovereignty Footer to vapi_system_prompt
    if "vapi_system_prompt" in brief:
        brief["vapi_system_prompt"] = append_sovereignty_footer(brief["vapi_system_prompt"])

    brief["script_type"] = script_type
    brief["business_name"] = business_name
    brief["leak_type"] = leak_type

    # Outbound scripts fire HITL gate — outbound calls are irreversible
    if script_type == "outbound":
        if not is_armed("voice"):
            alog("WARN", "Voice channel not armed — brief generated but gate required",
                 job_id=job_id, channel="voice", step="voice_go_check")

        gate_id = fire_hitl(
            trigger=f"Outbound voice brief for {business_name}",
            job_id=job_id,
            channel="voice",
            context={"business_name": business_name, "leak_type": leak_type, "script_type": "outbound"},
            recommended="Review voice brief before deploying outbound agent.",
        )
        brief["hitl_gate_id"] = gate_id
        alog("GATE", f"Voice outbound gate fired (gate {gate_id}). To approve: POST /gates/{gate_id}/resolve",
             job_id=job_id, channel="voice", step="voice_hitl")

    alog("INFO", f"Voice brief generated: {script_type} for {business_name}",
         job_id=job_id, channel="voice", step="voice_brief_complete")

    return brief
