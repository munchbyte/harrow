# HARROW — API Routes Reference

Base URL: `https://harrow.attic-tech.co.uk`
Auth: `X-API-Key` header or `harrow_token` session cookie on all endpoints except `/health` and `/auth`.

All responses follow the ASP-002 standard envelope:
```json
{
  "status": "ok|error",
  "agent_id": "harrow",
  "timestamp": "2026-03-22T10:00:00Z",
  "data": { ... }
}
```

---

## ASP-002 Standard Endpoints

### GET /health
Agent alive check. No auth required.
```bash
curl https://harrow.attic-tech.co.uk/health
```
Response: `{ status, agent_id, timestamp, data: { version, uptime_seconds } }`

### GET /info
Full agent description.
```bash
curl -H "X-API-Key: $KEY" https://harrow.attic-tech.co.uk/info
```
Response: `{ data: { agent_id, name, description, version, capabilities, tasks } }`

### POST /run
Execute a task. Creates a job. Returns immediately with job_id.
```bash
curl -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"task": "run_lead_harvest", "params": {"query": "restaurants in Llanelli", "limit": 20, "dry_run": true}, "caller": "adrian"}' \
  https://harrow.attic-tech.co.uk/run
```
Response: `{ data: { job_id, task, status: "running" } }`

**Available tasks:**
| Task | Params | Channel |
|------|--------|---------|
| run_lead_harvest | query, limit, dry_run | lead_gen |
| run_ghost_audit | limit, lead_id, dry_run | lead_gen |
| run_copy_review | copy_text | email |
| run_voice_brief | business_name, leak_type, leak_label, script_type | voice |
| run_social_brief | platform, content_type, topic, sector | social |
| run_ads_brief | platform, campaign_type, objective, budget_gbp | ads |
| run_channel_report | (none) | all |
| run_campaign | sector, location, limit, tone, dry_run | all |

### GET /status/{job_id}
Check a running or completed job.
```bash
curl -H "X-API-Key: $KEY" https://harrow.attic-tech.co.uk/status/{job_id}
```
Response: `{ data: { job_id, task, status, progress, result, channel } }`

### GET /logs
Activity log with filters.
```bash
curl -H "X-API-Key: $KEY" "https://harrow.attic-tech.co.uk/logs?channel=email&level=ERROR&limit=50"
```
Response: `{ data: { entries: [...] } }`

### POST /stop/{job_id}
Gracefully stop a running job.
```bash
curl -X POST -H "X-API-Key: $KEY" https://harrow.attic-tech.co.uk/stop/{job_id}
```
Response: `{ data: { job_id, status: "failed", message: "Stopped by user" } }`

---

## GO Gate Endpoints

### POST /go/{channel}
Arm a channel. Channels: email, voice, social, ads.
```bash
curl -X POST -H "X-API-Key: $KEY" https://harrow.attic-tech.co.uk/go/email
```
Response: `{ data: { channel: "email", armed: true, armed_at: "..." } }`

### POST /revoke/{channel}
Disarm a channel immediately.
```bash
curl -X POST -H "X-API-Key: $KEY" https://harrow.attic-tech.co.uk/revoke/email
```
Response: `{ data: { channel: "email", armed: false } }`

### GET /go-status
Return all four channel GO states.
```bash
curl -H "X-API-Key: $KEY" https://harrow.attic-tech.co.uk/go-status
```
Response: `{ data: { email: { armed: true, armed_at: "..." }, voice: {...}, social: {...}, ads: {...} } }`

---

## HITL Gate Endpoints

### GET /gates
List HITL gates. Default: pending only.
```bash
curl -H "X-API-Key: $KEY" "https://harrow.attic-tech.co.uk/gates?status=pending"
```
Response: `{ data: { gates: [...] } }`

### POST /gates/{id}/resolve
Approve a HITL gate. Job resumes.
```bash
curl -X POST -H "X-API-Key: $KEY" https://harrow.attic-tech.co.uk/gates/1/resolve
```
Response: `{ data: { id: 1, status: "resolved", resolved_by: "adrian" } }`

### GET /approve/{token}
One-Touch Receipt signed URL approval. No auth header required (HMAC in token).
```bash
curl https://harrow.attic-tech.co.uk/approve/{signed_token}
```
Redirects to dashboard on success. Returns 403 if token expired or invalid.

---

## Auth Endpoint

### POST /auth
Validate API key. Set session cookie.
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"token": "your-api-key"}' \
  https://harrow.attic-tech.co.uk/auth
```
Response: `{ data: { authenticated: true } }` + `Set-Cookie: harrow_token=...`

---

## Dashboard

### GET /
Serve the Control Centre dashboard (index.html via Jinja2). Requires auth cookie.

---

## Settings Endpoints

### POST /settings/key/test
Test an API key against its target service.
```bash
curl -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"key_name": "OUTSCRAPER_API_KEY"}' \
  https://harrow.attic-tech.co.uk/settings/key/test
```
Response: `{ data: { key_name: "OUTSCRAPER_API_KEY", result: "PASS|FAIL", detail: "..." } }`

### POST /settings/key/update
Update an API key in .env. Triggers graceful restart.
```bash
curl -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"key_name": "OUTSCRAPER_API_KEY", "value": "new-key-value"}' \
  https://harrow.attic-tech.co.uk/settings/key/update
```
Response: `{ data: { key_name: "OUTSCRAPER_API_KEY", updated: true } }`

### GET /settings/channel/{channel}
Return current config for a channel.
```bash
curl -H "X-API-Key: $KEY" https://harrow.attic-tech.co.uk/settings/channel/email
```
Response: `{ data: { send_window_start: "08:00", send_window_end: "17:00", m2_delay_days: 5, ... } }`

### POST /settings/channel/{channel}
Update channel config.
```bash
curl -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"m2_delay_days": 7}' \
  https://harrow.attic-tech.co.uk/settings/channel/email
```
Response: `{ data: { channel: "email", updated_keys: ["m2_delay_days"] } }`

### GET /settings/agent-info
Return version, uptime, capabilities, registry SQL.
```bash
curl -H "X-API-Key: $KEY" https://harrow.attic-tech.co.uk/settings/agent-info
```
Response: `{ data: { version, uptime, port, capabilities, registry_sql } }`

---

## SSE Streaming

### GET /stream/{job_id}
Server-Sent Events stream for live terminal output during long-running tasks.
```bash
curl -H "X-API-Key: $KEY" -N https://harrow.attic-tech.co.uk/stream/{job_id}
```
Returns `text/event-stream` with `data: { line, timestamp }` events.
