# HARROW — SQLite Schema

Database: `state/harrow.db` — auto-created by `core/db.py init_db()`.

---

## jobs
Every `/run` call creates one row. Tracks task execution from start to finish.

| Column | Type | Notes |
|--------|------|-------|
| job_id | TEXT PRIMARY KEY | UUID generated on creation |
| task | TEXT NOT NULL | Task name (e.g. run_lead_harvest) |
| caller | TEXT NOT NULL | Who triggered it (adrian, avery, dashboard) |
| status | TEXT NOT NULL DEFAULT 'running' | running / complete / failed |
| channel | TEXT | lead_gen / email / voice / social / ads |
| progress | TEXT | Free-text progress update |
| result | TEXT | JSON string — task output |
| error | TEXT | Error message if failed |
| created_at | TEXT NOT NULL | ISO timestamp |
| updated_at | TEXT | ISO timestamp — last status change |

```sql
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    task TEXT NOT NULL,
    caller TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    channel TEXT,
    progress TEXT,
    result TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT
);
```

---

## agent_logs
ASP-003 structured log. Every agent action, gate, error, and milestone is logged here.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | |
| timestamp | TEXT NOT NULL | ISO timestamp |
| level | TEXT NOT NULL | INFO / WARN / ERROR / GATE |
| agent_id | TEXT NOT NULL DEFAULT 'harrow' | |
| job_id | TEXT | FK to jobs — nullable for system events |
| caller | TEXT | Who triggered the action |
| step | TEXT | Named step within task |
| message | TEXT NOT NULL | Plain English log message |
| action | TEXT | What was done |
| outcome | TEXT | Result of the action |
| channel | TEXT | lead_gen / email / voice / social / ads |

```sql
CREATE TABLE IF NOT EXISTS agent_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    level TEXT NOT NULL,
    agent_id TEXT NOT NULL DEFAULT 'harrow',
    job_id TEXT,
    caller TEXT,
    step TEXT,
    message TEXT NOT NULL,
    action TEXT,
    outcome TEXT,
    channel TEXT
);
```

---

## go_state
Per-channel GO flag. Four rows — one per outbound channel. Email, voice, social, ads.

| Column | Type | Notes |
|--------|------|-------|
| channel | TEXT PRIMARY KEY | email / voice / social / ads |
| armed | INTEGER NOT NULL DEFAULT 0 | 0 = revoked, 1 = armed |
| armed_at | TEXT | ISO timestamp — when last armed |
| armed_by | TEXT | Who armed it |

```sql
CREATE TABLE IF NOT EXISTS go_state (
    channel TEXT PRIMARY KEY,
    armed INTEGER NOT NULL DEFAULT 0,
    armed_at TEXT,
    armed_by TEXT
);
```

---

## hitl_gates
HITL gate queue. Every irreversible action fires a gate. Gate must be resolved before job continues.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | |
| job_id | TEXT | FK to jobs |
| channel | TEXT | Which channel triggered it |
| trigger | TEXT NOT NULL | What fired the gate |
| context | TEXT | JSON — lead, brief summary, etc. |
| recommended | TEXT | What HARROW recommends |
| status | TEXT NOT NULL DEFAULT 'pending' | pending / resolved |
| created_at | TEXT NOT NULL | ISO timestamp |
| resolved_at | TEXT | ISO timestamp |
| resolved_by | TEXT | adrian / one_touch_receipt / avery |

```sql
CREATE TABLE IF NOT EXISTS hitl_gates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT,
    channel TEXT,
    trigger TEXT NOT NULL,
    context TEXT,
    recommended TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    resolved_by TEXT
);
```

---

## campaigns
Campaign Builder sessions. One row per campaign run.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | |
| name | TEXT NOT NULL | Campaign name |
| sector | TEXT NOT NULL | Target sector |
| location | TEXT NOT NULL | Target location |
| tone | TEXT NOT NULL DEFAULT 'dj' | dj / formal / concise |
| status | TEXT NOT NULL DEFAULT 'running' | running / awaiting_review / approved / complete / failed |
| created_at | TEXT NOT NULL | ISO timestamp |
| completed_at | TEXT | ISO timestamp |

