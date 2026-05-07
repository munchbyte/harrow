# HARROW — The Resonant CMO

## What This App Does
HARROW is the CMO agent for Goblin Media Network / Attic Tech Solutions.
Sovereign FastAPI service, port 8001. Five channels: lead gen, email, voice, social, ads.
Control Centre at harrow.goblinmedia.net. 7-stage Campaign Builder.
Voss copy techniques. v3.4 enhancements: Liability Predictor, 3-Failure Gate,
Log-Sync Auto, One-Touch Receipt.
GMN Marketing Rules Charter v2.0. ASP-001/002/003 compliant.

## Tech Stack
Python 3.11, FastAPI, Uvicorn, SQLite, Anthropic API (Haiku+Sonnet), Vanilla JS/Jinja2
gspread, ntfy.sh, Nginx, systemd, Certbot
Hosting: Hostinger VPS. VCS: GitHub (main=prod, dev=staging)

## Folder Structure
core/        db, auth, jobs, logging, hitl, go_state, log_sync, sub_agents
channels/    lead_gen, email, voice, social, ads
engine/      claude_client, voss, five_gate, liability, friction_filter
campaign/    builder, scheduler, copy_variants
notifications/ ntfy
integrations/ push_client
routes/      asp002, go_gates, hitl_routes, dashboard, settings
scripts/     smoke_test_push_client
templates/   index.html
state/       harrow.db

## Sub-agents

### Push CMS — Tier 3 (LIVE since 2026-05-01)
- URL (internal, used for HARROW->Push): http://localhost:8004
- URL (public, reference only): https://push.goblinmedia.net
- Auth: X-API-Key header, value in env PUSH_CMS_API_KEY
- Client module: integrations/push_client.py
- Registry entry: core/sub_agents.py SUB_AGENTS["push_cms"]
- Primary task HARROW dispatches: publish_content_brief
- All HARROW-dispatchable tasks: publish_content_brief, run_draft, run_carousel_brief, run_metrics_sync, run_archive
- Push runs its own cron for: scheduler, metrics sync, weekly improvement brief, token check, db backup, scout cycle
- HARROW's /health probes Push /health non-blocking — Push being down does NOT make HARROW unhealthy (ASP-001).
- Smoke test: python3 -m scripts.smoke_test_push_client

### Interact CRM — Tier 3 (LIVE since 2026-05-06)
- URL (used for HARROW->Interact): http://100.109.24.65:8003
  Same VPS as HARROW, but Interact binds to its tailscale0 interface only —
  NOT 0.0.0.0, NOT 127.0.0.1. Localhost will not work even from the same machine.
- Auth: X-API-Key header REQUIRED on every endpoint including /health
  (deviation from ASP-002 §4.1, accepted per ASP-001). Value in env INTERACT_API_KEY.
- Client module: integrations/interact_client.py
- Registry entry: core/sub_agents.py SUB_AGENTS["interact_crm"]
- Primary task HARROW dispatches: log_interaction
- All HARROW-dispatchable [HARROW-CRM] signal tasks: reply_received, advance_stage, log_interaction
- Named wrappers (use these from calling code, not raw dispatch()):
    send_reply_received(lead_id, contact_email, reply_text, stage)
    send_advance_stage(lead_id, new_stage, trigger, channel)
    send_log_interaction(lead_id, interaction_type, template, sent_at)
- HARROW's /health probes Interact /health non-blocking — Interact being down does NOT make HARROW unhealthy (ASP-001).
- Discovery + smoke test: python3 -m scripts.smoke_test_interact_client
  For end-to-end proof of dispatch, re-run with `--dispatch=pipeline_health` (read-only
  if exposed) or `--dispatch=retry_audit_pushes` (no-op while Avery is offline).
  Do NOT smoke-test with reply_received or advance_stage — those write real records
  and can fire HITL gates.

## Environment Variables
HARROW_API_KEY, ANTHROPIC_API_KEY, OUTSCRAPER_API_KEY
FIRECRAWL_API_KEY, GOOGLE_SHEETS_ID, GOOGLE_SERVICE_ACCOUNT_JSON
VAPI_API_KEY, PUSH_CMS_AGENT_URL, PUSH_CMS_API_KEY
INTERACT_AGENT_URL, INTERACT_API_KEY
NTFY_TOPIC, NTFY_SECRET

## Database
SQLite. state/harrow.db. Auto-created by core/db.py init_db().
Tables: jobs, agent_logs, go_state, hitl_gates, campaigns, campaign_steps,
copy_outputs, rejection_log, memory_log, settings

## Auth
X-API-Key header OR harrow_token cookie via core/auth.py require_key().
Only /health and /auth are unauthenticated. Single user (Adrian).

## Deployment
Hostinger VPS, /var/www/harrow/, port 8001.
systemd harrow-agent, Nginx proxy, Certbot SSL.
harrow.goblinmedia.net. Tailscale restricted.
main=production, dev=staging. Never deploy from dev without GO.

## Coding Conventions
- Python 3.11. Type hints on all functions.
- Async for all tasks. asyncio.create_task for background jobs.
- All logs via core/logging.py alog(). Never print().
- Every external call: try/except, ASP-003 stop-log-alert.
- One timeout retry only. No retry on 4xx/5xx.
- HITL gates: core/hitl.py fire_hitl(). Never inline.
- Sovereignty Footer: engine/five_gate.py append_sovereignty_footer(). Always.
- Log-Sync: core/log_sync.py write_memory_log() after sends.
- DB: core/db.py get_db() only. No raw sqlite3 elsewhere.

## What Claude Should Never Do
- Never write secrets into code, logs, or DB
- Never bypass fire_hitl() for any irreversible action
- Never omit the Sovereignty Footer from any copy output
- Never send, publish, or spend without checking GO flag
- Never deploy to main during a build session
- Never catch exceptions silently — always log + alert
- Never skip friction_filter.validate_run_request() on /run
