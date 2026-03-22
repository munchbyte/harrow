"""
engine/liability.py — HARROW Liability Predictor (!Audit_v2).

Cross-references business sector against niche failure dataset to identify
the Critical Failure Mode. The Leak Type gives the technical signal.
The Critical Failure Mode gives the human cost.

NICHE_FAILURES dict maps sector keywords to:
- Critical Failure Mode
- Unowned Consequence

Functions:
- detect_niche(category: str) -> dict — fuzzy match to niche entry
- get_liability_context(lead: dict) -> str — plain English failure scenario

If no niche match: use generic 'missed enquiry' failure mode, flag as WARN.
"""

# Phase 2: implement NICHE_FAILURES, detect_niche(), get_liability_context()
