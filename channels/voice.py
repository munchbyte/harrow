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

# Phase 4: implement task_voice_brief()