```sql
CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    sector TEXT NOT NULL,
    location TEXT NOT NULL,
    tone TEXT NOT NULL DEFAULT 'dj',
    status TEXT NOT NULL DEFAULT 'running',
    created_at TEXT NOT NULL,
    completed_at TEXT
);
```

---

## campaign_steps
Per-step progress within a campaign. 7 rows per campaign (one per stage).

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | |
| campaign_id | INTEGER NOT NULL | FK to campaigns |
| step_num | INTEGER NOT NULL | 1-7 |
| step_name | TEXT NOT NULL | define / harvest / audit / segment / generate / review / go |
| status | TEXT NOT NULL DEFAULT 'pending' | pending / running / complete / failed |
| result | TEXT | JSON — step output |
| started_at | TEXT | ISO timestamp |
| completed_at | TEXT | ISO timestamp |

```sql
CREATE TABLE IF NOT EXISTS campaign_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    step_num INTEGER NOT NULL,
    step_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    result TEXT,
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
);
```

---

## copy_outputs
Generated copy per leak type per campaign. M1/M2/M3 with gate and Voss results.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | |
| campaign_id | INTEGER NOT NULL | FK to campaigns |
| leak_type | TEXT NOT NULL | BOOKING / CONTACT / SPEED / TRUST / CONTENT |
| m1 | TEXT | M1 cold open copy |
| m2 | TEXT | M2 follow-up copy |
| m3 | TEXT | M3 soft close copy |
| gate_results | TEXT | JSON — Five-Gate PASS/FAIL per message |
| voss_results | TEXT | JSON — VC1/VC2 per message |
| approved | INTEGER NOT NULL DEFAULT 0 | 0 = pending, 1 = approved |
| created_at | TEXT NOT NULL | ISO timestamp |

```sql
CREATE TABLE IF NOT EXISTS copy_outputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    leak_type TEXT NOT NULL,
    m1 TEXT,
    m2 TEXT,
    m3 TEXT,
    gate_results TEXT,
    voss_results TEXT,
    approved INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
);
```

---

## rejection_log
3-Failure Gate tracker. Counts rejections per output type.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | |
| output_type | TEXT NOT NULL | e.g. BOOKING_copy, voice_brief, linkedin_post |
| job_id | TEXT | FK to jobs — which job was rejected |
| rejected_at | TEXT NOT NULL | ISO timestamp |
| failure_count | INTEGER NOT NULL DEFAULT 1 | Running count for this output_type |

```sql
CREATE TABLE IF NOT EXISTS rejection_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    output_type TEXT NOT NULL,
    job_id TEXT,
    rejected_at TEXT NOT NULL,
    failure_count INTEGER NOT NULL DEFAULT 1
);
```

---

## memory_log
Shared Memory Log — Log-Sync Auto target. Append-only. No updates. No deletes.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | |
| event_type | TEXT NOT NULL | m1_sent / m2_sent / m3_sent / gate_resolved / opt_out / stage_advance |
| job_id | TEXT | FK to jobs |
| lead_id | TEXT | Lead identifier |
| channel | TEXT | Which channel |
| detail | TEXT | JSON — full context |
| logged_at | TEXT NOT NULL | ISO timestamp |

```sql
CREATE TABLE IF NOT EXISTS memory_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    job_id TEXT,
    lead_id TEXT,
    channel TEXT,
    detail TEXT,
    logged_at TEXT NOT NULL
);
```

---

## settings
Channel configuration overrides. Key-value with channel scoping.

| Column | Type | Notes |
|--------|------|-------|
| key | TEXT NOT NULL | Setting name (e.g. send_window_start, m2_delay_days) |
| value | TEXT NOT NULL | Setting value |
| channel | TEXT | Channel scope — nullable for global settings |
| updated_at | TEXT NOT NULL | ISO timestamp |

Primary key: (key, channel)

```sql
CREATE TABLE IF NOT EXISTS settings (
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    channel TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (key, channel)
);
```
