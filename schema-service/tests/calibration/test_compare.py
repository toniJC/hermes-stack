"""Tests for calibration/compare.py."""
import dataclasses
import json
from pathlib import Path

import pytest

from calibration.compare import compare
from calibration.store import RunRecord, open_writer, write_record


def _make_record(
    run_id: str = "run-a",
    phase: str = "propose",
    fixture_id: str = "propose-simple-01",
    difficulty: str = "simple",
    fields_present_ratio: float = 1.0,
    schema_valid: bool = True,
) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        timestamp="2026-01-01T00:00:00+00:00",
        phase=phase,  # type: ignore[arg-type]
        fixture_id=fixture_id,
        difficulty=difficulty,
        latency_ms_client=100.0,
        latency_ms_server=95.0,
        retries=0,
        input_tokens_est=50,
        output_tokens_est=80,
        schema_valid=schema_valid,
        schema_errors=[],
        heuristic_scores={
            "fields_present_ratio": fields_present_ratio,
            "list_min_length": True,
            "str_min_length": True,
            "enum_valid": None,
            "approach_count": None,
            "coherence_score": None,
            "specificity_score": None,
        },
        judge_scores=None,
        raw_response={"intent": "something meaningful with enough characters to pass"},
        error=None,
    )


def _write_records(path: Path, records: list[RunRecord]) -> None:
    with open_writer(path) as fh:
        for r in records:
            write_record(fh, r)


# ---------------------------------------------------------------------------
# Scenario: Two comparable runs
# ---------------------------------------------------------------------------

def test_compare_overlapping_pairs_exit_zero(tmp_path: Path):
    """Scenario: Two comparable runs with same (phase, fixture, difficulty) → exit 0."""
    path_a = tmp_path / "run_a.jsonl"
    path_b = tmp_path / "run_b.jsonl"

    _write_records(path_a, [
        _make_record(run_id="run-a", fields_present_ratio=0.8, schema_valid=True),
    ])
    _write_records(path_b, [
        _make_record(run_id="run-b", fields_present_ratio=1.0, schema_valid=True),
    ])

    exit_code = compare(path_a, path_b, must_not_regress=["fields_present_ratio"], fmt="text")
    assert exit_code == 0


def test_compare_improvement_shows_up_arrow(tmp_path: Path, capsys):
    """An improvement in fields_present_ratio should show ↑ in the output."""
    path_a = tmp_path / "run_a.jsonl"
    path_b = tmp_path / "run_b.jsonl"

    _write_records(path_a, [_make_record(run_id="run-a", fields_present_ratio=0.5)])
    _write_records(path_b, [_make_record(run_id="run-b", fields_present_ratio=1.0)])

    compare(path_a, path_b, must_not_regress=[], fmt="text")
    captured = capsys.readouterr()
    assert "↑" in captured.out


# ---------------------------------------------------------------------------
# Scenario: No shared pairs
# ---------------------------------------------------------------------------

def test_compare_no_shared_pairs_exit_zero(tmp_path: Path):
    """Scenario: No shared pairs → warning printed, exit 0."""
    path_a = tmp_path / "run_a.jsonl"
    path_b = tmp_path / "run_b.jsonl"

    _write_records(path_a, [
        _make_record(run_id="run-a", phase="propose", fixture_id="propose-simple-01", difficulty="simple"),
    ])
    _write_records(path_b, [
        _make_record(run_id="run-b", phase="spec", fixture_id="spec-medium-01", difficulty="medium"),
    ])

    exit_code = compare(path_a, path_b, must_not_regress=["fields_present_ratio"], fmt="text")
    assert exit_code == 0


def test_compare_no_shared_pairs_prints_warning(tmp_path: Path, capsys):
    """No shared pairs must print a warning message to stderr."""
    path_a = tmp_path / "run_a.jsonl"
    path_b = tmp_path / "run_b.jsonl"

    _write_records(path_a, [_make_record(run_id="a", phase="propose", fixture_id="p-s", difficulty="simple")])
    _write_records(path_b, [_make_record(run_id="b", phase="spec", fixture_id="s-m", difficulty="medium")])

    compare(path_a, path_b, must_not_regress=[], fmt="text")
    captured = capsys.readouterr()
    assert "no shared" in captured.err.lower() or "warning" in captured.err.lower()


# ---------------------------------------------------------------------------
# Scenario: Regression in guarded metric → exit 1
# ---------------------------------------------------------------------------

def test_compare_regression_in_guarded_metric_exit_one(tmp_path: Path):
    """Regression in a must-not-regress metric must return exit code 1."""
    path_a = tmp_path / "run_a.jsonl"
    path_b = tmp_path / "run_b.jsonl"

    _write_records(path_a, [_make_record(run_id="run-a", fields_present_ratio=1.0)])
    _write_records(path_b, [_make_record(run_id="run-b", fields_present_ratio=0.5)])

    exit_code = compare(
        path_a, path_b,
        must_not_regress=["fields_present_ratio"],
        fmt="text",
    )
    assert exit_code == 1


def test_compare_regression_not_guarded_exit_zero(tmp_path: Path):
    """Regression in a non-guarded metric must not trigger exit code 1."""
    path_a = tmp_path / "run_a.jsonl"
    path_b = tmp_path / "run_b.jsonl"

    _write_records(path_a, [_make_record(run_id="run-a", fields_present_ratio=1.0)])
    _write_records(path_b, [_make_record(run_id="run-b", fields_present_ratio=0.5)])

    exit_code = compare(
        path_a, path_b,
        must_not_regress=[],  # no guarded metrics
        fmt="text",
    )
    assert exit_code == 0


# ---------------------------------------------------------------------------
# JSON format output
# ---------------------------------------------------------------------------

def test_compare_json_format_output(tmp_path: Path, capsys):
    """--format json must produce valid JSON output."""
    path_a = tmp_path / "run_a.jsonl"
    path_b = tmp_path / "run_b.jsonl"

    _write_records(path_a, [_make_record(run_id="a")])
    _write_records(path_b, [_make_record(run_id="b")])

    compare(path_a, path_b, must_not_regress=[], fmt="json")
    captured = capsys.readouterr()
    rows = json.loads(captured.out)
    assert isinstance(rows, list)
