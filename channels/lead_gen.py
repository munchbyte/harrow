"""
channels/lead_gen.py — HARROW Lead Generation (Workflows A + B).

Workflow A: Lead Harvest
- Outscraper Google Maps scraping + email enrichment
- ICP filter: hard rejects and soft warns
- Results written to Google Sheets Master Lead Sheet

Workflow B: Ghost Audit
- Firecrawl website scraping
- Claude Haiku analysis per lead
- Returns: leak_score (1-10), leak_type, leak_label
- Integrates Liability Predictor for niche-specific failure context

ICP Hard Rejects: no website, no phone, reviews >500, reviews <3, permanently closed
ICP Soft Warns: rating <2.5, reviews <10, no email, enterprise-hint keywords

Six Leak Types: BOOKING, CONTACT, SPEED, TRUST, CONTENT, NONE
"""

import os
import json
from typing import Optional
import requests

from core.logging import alog
from core.jobs import update_job
from engine.claude_client import call_claude_json
from engine.liability import get_liability_context

# Enterprise-hint keywords that trigger a soft WARN
_ENTERPRISE_HINTS = [
    "franchise", "chain", "group", "plc", "ltd", "corporate",
    "national", "international", "locations", "branches",
]

LEAK_TYPES = ["BOOKING", "CONTACT", "SPEED", "TRUST", "CONTENT", "NONE"]


# ── ICP Filter ─────────────────────────────────────────────────────────

def _icp_filter(lead: dict) -> tuple[str, list[str]]:
    """
    Apply ICP filter to a lead.
    Returns: (status, reasons) where status is 'PASS', 'WARN', or 'REJECT'.
    """
    reasons: list[str] = []
    rejected = False

    # Hard rejects
    if not lead.get("site"):
        reasons.append("REJECT: no website")
        rejected = True
    if not lead.get("phone"):
        reasons.append("REJECT: no phone number")
        rejected = True
    reviews = lead.get("reviews", 0) or 0
    if reviews > 500:
        reasons.append(f"REJECT: {reviews} reviews (enterprise-scale)")
        rejected = True
    if 0 < reviews < 3:
        reasons.append(f"REJECT: only {reviews} reviews (too small)")
        rejected = True
    if lead.get("permanently_closed") or lead.get("business_status") == "CLOSED_PERMANENTLY":
        reasons.append("REJECT: permanently closed")
        rejected = True

    if rejected:
        return "REJECT", reasons

    # Soft warns
    rating = lead.get("rating", 0) or 0
    if 0 < rating < 2.5:
        reasons.append(f"WARN: low rating ({rating})")
    if 0 < reviews < 10:
        reasons.append(f"WARN: few reviews ({reviews})")
    if not lead.get("email") and not lead.get("email_1"):
        reasons.append("WARN: no email found")

    # Enterprise hints
    name = (lead.get("name") or "").lower()
    description = (lead.get("description") or "").lower()
    text = f"{name} {description}"
    for hint in _ENTERPRISE_HINTS:
        if hint in text:
            reasons.append(f"WARN: enterprise hint '{hint}'")
            break

    status = "WARN" if reasons else "PASS"
    return status, reasons


# ── Workflow A: Lead Harvest ───────────────────────────────────────────

