# HARROW Changelog

## 2026-05-07 — BUG-006 closed: HARROW → Interact CRM signal handler
- integrations/interact_client.py: switched `health()` and `info()` to `auth=True` (Interact v2.0-dev requires X-API-Key on every endpoint, including /health — deviation from ASP-002 §4.1 accepted per ASP-001).
- integrations/interact_client.py: dropped the assumed caller enum (`INTERACT_CALLER_VALUES`); Interact's RunRequest schema accepts any caller string. Convention `caller='harrow'` retained as default.
- integrations/interact_client.py: added three named [HARROW-CRM] signal wrappers — `send_reply_received(lead_id, contact_email, reply_text, stage)`, `send_advance_stage(lead_id, new_stage, trigger, channel)`, `send_log_interaction(lead_id, interaction_type, template, sent_at)`.
- core/sub_agents.py: promoted `interact_crm` from `status='wiring'` → `status='live'` (live_since 2026-05-06); populated `tasks=[reply_received, advance_stage, log_interaction]`; `primary_task='log_interaction'`. Interact now appears in HARROW's `/health` sub_agents block.
- .env.example: changed `INTERACT_AGENT_URL=http://localhost:8003` → `http://100.109.24.65:8003` with comment explaining Interact binds to the Tailscale interface only (uvicorn listens on `100.109.24.65:8003`, not loopback).
- Unreachable error messages updated to point at the Tailscale URL gotcha.
- No Interact CRM code touched (ASP-001 sovereignty preserved).
- Smoke-test guidance: run `python3 -m scripts.smoke_test_interact_client --dispatch=pipeline_health` from the VPS after `set -a; source .env; set +a`. Avoid `reply_received` and `advance_stage` for smoke — those write real records and can fire HITL gates.

## v1.0.0 — 2026-03-22
### Phase 5: Dashboard + Settings + Channel Report
- Control Centre dashboard (templates/index.html) — login, GO states, HITL gates, task runner, SSE terminal, activity log
- routes/dashboard.py — GET / (Jinja2), GET /stream/{id} (SSE)
- routes/settings.py — key test/update, channel config CRUD, agent-info
- channels/report.py — cross-channel status report task
- 8 tasks registered, all endpoints live

### Phase 4: Voice, Social, Ads, Friction Filter, One-Touch Receipt
- channels/voice.py — Vapi voice brief generation, outbound HITL gate
- channels/social.py — PAC-Receipt Loop social brief, HITL gate, Push CMS routing
- channels/ads.py — Ad campaign brief, budget ceiling, HITL gate always
- engine/friction_filter.py — validate_run_request() wired into /run
- notifications/ntfy.py — HMAC-signed One-Touch Receipt, GET /approve/{token}

### Phase 3: Campaign Builder + Scheduler + Copy Variants
- campaign/builder.py — 7-stage CampaignBuilder orchestrator
- campaign/scheduler.py — autonomous follow-up scheduler (M2/M3 at 5-day intervals)
- campaign/copy_variants.py — 5 leak-type prompt templates + DEFAULT
- core/log_sync.py — memory_log append-only with [HARROW->LOG_SYNC] signal

### Phase 2: Claude Client + Lead Gen + Email + Five-Gate + Voss + Liability
- engine/claude_client.py — Anthropic SDK wrapper (Haiku + Sonnet)
- engine/liability.py — 25-niche failure dataset
- engine/voss.py — Accusation Audit, Label, No-Oriented Close + VC1/VC2 checks
- engine/five_gate.py — G1-G5 Claude analysis + Sovereignty Footer
- channels/lead_gen.py — Outscraper harvest + ICP filter + Firecrawl Ghost Audit
- channels/email.py — M1/M2/M3 generation + Five-Gate + anti-hype filter

### Phase 1: Data Layer + ASP-002 Endpoints
- core/db.py — 10 SQLite tables, WAL mode, context manager
- core/auth.py — require_key() (header + cookie + dev mode)
- core/logging.py — alog() structured logging
- core/jobs.py — job CRUD
- core/go_state.py — per-channel GO flags
- core/hitl.py — HITL gates + 3-Failure Gate tracking
- routes/asp002.py — /info, /run, /status, /logs, /stop, /auth
- routes/go_gates.py — /go, /revoke, /go-status
- routes/hitl_routes.py — /gates, /gates/{id}/resolve

## v0.0.1 — 2026-03-22
### Phase 0: Project Foundation
- Project scaffolded: full folder structure created
- claude.md written — Claude Code reads this first every session
- HARROW.md written — CMO system prompt with Charter, Voss, and Hard Locks
- SCHEMA.md written — all 10 SQLite tables defined with CREATE TABLE SQL
- ROUTES.md written — all ASP-002 endpoints documented with example curl
- DEPLOYMENT.md written — full VPS deployment guide
- .env.example with all 11 environment variables
- requirements.txt with all Python dependencies
- systemd unit file (harrow_agent.service)
- Nginx reverse proxy config with SSE support
- registry_entry.sql for AIOS agent_registry
- All module files scaffolded with docstrings (no business logic)
- harrow_agent.py entry point — imports only, returns scaffold message
