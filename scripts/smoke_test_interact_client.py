"""
scripts/smoke_test_interact_client.py — Interact CRM discovery + smoke test.

Discovery-first design (lesson from BUG-005): we don't yet know Interact's
exact contract — task names, caller enum, terminal status terms. This script
prints what Interact actually exposes so we can complete the wiring.

Phases:
  A. Discovery (always runs, read-only)
     1. health()                  — confirm liveness + show actual status string
     2. info()                    — print full identity blob (capabilities, etc.)
     3. /openapi.json (raw curl)  — print the /run schema if available
     4. logs(limit=5)             — confirm log endpoint is reachable

  B. Dispatch + status (opt-in via --dispatch=<task_name>)
     5. dispatch(task)            — only if the operator named a safe, idempotent task
     6. status() polled to terminal

Prereq: INTERACT_AGENT_URL and INTERACT_API_KEY set in the environment.

Run from repo root:
    python3 -m scripts.smoke_test_interact_client                     # discovery only
    python3 -m scripts.smoke_test_interact_client --dispatch=run_ping # also dispatch
"""

import argparse
import asyncio
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from integrations import interact_client


CALLER = "harrow"
CALLER_LABEL = "harrow_smoke"
POLL_TIMEOUT_SECONDS = 30
POLL_INTERVAL_SECONDS = 2

_HEALTHY = {"ok", "online", "healthy", "ready", "running"}
_TERMINAL_OK = {"success", "succeeded", "complete", "completed", "done", "finished"}
_TERMINAL_FAIL = {"failed", "failure", "error", "errored", "stopped", "cancelled", "canceled"}


def _check_env() -> tuple[bool, str]:
    url = os.environ.get("INTERACT_AGENT_URL", "")
    key = os.environ.get("INTERACT_API_KEY", "")
    if not url:
        return False, "INTERACT_AGENT_URL is not set"
    if not key:
        return False, "INTERACT_API_KEY is not set"
    return True, f"target={url}"


async def _step_health() -> bool:
    print("[1] GET /health ...")
    try:
        result = await interact_client.health()
    except Exception as e:
        print(f"    FAIL: {e}")
        return False
    status_value = str(result.get("status") or result.get("data", {}).get("status") or "").lower()
    if status_value not in _HEALTHY:
        print(f"    FAIL: status is '{status_value}', expected one of {_HEALTHY}")
        print(f"    Body: {json.dumps(result, indent=2, default=str)}")
        return False
    print(f"    PASS (status={status_value})")
    return True


async def _step_info() -> dict:
    print("[2] GET /info ...")
    try:
        result = await interact_client.info()
    except Exception as e:
        print(f"    FAIL: {e}")
        return {}
    print(f"    PASS — full /info body below:")
    print("    " + "-" * 56)
    for line in json.dumps(result, indent=2, default=str).splitlines():
        print(f"    {line}")
    print("    " + "-" * 56)
    return result


def _step_openapi() -> dict:
    """Fetch /openapi.json directly via urllib so we don't need any extra deps."""
    print("[3] GET /openapi.json (POST /run schema) ...")
    base = os.environ.get("INTERACT_AGENT_URL", "").rstrip("/")
    if not base:
        print("    SKIP — no INTERACT_AGENT_URL")
        return {}
    try:
        with urllib.request.urlopen(f"{base}/openapi.json", timeout=5) as resp:
            spec = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"    SKIP — {e}")
        return {}

    run_path = spec.get("paths", {}).get("/run", {})
    schemas = spec.get("components", {}).get("schemas", {})

    if not run_path and not schemas:
        print("    /openapi.json reachable but contains no /run path")
        return spec

    print("    /run path:")
    for line in json.dumps(run_path, indent=2, default=str).splitlines():
        print(f"      {line}")

    for name, schema in schemas.items():
        if "run" in name.lower() or "request" in name.lower():
            print(f"    schema {name}:")
            for line in json.dumps(schema, indent=2, default=str).splitlines():
                print(f"      {line}")
    return spec


