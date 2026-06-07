#!/usr/bin/env python
"""Smoke tests for schema-service running on localhost:8010.

Usage:
    /Users/pirito/projects/mlx-qwen/mlx_env/bin/python scripts/smoke.py

Prerequisites:
    - schema-service running: uvicorn app.main:app --host 127.0.0.1 --port 8010
    - LiteLLM running on localhost:8002 with local-thinking, local-coder, local-hermes
"""
from __future__ import annotations

import asyncio
import sys

import httpx

BASE_URL = "http://127.0.0.1:8010"
TIMEOUT = 180.0  # seconds — local LLM calls can be slow


async def check(client: httpx.AsyncClient, label: str, method: str, path: str, **kwargs) -> bool:
    """Run one HTTP check. Returns True on pass, False on fail."""
    try:
        response = await client.request(method, f"{BASE_URL}{path}", timeout=TIMEOUT, **kwargs)
        ok = 200 <= response.status_code < 300
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {label} → HTTP {response.status_code}")
        if not ok:
            print(f"       body: {response.text[:300]}")
        return ok
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] {label} → {exc}")
        return False


def check_fields(label: str, data: dict, required_fields: list[str]) -> bool:
    """Verify all required_fields are present in *data*."""
    missing = [f for f in required_fields if f not in data]
    if missing:
        print(f"[FAIL] {label} — missing fields: {missing}")
        return False
    print(f"[PASS] {label} — fields present: {required_fields}")
    return True


async def main() -> int:
    failures = 0

    async with httpx.AsyncClient() as client:
        # --- /healthz ---
        r = await client.get(f"{BASE_URL}/healthz", timeout=10.0)
        if r.status_code == 200 and r.json() == {"status": "ok"}:
            print("[PASS] GET /healthz → 200 {status: ok}")
        else:
            print(f"[FAIL] GET /healthz → HTTP {r.status_code} body={r.text[:200]}")
            failures += 1

        # --- POST /v1/sdd/propose ---
        propose_payload = {"context": "Build a simple REST API for todo items using FastAPI."}
        r = await client.post(
            f"{BASE_URL}/v1/sdd/propose",
            json=propose_payload,
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json()
            required = ["intent", "scope_in", "scope_out", "risks", "next_steps"]
            if not check_fields("POST /v1/sdd/propose — schema", data, required):
                failures += 1
            else:
                print(f"[PASS] POST /v1/sdd/propose → 200, intent={data.get('intent', '')[:60]}")
        else:
            print(f"[FAIL] POST /v1/sdd/propose → HTTP {r.status_code} body={r.text[:300]}")
            failures += 1

        # --- POST /v1/sdd/spec ---
        spec_payload = {"context": "Define the spec for a FastAPI todo API with CRUD endpoints."}
        r = await client.post(
            f"{BASE_URL}/v1/sdd/spec",
            json=spec_payload,
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json()
            required = ["requirements", "scenarios", "out_of_scope"]
            if not check_fields("POST /v1/sdd/spec — schema", data, required):
                failures += 1
            else:
                print(f"[PASS] POST /v1/sdd/spec → 200, {len(data.get('requirements', []))} requirements")
        else:
            print(f"[FAIL] POST /v1/sdd/spec → HTTP {r.status_code} body={r.text[:300]}")
            failures += 1

        # --- POST /v1/sdd/tasks ---
        tasks_payload = {"context": "Break down implementation tasks for a FastAPI todo API."}
        r = await client.post(
            f"{BASE_URL}/v1/sdd/tasks",
            json=tasks_payload,
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json()
            required = ["tasks", "estimated_files", "pr_risk"]
            if not check_fields("POST /v1/sdd/tasks — schema", data, required):
                failures += 1
            else:
                print(f"[PASS] POST /v1/sdd/tasks → 200, pr_risk={data.get('pr_risk', '?')}")
        else:
            print(f"[FAIL] POST /v1/sdd/tasks → HTTP {r.status_code} body={r.text[:300]}")
            failures += 1

        # --- POST /v1/sdd/verify ---
        verify_payload = {
            "context": (
                "Verify this implementation: a FastAPI todo API with GET /todos and POST /todos. "
                "Spec requires: list todos, create todo, each with id and title fields."
            )
        }
        r = await client.post(
            f"{BASE_URL}/v1/sdd/verify",
            json=verify_payload,
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json()
            required = ["status", "critical", "warnings", "suggestions"]
            if not check_fields("POST /v1/sdd/verify — schema", data, required):
                failures += 1
            else:
                print(f"[PASS] POST /v1/sdd/verify → 200, status={data.get('status', '?')}")
        else:
            print(f"[FAIL] POST /v1/sdd/verify → HTTP {r.status_code} body={r.text[:300]}")
            failures += 1

        # --- Retry/logging note ---
        # The retry loop writes 'retries' to structured logs, not to the response body.
        # On a successful first-attempt request, retries=0 should appear in the service logs.
        # Verify this by reading the service log output when running the tests above.
        print()
        print("NOTE: retry/degradation behavior is observable in service logs only.")
        print("      Look for JSON log lines with 'retries' and 'mode_history' fields.")

    print()
    if failures == 0:
        print("All smoke tests passed.")
        return 0
    else:
        print(f"{failures} smoke test(s) FAILED.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
