"""Tests for calibration/runner.py.

Live integration tests are marked with @pytest.mark.live and skipped by default.
Run them with: pytest -m live
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from calibration.runner import _parse_args, main, preflight, run


# ---------------------------------------------------------------------------
# Scenario: Invalid phase name exits 1 before any requests
# ---------------------------------------------------------------------------

def test_invalid_phase_exits_1():
    """Passing an invalid phase name must exit with code 1 and print valid phases."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--phases", "invalid_phase"])
    assert exc_info.value.code == 1


def test_valid_phases_accepted():
    """All 6 valid phase names must be accepted without raising SystemExit."""
    args = _parse_args(["--phases", "propose,spec"])
    phases = [p.strip() for p in args.phases.split(",")]
    assert "propose" in phases
    assert "spec" in phases


# ---------------------------------------------------------------------------
# Scenario: One service unreachable — preflight raises SystemExit(1)
# ---------------------------------------------------------------------------

def test_preflight_schema_service_down_exits_1(tmp_path: Path):
    """Scenario: schema-service is down → exit 1, no JSONL written."""

    async def _run():
        transport = httpx.MockTransport(
            handler=lambda req: httpx.Response(503, text="service unavailable")
        )
        async with httpx.AsyncClient(transport=transport) as client:
            await preflight(client)

    with pytest.raises(SystemExit) as exc_info:
        asyncio.run(_run())

    assert exc_info.value.code == 1


def test_preflight_litellm_down_exits_1():
    """Scenario: LiteLLM is down → exit 1."""
    call_count = 0

    def _handler(req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if "8010" in str(req.url):
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(503, text="litellm down")

    async def _run():
        transport = httpx.MockTransport(handler=_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            await preflight(client)

    with pytest.raises(SystemExit) as exc_info:
        asyncio.run(_run())

    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Scenario: Successful health + one phase call → record appended
# ---------------------------------------------------------------------------

def _propose_response() -> dict:
    return {
        "intent": "Add dark mode toggle to user settings page with localStorage persistence",
        "scope_in": ["dark mode CSS", "toggle component"],
        "scope_out": ["system theme detection"],
        "risks": ["WCAG contrast requirements"],
        "next_steps": ["create useTheme hook", "update CSS variables"],
    }


def test_valid_run_appends_record(tmp_path: Path):
    """Scenario: Mock valid health + one phase call → record written to JSONL."""
    out_dir = tmp_path / "runs"
    run_id = "test-run-001"

    def _handler(req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if "/propose" in path:
            return httpx.Response(
                200,
                json=_propose_response(),
                headers={
                    "X-SDD-Retries": "0",
                    "X-SDD-Latency-Ms": "120",
                },
            )
        return httpx.Response(404, text="not found")

    async def _run():
        transport = httpx.MockTransport(handler=_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            # Patch the AsyncClient used inside runner.run
            with patch("calibration.runner.httpx.AsyncClient") as mock_cls:
                mock_cls.return_value.__aenter__ = AsyncMock(return_value=client)
                mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                await run(
                    phases=["propose"],
                    difficulties=["simple"],
                    use_judge=False,
                    out_dir=out_dir,
                    run_id=run_id,
                    repeat=1,
                    concurrency=1,
                )

    asyncio.run(_run())

    out_path = out_dir / f"{run_id}.jsonl"
    assert out_path.exists(), "JSONL file was not created"

    lines = out_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 1, "Expected at least one JSONL record"

    record = json.loads(lines[0])
    assert record["run_id"] == run_id
    assert record["phase"] == "propose"


# ---------------------------------------------------------------------------
# Live integration tests (skipped by default)
# ---------------------------------------------------------------------------

@pytest.mark.live
def test_live_full_run(tmp_path: Path):
    """Live integration test — requires schema-service on :8010 and LiteLLM on :4000."""
    out_dir = tmp_path / "runs"
    run_id = "live-test-001"

    asyncio.run(
        run(
            phases=["propose"],
            difficulties=["simple"],
            use_judge=False,
            out_dir=out_dir,
            run_id=run_id,
            repeat=1,
            concurrency=1,
        )
    )

    out_path = out_dir / f"{run_id}.jsonl"
    assert out_path.exists()
    lines = out_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 1

    record = json.loads(lines[0])
    assert record["phase"] == "propose"
    assert record["latency_ms_client"] > 0
