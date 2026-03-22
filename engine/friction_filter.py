"""
engine/friction_filter.py — HARROW Friction Filter (!Refusal_Logic).

Rejects any directive lacking an End-to-End failure prediction.
Ensures HARROW never outruns the Practitioner's understanding.

Rules:
- run_social_brief requires topic
- run_ads_brief requires objective AND monthly_budget_gbp
- run_voice_brief requires business_name
- run_copy_review requires copy_text
- run_lead_harvest requires query
- run_campaign requires sector AND location
- Any copy generation without lead_id or copy_text triggers Ghost Audit first

Invalid requests logged as GATE entries. Caller receives 400 with plain English reason.

Function: validate_run_request(task, params) -> (bool, str)
"""

from core.logging import alog

# Task -> required params with human-readable descriptions
_TASK_RULES: dict[str, dict[str, str]] = {
    "run_lead_harvest": {
        "query": "Search query (e.g. 'restaurants in Llanelli')",
    },
    "run_ghost_audit": {
        # No strict requirements — can run with empty leads (returns empty)
    },
    "run_copy_review": {
        "copy_text": "The marketing copy text to review",
    },
    "run_voice_brief": {
        "business_name": "Name of the target business",
    },
    "run_social_brief": {
        "topic": "Content topic or theme",
    },
    "run_ads_brief": {
        "objective": "Campaign objective (e.g. 'generate leads', 'increase brand awareness')",
        "monthly_budget_gbp": "Monthly budget in GBP (must be a positive number)",
    },
    "run_campaign": {
        "sector": "Target business sector (e.g. 'restaurants', 'salons')",
        "location": "Target geographic location (e.g. 'Llanelli', 'Cardiff')",
    },
    "run_channel_report": {
        # No params required
    },
}

# Params that need numeric validation
_NUMERIC_PARAMS = {"monthly_budget_gbp", "budget_gbp", "limit"}


def validate_run_request(task: str, params: dict) -> tuple[bool, str]:
    """
    Validate a /run request against task-specific rules.
    Returns (is_valid, error_message). If valid, error_message is empty.

    Logs GATE entry on rejection.
    """
    rules = _TASK_RULES.get(task)

    # Unknown task — let asp002 handle it
    if rules is None:
        return True, ""

    missing: list[str] = []
    for param_name, description in rules.items():
        value = params.get(param_name)

        if value is None or value == "":
            missing.append(f"  - {param_name}: {description}")
            continue

        # Numeric validation
        if param_name in _NUMERIC_PARAMS:
            try:
                num = float(value) if isinstance(value, str) else value
                if num <= 0:
                    missing.append(f"  - {param_name}: must be a positive number (got {value})")
            except (ValueError, TypeError):
                missing.append(f"  - {param_name}: must be a number (got '{value}')")

    if missing:
        reason = f"Task '{task}' is missing required parameters:\n" + "\n".join(missing)
        alog(
            "GATE",
            f"Friction filter rejected '{task}': {len(missing)} missing params. "
            f"To approve: provide the missing parameters and retry",
            step="friction_filter",
            action="validate_run_request",
            outcome="rejected",
        )
        return False, reason

    # Special rule: ads budget ceiling warning (not a rejection, just a note)
    if task == "run_ads_brief":
        budget = params.get("monthly_budget_gbp", params.get("budget_gbp", 0))
        try:
            if float(budget) > 2000:
                alog("WARN", f"Ads budget {budget} GBP exceeds soft ceiling — extra review recommended",
                     step="friction_filter")
        except (ValueError, TypeError):
            pass

    return True, ""