async def _step_logs() -> bool:
    print("[4] GET /logs?limit=5 ...")
    try:
        entries = await interact_client.logs(limit=5)
    except Exception as e:
        print(f"    FAIL: {e}")
        return False
    print(f"    PASS ({len(entries)} entries returned)")
    return True


async def _step_dispatch_and_poll(task: str) -> bool:
    print(f"[5] POST /run task={task} caller={CALLER} caller_label={CALLER_LABEL} ...")
    try:
        result = await interact_client.dispatch(
            task, {}, caller=CALLER, caller_label=CALLER_LABEL,
        )
    except interact_client.InteractClientError as e:
        print(f"    FAIL: {e}")
        if e.body:
            print(f"    response body: {e.body}")
        return False
    except Exception as e:
        print(f"    FAIL: {type(e).__name__}: {e}")
        return False

    data = result.get("data", result) if isinstance(result, dict) else {}
    interact_job_id = data.get("job_id") if isinstance(data, dict) else None
    if not interact_job_id:
        print(f"    FAIL: no job_id in response. Body: {result}")
        return False
    print(f"    PASS (interact_job_id={interact_job_id})")

    print(f"[6] GET /status/{interact_job_id} (poll up to {POLL_TIMEOUT_SECONDS}s) ...")
    deadline = time.time() + POLL_TIMEOUT_SECONDS
    last_status = None
    while time.time() < deadline:
        try:
            poll = await interact_client.status(interact_job_id)
        except Exception as e:
            print(f"    FAIL: poll error: {e}")
            return False
        d = poll.get("data", poll) if isinstance(poll, dict) else {}
        raw = d.get("status") if isinstance(d, dict) else None
        job_status = str(raw).lower() if raw else None
        if job_status != last_status:
            print(f"    ... status={job_status}")
            last_status = job_status
        if job_status in _TERMINAL_OK:
            print(f"    PASS (final status={job_status})")
            return True
        if job_status in _TERMINAL_FAIL:
            print(f"    FAIL: job ended with status={job_status}. Body: {poll}")
            return False
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
    print(f"    FAIL: did not reach terminal state within {POLL_TIMEOUT_SECONDS}s (last={last_status})")
    return False


async def main() -> int:
    parser = argparse.ArgumentParser(description="Interact CRM discovery + smoke test")
    parser.add_argument(
        "--dispatch",
        metavar="TASK",
        help="Optional: dispatch this task and poll status. "
             "Only use a known idempotent task discovered from the /info output above.",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("HARROW -> Interact CRM smoke test")
    print("=" * 60)

    ok, msg = _check_env()
    print(f"env: {msg}")
    if not ok:
        print("ABORT: missing required env. Set INTERACT_AGENT_URL and INTERACT_API_KEY.")
        return 2

    results = {}
    results["health"] = await _step_health()
    info_blob = await _step_info()
    results["info"] = bool(info_blob)
    _step_openapi()  # informational only — not pass/fail
    results["logs"] = await _step_logs()

    if args.dispatch:
        results["dispatch+status"] = await _step_dispatch_and_poll(args.dispatch)
    else:
        print("[5] dispatch SKIPPED — re-run with --dispatch=<task_name> "
              "after picking an idempotent task from the /info capabilities above.")

    print()
    print("-" * 60)
    print("DISCOVERY SUMMARY")
    print("-" * 60)
    for step, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL':<5}  {step}")
    print("-" * 60)
    if all(results.values()):
        if args.dispatch:
            print("RESULT: ALL PASS — Interact wiring proven end-to-end.")
        else:
            print("RESULT: DISCOVERY PASS — read /info above and re-run with --dispatch=<task> to prove dispatch.")
        return 0
    print("RESULT: FAILURES PRESENT")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
