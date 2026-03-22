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

# Phase 2: implement run_five_gate(), append_sovereignty_footer()
