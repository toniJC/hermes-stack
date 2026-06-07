"""Calibration runner — async CLI entrypoint.

Usage:
    python -m calibration.runner [options]

Options:
    --phases   Comma-separated phase names (default: all 6)
    --fixtures Comma-separated difficulty labels (default: all 3)
    --judge    Enable LLM-as-judge for all phases
    --out      Output directory (default: calibration/runs/)
    --run-id   Override generated run_id
    --repeat   Number of times to repeat each (phase, fixture) pair (default: 1)
    --concurrency  Number of phases to fan-out concurrently (default: 1)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from calibration.fixtures import (
    Difficulty,
    FIXTURES,
    Fixture,
    Phase,
    get_fixtures,
)
from calibration.judge import judge as llm_judge
from calibration.scorer import estimate_tokens, score
from calibration.store import RunRecord, new_run_id, open_writer, write_record

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SCHEMA_SERVICE_BASE = "http://localhost:8010"
_LITELLM_BASE = "http://localhost:8002"
_HEALTH_TIMEOUT = 5.0
_REQUEST_TIMEOUT = 120.0

_ALL_PHASES: list[Phase] = ["propose", "spec", "design", "tasks", "verify", "explore", "apply"]
_ALL_DIFFICULTIES: list[Difficulty] = ["simple", "medium", "complex"]

_PHASE_ENDPOINTS: dict[Phase, str] = {
    "propose": "/v1/sdd/propose",
    "spec": "/v1/sdd/spec",
    "design": "/v1/sdd/design",
    "tasks": "/v1/sdd/tasks",
    "verify": "/v1/sdd/verify",
    "explore": "/v1/sdd/explore",
    "apply": "/v1/sdd/apply",
}


# ---------------------------------------------------------------------------
# Pre-flight health check
# ---------------------------------------------------------------------------

async def _check_health(client: httpx.AsyncClient, url: str, name: str) -> None:
    """Attempt a GET to *url*. Raises SystemExit(1) on failure."""
    try:
        resp = await client.get(url, timeout=_HEALTH_TIMEOUT)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        print(
            f"[preflight] FAIL — {name} at {url} is unreachable: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


async def preflight(client: httpx.AsyncClient) -> None:
    """Check that both schema-service and LiteLLM are up."""
    await _check_health(client, f"{_SCHEMA_SERVICE_BASE}/healthz", "schema-service")
    await _check_health(client, f"{_LITELLM_BASE}/health", "LiteLLM")
    print("[preflight] Both services healthy.")


# ---------------------------------------------------------------------------
# Single (phase, fixture) execution
# ---------------------------------------------------------------------------

async def run_pair(
    client: httpx.AsyncClient,
    run_id: str,
    fixture: Fixture,
    use_judge: bool,
) -> RunRecord:
    """Execute one (phase, fixture) pair and return the RunRecord."""
    phase = fixture.phase
    endpoint = _PHASE_ENDPOINTS[phase]
    payload: dict[str, Any] = {"context": fixture.context, **fixture.payload_extra}

    # Estimate input tokens before the call
    input_tokens_est = estimate_tokens(fixture.context)

    start = time.monotonic()
    error: str | None = None
    raw_response: dict[str, Any] | None = None
    schema_valid = False
    schema_errors: list[str] = []
    latency_ms_server: float | None = None
    retries: int | None = None
    output_tokens_est = 0

    try:
        resp = await client.post(
            f"{_SCHEMA_SERVICE_BASE}{endpoint}",
            json=payload,
            timeout=_REQUEST_TIMEOUT,
        )

        # Read server-side headers
        raw_retries = resp.headers.get("X-SDD-Retries")
        raw_latency = resp.headers.get("X-SDD-Latency-Ms")
        if raw_retries is not None:
            try:
                retries = int(raw_retries)
            except ValueError:
                pass
        if raw_latency is not None:
            try:
                latency_ms_server = float(raw_latency)
            except ValueError:
                pass

        if resp.status_code < 300:
            raw_response = resp.json()
            schema_valid = True

            # Estimate output tokens from the serialised response
            output_tokens_est = estimate_tokens(json.dumps(raw_response))

            # Validate against Pydantic schemas
            try:
                _validate_schema(phase, raw_response)
            except Exception as exc:  # noqa: BLE001
                schema_valid = False
                schema_errors = [str(exc)]
        else:
            error = f"HTTP {resp.status_code}: {resp.text[:500]}"

    except Exception as exc:  # noqa: BLE001
        error = str(exc)

    latency_ms_client = (time.monotonic() - start) * 1000

    # Deterministic heuristic scores
    heuristic_scores = score(phase, raw_response or {}, latency_ms_client)

    # Opt-in LLM-as-judge (all phases, no hard failure)
    judge_scores: dict[str, Any] | None = None
    if use_judge and raw_response:
        try:
            result = llm_judge(phase, fixture.context, raw_response)
            judge_scores = result
            # Propagate judge scores into heuristic_scores dict
            heuristic_scores["coherence_score"] = result["coherence_score"]
            heuristic_scores["specificity_score"] = result["specificity_score"]
        except Exception as exc:  # noqa: BLE001
            print(
                f"  [judge] WARNING — judge call failed for {phase}/{fixture.difficulty}: {exc}",
                file=sys.stderr,
            )

    return RunRecord(
        run_id=run_id,
        timestamp=datetime.now(tz=timezone.utc).isoformat(),
        phase=phase,
        fixture_id=fixture.id,
        difficulty=fixture.difficulty,
        latency_ms_client=round(latency_ms_client, 2),
        latency_ms_server=latency_ms_server,
        retries=retries,
        input_tokens_est=input_tokens_est,
        output_tokens_est=output_tokens_est,
        schema_valid=schema_valid,
        schema_errors=schema_errors,
        heuristic_scores=heuristic_scores,
        judge_scores=judge_scores,
        raw_response=raw_response,
        error=error,
    )


def _validate_schema(phase: Phase, response: dict[str, Any]) -> None:
    """Validate *response* against the appropriate Pydantic schema."""
    if phase == "propose":
        from app.schemas.propose import ProposalOut
        ProposalOut.model_validate(response)
    elif phase == "spec":
        from app.schemas.spec import SpecOut
        SpecOut.model_validate(response)
    elif phase == "design":
        from app.schemas.design import DesignOut
        DesignOut.model_validate(response)
    elif phase == "tasks":
        from app.schemas.tasks import TasksOut
        TasksOut.model_validate(response)
    elif phase == "verify":
        from app.schemas.verify import VerifyReportOut
        VerifyReportOut.model_validate(response)
    elif phase == "explore":
        from app.schemas.explore import ExploreOut
        ExploreOut.model_validate(response)
    elif phase == "apply":
        from app.schemas.apply import ApplyOut
        ApplyOut.model_validate(response)


# ---------------------------------------------------------------------------
# Main async run
# ---------------------------------------------------------------------------

async def run(
    phases: list[Phase],
    difficulties: list[Difficulty],
    use_judge: bool,
    out_dir: Path,
    run_id: str,
    repeat: int,
    concurrency: int,
) -> None:
    out_path = out_dir / f"{run_id}.jsonl"
    print(f"[runner] run_id={run_id}")
    print(f"[runner] output={out_path}")
    print(f"[runner] phases={phases}  difficulties={difficulties}  repeat={repeat}")

    async with httpx.AsyncClient() as client:
        await preflight(client)

        # Build the work list
        work: list[Fixture] = []
        for phase in phases:
            all_phase_fixtures = get_fixtures(phase)
            for fix in all_phase_fixtures:
                if fix.difficulty in difficulties:
                    work.extend([fix] * repeat)

        if not work:
            print("[runner] No fixtures matched the requested filters. Exiting.")
            return

        records: list[RunRecord] = []

        if concurrency <= 1:
            # Sequential execution
            with open_writer(out_path) as fh:
                for fixture in work:
                    print(
                        f"  [{fixture.phase}/{fixture.difficulty}] running {fixture.id} …",
                        end=" ",
                        flush=True,
                    )
                    record = await run_pair(client, run_id, fixture, use_judge)
                    write_record(fh, record)
                    records.append(record)
                    status = "OK" if record.error is None else f"ERR({record.error[:60]})"
                    print(
                        f"{status}  latency={record.latency_ms_client:.0f}ms  "
                        f"ratio={record.heuristic_scores.get('fields_present_ratio', 0):.2f}"
                    )
        else:
            # Concurrent phase fan-out
            semaphore = asyncio.Semaphore(concurrency)

            async def bounded(fixture: Fixture) -> RunRecord:
                async with semaphore:
                    return await run_pair(client, run_id, fixture, use_judge)

            records = await asyncio.gather(*[bounded(f) for f in work])
            with open_writer(out_path) as fh:
                for record in records:
                    write_record(fh, record)

    _print_summary(records)
    print(f"\n[runner] Done. Records written to {out_path}")


def _print_summary(records: list[RunRecord]) -> None:
    """Print a compact summary table to stdout."""
    print()
    print(
        f"{'phase':<10} {'difficulty':<10} {'latency_ms':>12} "
        f"{'ratio':>8} {'schema':>8} {'error':>6}"
    )
    print("-" * 64)
    for r in records:
        ratio = r.heuristic_scores.get("fields_present_ratio", 0.0)
        print(
            f"{r.phase:<10} {r.difficulty:<10} {r.latency_ms_client:>12.1f} "
            f"{ratio:>8.2f} {str(r.schema_valid):>8} {'Y' if r.error else '-':>6}"
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the schema-service calibration harness.",
        prog="python -m calibration.runner",
    )
    parser.add_argument(
        "--phases",
        default=",".join(_ALL_PHASES),
        help="Comma-separated phase names (default: all 6)",
    )
    parser.add_argument(
        "--fixtures",
        default=",".join(_ALL_DIFFICULTIES),
        help="Comma-separated difficulty labels: simple,medium,complex",
    )
    parser.add_argument(
        "--judge",
        action="store_true",
        default=False,
        help="Enable LLM-as-judge for all phases",
    )
    parser.add_argument(
        "--out",
        default="calibration/runs/",
        help="Output directory for JSONL files (default: calibration/runs/)",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Override generated run_id",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Number of times to repeat each (phase, fixture) pair (default: 1)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Number of concurrent phase calls (default: 1 = sequential)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    # Validate phases
    requested_phases: list[Phase] = []
    for p in args.phases.split(","):
        p = p.strip()
        if p not in _ALL_PHASES:
            print(
                f"Error: '{p}' is not a valid phase name.\n"
                f"Valid phases: {', '.join(_ALL_PHASES)}",
                file=sys.stderr,
            )
            raise SystemExit(1)
        requested_phases.append(p)  # type: ignore[arg-type]

    # Validate difficulties
    requested_difficulties: list[Difficulty] = []
    for d in args.fixtures.split(","):
        d = d.strip()
        if d not in _ALL_DIFFICULTIES:
            print(
                f"Error: '{d}' is not a valid difficulty label.\n"
                f"Valid labels: {', '.join(_ALL_DIFFICULTIES)}",
                file=sys.stderr,
            )
            raise SystemExit(1)
        requested_difficulties.append(d)  # type: ignore[arg-type]

    run_id = args.run_id or new_run_id()
    out_dir = Path(args.out)

    asyncio.run(
        run(
            phases=requested_phases,
            difficulties=requested_difficulties,
            use_judge=args.judge,
            out_dir=out_dir,
            run_id=run_id,
            repeat=args.repeat,
            concurrency=args.concurrency,
        )
    )


if __name__ == "__main__":
    main()
