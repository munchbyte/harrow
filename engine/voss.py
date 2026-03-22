"""
engine/voss.py — HARROW Voss Technique Engine.

Applies Chris Voss negotiation-derived communication techniques
across all outbound copy. Structural rules, not stylistic preferences.

Six techniques: Accusation Audit, No-Oriented Questions, Mirroring,
Labelling, Calibrated Questions, Late-Night FM DJ Tone.

Functions:
- apply_accusation_audit(leak_type, sector) -> str — M1 opening line
- apply_label(leak_type, critical_failure) -> str — M2 emotional label
- apply_no_oriented_close(leak_type) -> str — M3 closing question
- check_vc1(copy_text) -> bool — accusation audit pattern present?
- check_vc2(copy_text) -> bool — no-oriented exit ramp present?
"""

import re

# --- Accusation Audit templates by leak type ---
# M1 opener: name the negative thing the prospect is probably thinking
_ACCUSATION_AUDITS: dict[str, str] = {
    "BOOKING": (
        "You probably think another marketing email is the last thing you need "
        "when you are already stretched thin running the business."
    ),
    "CONTACT": (
        "You are likely thinking that if your current setup was really losing you enquiries, "
        "you would have noticed by now."
    ),
    "SPEED": (
        "You might feel that your website loads fine on your phone "
        "and anyone complaining about speed is being dramatic."
    ),
    "TRUST": (
        "You may be thinking your reputation speaks for itself "
        "and online reviews are not something you need to manage."
    ),
    "CONTENT": (
        "You probably believe that if your website has not caused problems so far, "
        "there is no reason to change it now."
    ),
}

# --- Labelling templates by leak type ---
# M2 opener: name the emotion behind their situation
_LABELS: dict[str, str] = {
    "BOOKING": "It seems like you have built something solid, and the idea of changing how bookings work feels like an unnecessary risk.",
    "CONTACT": "It sounds like you have always managed enquiries your way, and the suggestion that you are missing some feels almost insulting.",
    "SPEED": "It feels like being told your website is slow is a criticism of the business you have built.",
    "TRUST": "It seems like the thought of actively managing your online reputation feels inauthentic to you.",
    "CONTENT": "It sounds like your website was set up years ago and has just worked — touching it feels like opening a can of worms.",
}

# --- No-Oriented Close templates by leak type ---
# M3 closer: structured so 'no' still moves forward
_NO_ORIENTED_CLOSES: dict[str, str] = {
    "BOOKING": "Would it be a terrible idea to see exactly how many bookings your current setup is missing each month?",
    "CONTACT": "Would it be unreasonable to run a quick audit showing where enquiries are falling through?",
    "SPEED": "Would it be wrong to check whether your page speed is actually costing you visitors?",
    "TRUST": "Would it be ridiculous to see what a potential customer finds when they search for you right now?",
    "CONTENT": "Would it be out of line to show you what your website looks like to someone visiting for the first time?",
}

_DEFAULT_AUDIT = (
    "You probably think another business email is the last thing you need right now."
)
_DEFAULT_LABEL = (
    "It seems like you have built something that works, and changing it feels like an unnecessary risk."
)
_DEFAULT_CLOSE = (
    "Would it be a terrible idea to see what a new customer actually experiences when they find you online?"
)


def apply_accusation_audit(leak_type: str, sector: str = "") -> str:
    """Return an M1 accusation audit opening line for the given leak type."""
    return _ACCUSATION_AUDITS.get(leak_type, _DEFAULT_AUDIT)


def apply_label(leak_type: str, critical_failure: str = "") -> str:
    """Return an M2 labelling line for the given leak type."""
    return _LABELS.get(leak_type, _DEFAULT_LABEL)


def apply_no_oriented_close(leak_type: str) -> str:
    """Return an M3 no-oriented closing question for the given leak type."""
    return _NO_ORIENTED_CLOSES.get(leak_type, _DEFAULT_CLOSE)


# --- Voss Compliance Checks ---

# VC1: Accusation audit patterns — phrases that acknowledge resistance
_VC1_PATTERNS = [
    r"you(?:'re| are)?\s+(?:probably|likely|might|may)\s+(?:think|feel|believe|wonder)",
    r"you(?:'re| are)?\s+(?:right to|entitled to)\s+(?:think|feel|believe|question)",
    r"it\s+(?:might|may|probably)\s+(?:seem|feel|sound|look)\s+like",
    r"the last thing you\s+(?:need|want)",
    r"you\s+(?:did not|didn't)\s+ask for",
]

# VC2: No-oriented / exit ramp patterns — gives prospect a way to say no
_VC2_PATTERNS = [
    r"would it be\s+(?:a terrible idea|unreasonable|wrong|out of line|ridiculous|too much)",
    r"is it\s+(?:a bad idea|unreasonable|wrong|too much)",
    r"feel free to\s+(?:ignore|delete|disregard|say no)",
    r"no (?:obligation|pressure|commitment)",
    r"if (?:this isn't|this is not|that's not|that is not)\s+(?:for you|relevant|useful)",
    r"you(?:'re| are)?\s+(?:welcome|free)\s+to\s+(?:ignore|say no|pass)",
    r"happy to\s+(?:leave it|step back|drop it)",
]


def check_vc1(copy_text: str) -> bool:
    """Check if copy contains an accusation audit pattern (VC1)."""
    lower = copy_text.lower()
    return any(re.search(p, lower) for p in _VC1_PATTERNS)


def check_vc2(copy_text: str) -> bool:
    """Check if copy contains a no-oriented exit ramp (VC2)."""
    lower = copy_text.lower()
    return any(re.search(p, lower) for p in _VC2_PATTERNS)
