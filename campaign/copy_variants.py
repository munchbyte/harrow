"""
campaign/copy_variants.py — HARROW Per-Leak-Type Copy Templates.

COPY_TEMPLATES dict: BOOKING, CONTACT, SPEED, TRUST, CONTENT
Each has M1/M2/M3 structural prompts with embedded Voss techniques.
Templates are prompts — not final copy. Claude Sonnet fills them.

A DEFAULT template handles any leak_type not in the dict (with WARN log).

Message structure:
- M1: Accusation Audit + No-Oriented Question
- M2: Labelling + Calibrated Question
- M3: No-Oriented Close + Explicit Permission to Say No
"""

# Phase 3: implement COPY_TEMPLATES, get_template()
