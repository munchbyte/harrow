"""
channels/email.py — HARROW Email Channel.

Copy generation and review for M1/M2/M3 email sequences.
Uses Sonnet 4.6 for generation, Haiku 4.5 for gate checks.

Prompt includes: leak_type, leak_label, liability_context, sector, business_name, tone.
Each generated message has Sovereignty Footer appended automatically.

Tasks:
- task_copy_review(job_id, params, caller) — Five-Gate + Voss check on supplied copy_text
- generate_email_sequence(lead) — generate M1/M2/M3 for one lead
"""

import json
from typing import Optional

from core.logging import alog
from core.jobs import update_job
from engine.claude_client import call_sonnet
from engine.five_gate import run_five_gate, append_sovereignty_footer
from engine.voss import (
    apply_accusation_audit,
    apply_label,
    apply_no_oriented_close,
    check_vc1,
    check_vc2,
)
from engine.liability import get_liability_context

# --- Anti-Hype word list ---
_BANNED_WORDS = [
    "revolutionary", "game-changer", "game changer", "disruptive",
    "passive income", "set-and-forget", "set and forget",
    "automated wealth", "explosive growth", "10x",
    "unlock your potential", "the secret to", "the one thing", "the hack",
]

# --- Tone instructions ---
_TONE_INSTRUCTIONS = {
    "dj": "Late-Night FM DJ tone: slow, calm, deliberate. No urgency. No exclamation marks. Every sentence earns its place.",
    "formal": "Professional and measured. Clear, direct language. No jargon. No enthusiasm.",
    "concise": "Extremely concise. Short sentences. No filler. Every word counts.",
}

# --- M1/M2/M3 generation prompts ---

_M1_PROMPT = """Generate a cold email (M1) for the following business.
This is the FIRST message — the accusation audit opener.

BUSINESS: {business_name}
SECTOR: {sector}
LEAK TYPE: {leak_type}
LEAK LABEL: {leak_label}
LIABILITY CONTEXT: {liability_context}

STRUCTURAL REQUIREMENTS:
1. Open with an Accusation Audit — acknowledge what they are probably thinking:
   "{accusation_audit}"
2. Name the specific problem (Origin Scar Label) — use the leak label above
3. Connect to Time, Money, Focus, or Sovereignty (Translation Bridge)
4. Close with a No-Oriented Question — the prospect can say no and still move forward
5. Offer something verifiable (Receipt Promise) — a free audit, a specific number, a report

TONE: {tone_instruction}

ANTI-HYPE: Never use: revolutionary, game-changer, disruptive, passive income, set-and-forget, automated wealth, explosive growth, 10x, unlock your potential, the secret to, the one thing, the hack.

Return the email only. No subject line. No sign-off beyond a first name. Keep it under 150 words."""

_M2_PROMPT = """Generate a follow-up email (M2) for the following business.
This is the SECOND message — sent 5 days after M1 with no reply.

BUSINESS: {business_name}
SECTOR: {sector}
LEAK TYPE: {leak_type}
LEAK LABEL: {leak_label}
LIABILITY CONTEXT: {liability_context}

STRUCTURAL REQUIREMENTS:
1. Open with a Label — name the emotion behind their situation:
   "{label}"
2. Reference M1 briefly (do NOT repeat it)
3. Add one new piece of evidence or a specific number
4. Close with a Calibrated Question using How or What (never Why)
5. Include an explicit exit ramp — make it easy to say no

TONE: {tone_instruction}

Return the email only. Under 120 words."""

_M3_PROMPT = """Generate a final email (M3) for the following business.
This is the THIRD and LAST message — sent 5 days after M2 with no reply.

BUSINESS: {business_name}
SECTOR: {sector}
LEAK TYPE: {leak_type}
LEAK LABEL: {leak_label}
LIABILITY CONTEXT: {liability_context}

STRUCTURAL REQUIREMENTS:
1. Acknowledge this is the last message
2. Briefly restate the core problem in one sentence
3. Close with a No-Oriented Question:
   "{no_oriented_close}"
4. Give explicit permission to ignore — no guilt, no pressure
5. Sign off cleanly

TONE: {tone_instruction}

Return the email only. Under 100 words."""


def _check_anti_hype(text: str) -> list[str]:
    """Return list of banned words found in text."""
    lower = text.lower()
    return [word for word in _BANNED_WORDS if word in lower]


# ── Task: Copy Review ──────────────────────────────────────────────────

