"""
scripts/smoke_test_push_client.py — End-to-end smoke test for Push CMS client.

Runs the six ASP-002 endpoints HARROW exposes against Push:
    1. health()                             — liveness check
    2. info()                               — identity check
    3. dispatch('run_db_backup')            — idempotent low-impact dispatch
    4. status(job_id) (polled up to 30s)    — wait for completion
    5. logs() (sanity probe)
    6. summary

Why run_db_backup? It's idempotent and verifiable. NEVER use
publish_content_brief here — that publishes real content.

Prereq: PUSH_CMS_AGENT_URL and PUSH_CMS_API_KEY set in the environment.

Run from repo root:
    python -m scripts.smoke_test_push_client
"""

import asyncio
import os
import sys
import time
from pathlib import Path

# Make 'integrations' importable when run as a module from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from integrations import push_client


CALLER = "harrow"            # Push enforces enum {human, harrow, avery, monitor}
CALLER_LABEL = "harrow_smoke"  # free-form trace tag — appears in Push's logs
POLL_TIMEOUT_SECONDS = 30
POLL_INTERVAL_SECONDS = 2


def _check_env() -> tuple[bool, str]:
    url = os.environ.get("PUSH_CMS_AGENT_URL") or os.environ.get("PUSH_CMS_URL", "")
    key = os.environ.get("PUSH_CMS_API_KEY", "")
    if not url:
        return False, "PUSH_CMS_AGENT_URL is not set"
    if not key:
        return False, "PUSH_CMS_API_KEY is not set"
    return True, f"target={url}"


_HEALTHY = {"ok", "online", "healthy", "ready", "running"}


async def _step_health() -> bool:
    print("[1/5] GET /health ...")
    try:
        result = await push_client.health()
    except Exception as e:
        print(f"      FAIL: {e}")
        return False
    status_value = str(result.get("status") or result.get("data", {}).get("status") or "").lower()
    if status_value not in _HEALTHY:
        print(f"      FAIL: status field is '{status_value}', expected one of {_HEALTHY}. Body: {result}")
        return False
    print(f"      PASS (status={status_value})")
    return True


async def _step_info() -> bool:
    print("[2/5] GET /info ...")
    try:
        result = await push_client.info()
    except Exception as e:
        print(f"      FAIL: {e}")
        return False
    blob = str(result).lower()
    if "push" not in blob:
        print(f"      FAIL: response does not mention 'push'. Body: {result}")
        return False
    print("      PASS")
    return True


async def _step_dispatch() -> tuple[bool, str]:
    print(f"[3/5] POST /run task=run_db_backup caller={CALLER} caller_label={CALLER_LABEL} ...")
    try:
        result = await push_client.dispatch(
            "run_db_backup", {}, caller=CALLER, caller_label=CALLER_LABEL,
        )
    except push_client.PushClientError as e:
        # Print the body so we can see exactly what Push rejected.
        print(f"      FAIL: {e}")
        if e.body:
            print(f"      response body: {e.body}")
        return False, ""
    except Exception as e:
        print(f"      FAIL: {type(e).__name__}: {e}")
        return False, ""
    data = result.get("data", result) if isinstance(result, dict) else {}
    job_id = data.get("job_id") if isinstance(data, dict) else None
    if not job_id:
        print(f"      FAIL: no job_id in response. Body: {result}")
        return False, ""
    print(f"      PASS (push_job_id={job_id})")
    return True, job_id


async def _step_poll_status(push_job_id: str) -> bool:
    print(f"[4/5] GET /status/{push_job_id} (poll up to {POLL_TIMEOUT_SECONDS}s) ...")
    deadline = time.time() + POLL_TIMEOUT_SECONDS
    last_status = None
    while time.time() < deadline:
        try:
            result = await push_client.status(push_job_id)
        except Exception as e:
            print(f"      FAIL: poll error: {e}")
            return False
        data = result.get("data", result) if isinstance(result, dict) else {}
        job_status = data.get("status") if isinstance(data, dict) else None
        if job_status != last_status:
            print(f"      ... status={job_status}")
            last_status = job_status
        if job_status in ("success", "complete", "done"):
            print(f"      PASS (final status={job_status})")
            return True
        if job_status in ("failed", "error", "stopped"):
            print(f"      FAIL: job ended with status={job_status}. Body: {result}")
            return False
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
    print(f"      FAIL: status did not reach success within {POLL_TIMEOUT_SECONDS}s (last={last_status})")
    return False


async def _step_logs() -> bool:
    print("[5/5] GET /logs?limit=5 ...")
    try:
        entries = await push_client.logs(limit=5)
    except Exception as e:
        print(f"      FAIL: {e}")
        return False
    print(f"      PASS ({len(entries)} entries returned)")
    return True


async def main() -> int:
    print("=" * 60)
    print("HARROW -> Push CMS smoke test")
    print("=" * 60)

    ok, msg = _check_env()
    print(f"env: {msg}")
    if not ok:
        print("ABORT: missing required env. Set PUSH_CMS_AGENT_URL and PUSH_CMS_API_KEY.")
        return 2

    results = {}
    results["health"] = await _step_health()
    results["info"] = await _step_info()
    dispatched, push_job_id = await _step_dispatch()
    results["dispatch"] = dispatched
    results["status"] = await _step_poll_status(push_job_id) if dispatched else False
    results["logs"] = await _step_logs()

    print()
    print("-" * 60)
    print("SUMMARY")
    print("-" * 60)
    for step, ok in results.items():
        marker = "PASS" if ok else "FAIL"
        print(f"  {marker:<5}  {step}")
    all_pass = all(results.values())
    print("-" * 60)
    print("RESULT: " + ("ALL PASS" if all_pass else "FAILURES PRESENT"))
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
