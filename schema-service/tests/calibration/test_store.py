"""Tests for calibration/store.py."""
import json
import re
from pathlib import Path

import pytest

from calibration.store import RunRecord, load, new_run_id, open_writer, write_record


def _make_record(run_id: str = "test-run", phase: str = "propose") -> RunRecord:
    return RunRecord(
        run_id=run_id,
        timestamp="2026-01-01T00:00:00+00:00",
        phase=phase,  # type: ignore[arg-type]
        fixture_id=f"{phase}-simple-01",
        difficulty="simple",
        latency_ms_client=123.4,
        latency_ms_server=100.0,
        retries=0,
        input_tokens_est=50,
        output_tokens_est=80,
        schema_valid=True,
        schema_errors=[],
        heuristic_scores={"fields_present_ratio": 1.0},
        judge_scores=None,
        raw_response={"intent": "do something meaningful here with more than 20 chars"},
        error=None,
    )


def test_write_then_load_round_trip(tmp_path: Path):
    """Scenario: Record written correctly — write 2 records, load, assert equality."""
    out_path = tmp_path / "test.jsonl"

    record_a = _make_record(run_id="run-abc", phase="propose")
    record_b = _make_record(run_id="run-abc", phase="spec")

    with open_writer(out_path) as fh:
        write_record(fh, record_a)
        write_record(fh, record_b)

    loaded = load(out_path)
    assert len(loaded) == 2
    assert loaded[0] == record_a
    assert loaded[1] == record_b


def test_each_line_is_valid_json(tmp_path: Path):
    """Each written line must be independently parseable with json.loads."""
    out_path = tmp_path / "test.jsonl"
    record = _make_record()

    with open_writer(out_path) as fh:
        write_record(fh, record)

    lines = out_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert "run_id" in parsed
    assert "phase" in parsed
    assert "timestamp" in parsed
    assert "heuristic_scores" in parsed


def test_new_run_id_has_date_prefix():
    """Scenario: File path is deterministic from run_id — run_id includes date prefix."""
    run_id = new_run_id()
    # Format: yyyymmdd-hhmmss-<8hex>
    assert re.match(r"^\d{8}-\d{6}-[0-9a-f]{8}$", run_id), (
        f"run_id '{run_id}' does not match expected format yyyymmdd-hhmmss-<8hex>"
    )


def test_new_run_id_unique():
    """Two consecutive run_ids must differ."""
    id1 = new_run_id()
    id2 = new_run_id()
    assert id1 != id2


def test_open_writer_creates_parent_dirs(tmp_path: Path):
    """open_writer must create parent directories if they do not exist."""
    nested_path = tmp_path / "deep" / "nested" / "run.jsonl"
    record = _make_record()

    with open_writer(nested_path) as fh:
        write_record(fh, record)

    assert nested_path.exists()
    loaded = load(nested_path)
    assert len(loaded) == 1


def test_append_mode_does_not_truncate(tmp_path: Path):
    """Writing twice to the same path must append, not overwrite."""
    out_path = tmp_path / "run.jsonl"
    record_a = _make_record(run_id="run-1")
    record_b = _make_record(run_id="run-2")

    with open_writer(out_path) as fh:
        write_record(fh, record_a)

    with open_writer(out_path) as fh:
        write_record(fh, record_b)

    loaded = load(out_path)
    assert len(loaded) == 2
