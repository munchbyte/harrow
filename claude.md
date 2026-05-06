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
- Smoke test: python -m scripts.smoke_test_push_client

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