async def task_copy_review(job_id: str, params: dict, caller: str) -> dict:
    """
    Five-Gate + Voss check on supplied copy_text.
    Params: copy_text (str, required)
    """
    copy_text = params.get("copy_text")
    if not copy_text:
        raise ValueError("Missing required param: copy_text")

    update_job(job_id, progress="Running Five-Gate + Voss check...")

    # Run Five-Gate (includes VC1/VC2)
    gate_results = await run_five_gate(copy_text, job_id=job_id)

    # Anti-hype check
    hype_violations = _check_anti_hype(copy_text)
    gate_results["anti_hype"] = {
        "pass": len(hype_violations) == 0,
        "violations": hype_violations,
    }

    if hype_violations:
        gate_results["all_pass"] = False
        alog("WARN", f"Anti-hype violations: {', '.join(hype_violations)}",
             job_id=job_id, channel="email", step="copy_review")

    return {
        "copy_text": copy_text,
        "gate_results": gate_results,
        "overall": "PASS" if gate_results["all_pass"] else "FAIL",
    }


# ── Generate Email Sequence ────────────────────────────────────────────

async def generate_email_sequence(
    lead: dict,
    *,
    tone: str = "dj",
    job_id: Optional[str] = None,
) -> dict:
    """
    Generate M1/M2/M3 email sequence for one lead.
    Returns dict with m1, m2, m3, gate_results, voss_results.
    """
    business_name = lead.get("business_name", lead.get("name", "the business"))
    sector = lead.get("sector", lead.get("category", "service business"))
    leak_type = lead.get("leak_type", "CONTACT")
    leak_label = lead.get("leak_label", "slow response to enquiries")
    liability_context = get_liability_context(lead)
    tone_instruction = _TONE_INSTRUCTIONS.get(tone, _TONE_INSTRUCTIONS["dj"])

    # Voss technique inputs
    accusation_audit = apply_accusation_audit(leak_type, sector)
    label = apply_label(leak_type)
    no_oriented_close = apply_no_oriented_close(leak_type)

    # Generate M1
    alog("INFO", f"Generating M1 for {business_name}", job_id=job_id, channel="email", step="gen_m1")
    m1_prompt = _M1_PROMPT.format(
        business_name=business_name, sector=sector, leak_type=leak_type,
        leak_label=leak_label, liability_context=liability_context,
        accusation_audit=accusation_audit, tone_instruction=tone_instruction,
    )
    m1 = await call_sonnet(m1_prompt, job_id=job_id, step="gen_m1")
    m1 = append_sovereignty_footer(m1)

    # Generate M2
    alog("INFO", f"Generating M2 for {business_name}", job_id=job_id, channel="email", step="gen_m2")
    m2_prompt = _M2_PROMPT.format(
        business_name=business_name, sector=sector, leak_type=leak_type,
        leak_label=leak_label, liability_context=liability_context,
        label=label, tone_instruction=tone_instruction,
    )
    m2 = await call_sonnet(m2_prompt, job_id=job_id, step="gen_m2")
    m2 = append_sovereignty_footer(m2)

    # Generate M3
    alog("INFO", f"Generating M3 for {business_name}", job_id=job_id, channel="email", step="gen_m3")
    m3_prompt = _M3_PROMPT.format(
        business_name=business_name, sector=sector, leak_type=leak_type,
        leak_label=leak_label, liability_context=liability_context,
        no_oriented_close=no_oriented_close, tone_instruction=tone_instruction,
    )
    m3 = await call_sonnet(m3_prompt, job_id=job_id, step="gen_m3")
    m3 = append_sovereignty_footer(m3)

    # Run Five-Gate on all three
    gate_results = {}
    for label_key, text in [("m1", m1), ("m2", m2), ("m3", m3)]:
        try:
            gate_results[label_key] = await run_five_gate(text, job_id=job_id)
        except Exception as e:
            alog("WARN", f"Five-Gate failed for {label_key}: {e}",
                 job_id=job_id, channel="email", step=f"gate_{label_key}")
            gate_results[label_key] = {"error": str(e)}

    # Voss compliance summary
    voss_results = {
        "m1": {"VC1": check_vc1(m1), "VC2": check_vc2(m1)},
        "m2": {"VC1": check_vc1(m2), "VC2": check_vc2(m2)},
        "m3": {"VC1": check_vc1(m3), "VC2": check_vc2(m3)},
    }

    # Anti-hype check
    for label_key, text in [("m1", m1), ("m2", m2), ("m3", m3)]:
        violations = _check_anti_hype(text)
        if violations:
            alog("WARN", f"Anti-hype violation in {label_key}: {', '.join(violations)}",
                 job_id=job_id, channel="email", step=f"hype_{label_key}")

    return {
        "business_name": business_name,
        "leak_type": leak_type,
        "m1": m1,
        "m2": m2,
        "m3": m3,
        "gate_results": gate_results,
        "voss_results": voss_results,
    }