async def task_lead_harvest(job_id: str, params: dict, caller: str) -> dict:
    """
    Outscraper Google Maps scraping + ICP filter.
    Params: query (str, required), limit (int, default 20), dry_run (bool, default True)
    """
    query = params.get("query")
    if not query:
        raise ValueError("Missing required param: query")

    limit = params.get("limit", 20)
    dry_run = params.get("dry_run", True)

    update_job(job_id, progress=f"Harvesting leads: '{query}' (limit={limit}, dry_run={dry_run})")
    alog("INFO", f"Lead harvest started: '{query}' limit={limit} dry_run={dry_run}",
         job_id=job_id, caller=caller, channel="lead_gen", step="harvest_start")

    api_key = os.environ.get("OUTSCRAPER_API_KEY", "")
    if not api_key:
        raise RuntimeError("OUTSCRAPER_API_KEY not set. To resolve this: add key to .env")

    # Call Outscraper Google Maps API
    try:
        update_job(job_id, progress="Calling Outscraper API...")
        response = requests.get(
            "https://api.app.outscraper.com/maps/search-v3",
            params={"query": query, "limit": limit, "async": False},
            headers={"X-API-KEY": api_key},
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
    except requests.Timeout:
        alog("ERROR", "Outscraper API timeout. To resolve this: retry with smaller limit or check API status",
             job_id=job_id, channel="lead_gen", step="harvest_outscraper")
        raise
    except requests.HTTPError as e:
        alog("ERROR", f"Outscraper API error: {e}. To resolve this: check API key and quota",
             job_id=job_id, channel="lead_gen", step="harvest_outscraper")
        raise

    # Extract leads from nested response
    raw_leads = []
    if isinstance(data, list) and data:
        raw_leads = data[0] if isinstance(data[0], list) else data
    elif isinstance(data, dict):
        raw_leads = data.get("data", [])
        if isinstance(raw_leads, list) and raw_leads and isinstance(raw_leads[0], list):
            raw_leads = raw_leads[0]

    update_job(job_id, progress=f"Got {len(raw_leads)} raw results, applying ICP filter...")

    # Apply ICP filter
    passed: list[dict] = []
    warned: list[dict] = []
    rejected: list[dict] = []

    for lead in raw_leads:
        status, reasons = _icp_filter(lead)
        lead["_icp_status"] = status
        lead["_icp_reasons"] = reasons

        if status == "REJECT":
            rejected.append(lead)
        elif status == "WARN":
            warned.append(lead)
        else:
            passed.append(lead)

    alog("INFO",
         f"ICP filter: {len(passed)} PASS, {len(warned)} WARN, {len(rejected)} REJECT",
         job_id=job_id, channel="lead_gen", step="harvest_icp")

    update_job(job_id, progress=f"ICP filter done: {len(passed)} PASS, {len(warned)} WARN, {len(rejected)} REJECT")

    # In dry_run mode, don't write to Google Sheets
    if dry_run:
        alog("INFO", "Dry run — skipping Google Sheets write",
             job_id=job_id, channel="lead_gen", step="harvest_sheets")
    else:
        update_job(job_id, progress="Writing to Google Sheets...")
        try:
            _write_to_sheets(passed + warned, job_id)
        except Exception as e:
            alog("ERROR", f"Google Sheets write failed: {e}. To resolve this: check GOOGLE_SHEETS_ID and service account",
                 job_id=job_id, channel="lead_gen", step="harvest_sheets")
            # Non-fatal — leads are still in the result

    result = {
        "query": query,
        "total_raw": len(raw_leads),
        "passed": len(passed),
        "warned": len(warned),
        "rejected": len(rejected),
        "dry_run": dry_run,
        "leads": [
            {
                "name": l.get("name"),
                "site": l.get("site"),
                "phone": l.get("phone"),
                "email": l.get("email") or l.get("email_1"),
                "rating": l.get("rating"),
                "reviews": l.get("reviews"),
                "category": l.get("category") or l.get("type"),
                "address": l.get("full_address") or l.get("address"),
                "icp_status": l["_icp_status"],
                "icp_reasons": l["_icp_reasons"],
            }
            for l in (passed + warned)
        ],
    }

    return result


def _write_to_sheets(leads: list[dict], job_id: str) -> None:
    """Write leads to Google Sheets Master Lead Sheet via gspread."""
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials

    sheets_id = os.environ.get("GOOGLE_SHEETS_ID", "")
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not sheets_id or not sa_json:
        raise RuntimeError("GOOGLE_SHEETS_ID or GOOGLE_SERVICE_ACCOUNT_JSON not set")

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(sa_json, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheets_id).sheet1

    # Append rows
    rows = []
    for l in leads:
        rows.append([
            l.get("name", ""),
            l.get("site", ""),
            l.get("phone", ""),
            l.get("email") or l.get("email_1", ""),
            str(l.get("rating", "")),
            str(l.get("reviews", "")),
            l.get("category") or l.get("type", ""),
            l.get("full_address") or l.get("address", ""),
            l.get("_icp_status", ""),
            "; ".join(l.get("_icp_reasons", [])),
        ])

    if rows:
        sheet.append_rows(rows)
        alog("INFO", f"Wrote {len(rows)} leads to Google Sheets",
             job_id=job_id, channel="lead_gen", step="harvest_sheets")


# ── Workflow B: Ghost Audit ────────────────────────────────────────────

_GHOST_AUDIT_PROMPT = """You are a website auditor for UK service SMEs. Analyse this website content
and identify the primary business leak.

BUSINESS: {business_name}
CATEGORY: {category}
WEBSITE CONTENT (truncated):
---
{content}
---

Assess against these six leak types:
- BOOKING: No online booking, broken booking flow, or booking buried >2 clicks deep
- CONTACT: Contact form missing/broken, no email visible, phone only
- SPEED: Page load >3s, heavy images, poor mobile experience
- TRUST: Few/no reviews shown, no testimonials, no case studies, no credentials
- CONTENT: Outdated content, thin pages, no blog, generic stock photos, broken links
- NONE: No significant leak detected

Return ONLY valid JSON:
{{
  "leak_type": "BOOKING|CONTACT|SPEED|TRUST|CONTENT|NONE",
  "leak_score": 1-10,
  "leak_label": "short plain English description of the specific problem",
  "evidence": ["bullet point 1", "bullet point 2"],
  "recommendation": "one sentence recommendation"
}}"""


async def task_ghost_audit(job_id: str, params: dict, caller: str) -> dict:
    """
    Firecrawl website scraping + Claude Haiku analysis.
    Params: lead_id (str, optional), limit (int, default 5), dry_run (bool, default True)
    """
    limit = params.get("limit", 5)
    dry_run = params.get("dry_run", True)

    # If a specific lead_id is provided, audit just that one
    # Otherwise, fetch recent PASS/WARN leads from the last harvest
    leads_to_audit = params.get("leads", [])
    if not leads_to_audit:
        alog("WARN", "No leads provided for ghost audit — pass leads in params",
             job_id=job_id, channel="lead_gen", step="audit_start")
        return {"audited": 0, "message": "No leads provided. Pass leads array in params."}

    firecrawl_key = os.environ.get("FIRECRAWL_API_KEY", "")
    if not firecrawl_key:
        raise RuntimeError("FIRECRAWL_API_KEY not set. To resolve this: add key to .env")

    update_job(job_id, progress=f"Ghost auditing {min(limit, len(leads_to_audit))} leads...")
    results = []

    for i, lead in enumerate(leads_to_audit[:limit]):
        site = lead.get("site", "")
        name = lead.get("name", lead.get("business_name", "Unknown"))
        category = lead.get("category", lead.get("sector", ""))

        if not site:
            alog("WARN", f"Skipping {name}: no website", job_id=job_id, channel="lead_gen", step="audit_scrape")
            continue

        update_job(job_id, progress=f"Auditing {i+1}/{min(limit, len(leads_to_audit))}: {name}")

        # Scrape with Firecrawl
        try:
            scrape_resp = requests.post(
                "https://api.firecrawl.dev/v1/scrape",
                headers={"Authorization": f"Bearer {firecrawl_key}"},
                json={"url": site, "formats": ["markdown"]},
                timeout=60,
            )
            scrape_resp.raise_for_status()
            scrape_data = scrape_resp.json()
            content = scrape_data.get("data", {}).get("markdown", "")[:4000]  # Truncate for Haiku
        except Exception as e:
            alog("WARN", f"Firecrawl failed for {site}: {e}",
                 job_id=job_id, channel="lead_gen", step="audit_scrape")
            results.append({"name": name, "site": site, "error": str(e)})
            continue

        if not content or len(content) < 50:
            alog("WARN", f"Insufficient content scraped from {site}",
                 job_id=job_id, channel="lead_gen", step="audit_scrape")
            results.append({"name": name, "site": site, "error": "Insufficient content"})
            continue

        # Claude Haiku analysis
        try:
            prompt = _GHOST_AUDIT_PROMPT.format(
                business_name=name, category=category, content=content
            )
            audit = await call_claude_json(
                prompt,
                system="You are a website auditor. Return valid JSON only.",
                job_id=job_id, step="audit_claude",
            )
        except Exception as e:
            alog("ERROR", f"Claude audit failed for {name}: {e}. To resolve this: check API key",
                 job_id=job_id, channel="lead_gen", step="audit_claude")
            results.append({"name": name, "site": site, "error": str(e)})
            continue

        # Add liability context
        lead_with_audit = {**lead, **audit}
        liability = get_liability_context(lead_with_audit)

        audit_result = {
            "name": name,
            "site": site,
            "category": category,
            "leak_type": audit.get("leak_type", "NONE"),
            "leak_score": audit.get("leak_score", 0),
            "leak_label": audit.get("leak_label", ""),
            "evidence": audit.get("evidence", []),
            "recommendation": audit.get("recommendation", ""),
            "liability_context": liability,
        }
        results.append(audit_result)

        alog("INFO",
             f"Audited {name}: {audit_result['leak_type']} (score {audit_result['leak_score']})",
             job_id=job_id, channel="lead_gen", step="audit_complete")

    return {
        "audited": len([r for r in results if "error" not in r]),
        "errors": len([r for r in results if "error" in r]),
        "results": results,
    }
