# HARROW Changelog

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
