"""
engine/friction_filter.py — HARROW Friction Filter (!Refusal_Logic).

Rejects any directive lacking an End-to-End failure prediction.
Ensures HARROW never outruns the Practitioner's understanding.

Rules:
- run_social_brief requires topic
- run_ads_brief requires objective AND monthly_budget_gbp
- run_voice_brief requires business_name
- run_copy_review requires copy_text
- Any copy generation without lead_id or copy_text triggers Ghost Audit first

Invalid requests logged as GATE entries. Caller receives 400 with plain English reason.

Function: validate_run_request(task, params) -> (bool, str)
"""

# Phase 4: implement validate_run_request()
