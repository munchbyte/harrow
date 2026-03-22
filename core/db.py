"""
core/db.py — HARROW database layer.

This is the ONLY place for sqlite3 calls. All other files import from here.
Database: state/harrow.db — auto-created on first run.

Tables: jobs, agent_logs, go_state, hitl_gates, campaigns, campaign_steps,
        copy_outputs, rejection_log, memory_log, settings
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent.parent / "state" / "harrow.db"

_CREATE_TABLES = """
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

CREATE TABLE IF NOT EXISTS go_state (
    channel TEXT PRIMARY KEY,
    armed INTEGER NOT NULL DEFAULT 0,
    armed_at TEXT,
    armed_by TEXT
);

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

CREATE TABLE IF NOT EXISTS rejection_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    output_type TEXT NOT NULL,
    job_id TEXT,
    rejected_at TEXT NOT NULL,
    failure_count INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS memory_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    job_id TEXT,
    lead_id TEXT,
    channel TEXT,
    detail TEXT,
    logged_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    channel TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (key, channel)
);
"""

_SEED_GO_STATE = """
INSERT OR IGNORE INTO go_state (channel, armed) VALUES ('email', 0);
INSERT OR IGNORE INTO go_state (channel, armed) VALUES ('voice', 0);
INSERT OR IGNORE INTO go_state (channel, armed) VALUES ('social', 0);
INSERT OR IGNORE INTO go_state (channel, armed) VALUES ('ads', 0);
"""


def init_db() -> None:
    """Create database file and all tables. Safe to call repeatedly."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript(_CREATE_TABLES)
    conn.executescript(_SEED_GO_STATE)
    conn.commit()
    conn.close()


@contextmanager
def get_db():
    """Yield a sqlite3 connection with row_factory=Row. Auto-commits on exit."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
