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

# Phase 2: implement all Voss functions
