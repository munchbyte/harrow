"""
engine/five_gate.py — HARROW Five-Gate Copy Check + Sovereignty Footer.

This is the ONLY place to append the Sovereignty Footer.

Five Gates:
G1 — No-Oriented Frame
G2 — Origin Scar Label
G3 — Translation Bridge
G4 — Calibrated Question
G5 — Receipt Promise

Plus Voss Compliance:
VC1 — Accusation Audit present?
VC2 — Exit ramp present?

Functions:
- run_five_gate(copy_text) -> dict — Claude Haiku call, structured JSON
- append_sovereignty_footer(text) -> str — appends mandatory footer

Footer: 'System-generated blueprint. Final authority and dashboard verification remain with the Practitioner.'
Footer cannot be suppressed. If already present, do not duplicate.
"""

from typing import Optional
from engine.claude_client import call_claude_json
from engine.voss import check_vc1, check_vc2
from core.logging import alog

SOVEREIGNTY_FOOTER = (
    "System-generated blueprint. Final authority and dashboard "
    "verification remain with the Practitioner."
)

_FIVE_GATE_PROMPT = """You are a copy quality assessor for HARROW, the CMO agent.
Analyse the following outbound marketing copy against five gates and return a JSON object.

FIVE GATES:
G1 — No-Oriented Frame: Can the prospect easily say 'no, that's not us'? The copy should NOT force a yes.
G2 — Origin Scar Label: Does the copy name a specific, observable business problem (not vague)?
G3 — Translation Bridge: Does it connect the problem to one of: Time, Money, Focus, or Sovereignty?
G4 — Calibrated Question: Does the closing question use How or What (never Why)?
G5 — Receipt Promise: Does it offer something verifiable and concrete (an audit, a report, a number)?

Return ONLY valid JSON in this exact format:
{
  "G1": {"pass": true/false, "reason": "brief explanation"},
  "G2": {"pass": true/false, "reason": "brief explanation"},
  "G3": {"pass": true/false, "reason": "brief explanation"},
  "G4": {"pass": true/false, "reason": "brief explanation"},
  "G5": {"pass": true/false, "reason": "brief explanation"},
  "all_pass": true/false,
  "summary": "one-sentence overall assessment"
}

COPY TO ASSESS:
---
{copy_text}
---

Return JSON only. No markdown fences. No explanation outside the JSON."""


async def run_five_gate(
    copy_text: str,
    *,
    job_id: Optional[str] = None,
) -> dict:
    """
    Run the Five-Gate Copy Check on a piece of text.
    Returns a dict with G1-G5 results, VC1, VC2, all_pass, and summary.
    Uses Claude Haiku for speed. Adds local VC1/VC2 checks.
    """
    # Claude Haiku analysis for G1-G5
    prompt = _FIVE_GATE_PROMPT.format(copy_text=copy_text)
    try:
        result = await call_claude_json(
            prompt,
            system="You are a marketing copy quality assessor. Return valid JSON only.",
            max_tokens=512,
            job_id=job_id,
            step="five_gate",
        )
    except Exception as e:
        alog(
            "ERROR",
            f"Five-Gate check failed: {e}. To resolve this: check Claude API key and connectivity",
            job_id=job_id, step="five_gate",
        )
        raise

    # Add local Voss compliance checks
    result["VC1"] = {"pass": check_vc1(copy_text), "reason": "Accusation audit pattern check"}
    result["VC2"] = {"pass": check_vc2(copy_text), "reason": "No-oriented exit ramp check"}

    # Recalculate all_pass to include VC checks
    gate_keys = ["G1", "G2", "G3", "G4", "G5", "VC1", "VC2"]
    result["all_pass"] = all(
        result.get(k, {}).get("pass", False) for k in gate_keys
    )

    gate_status = "PASS" if result["all_pass"] else "FAIL"
    failed = [k for k in gate_keys if not result.get(k, {}).get("pass", False)]
    alog(
        "INFO",
        f"Five-Gate result: {gate_status}" + (f" (failed: {', '.join(failed)})" if failed else ""),
        job_id=job_id, step="five_gate",
        action="run_five_gate", outcome=gate_status,
    )

    return result


def append_sovereignty_footer(text: str) -> str:
    """
    Append the mandatory Sovereignty Footer to text.
    If already present, do not duplicate. Cannot be suppressed.
    """
    if SOVEREIGNTY_FOOTER in text:
        return text
    return f"{text.rstrip()}\n\n{SOVEREIGNTY_FOOTER}"
