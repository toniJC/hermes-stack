"""Comparison tool for two calibration run JSONL files.

Usage:
    python -m calibration.compare runs/A.jsonl runs/B.jsonl [options]

Options:
    --must-not-regress  Comma-separated metric names that must not decrease.
                        Default: fields_present_ratio,schema_valid
    --format            Output format: text (default) or json

Exit codes:
    0 — no regression in guarded metrics (or no shared pairs)
    1 — regression detected in at least one guarded metric
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from calibration.store import RunRecord, load

_DEFAULT_GUARDED = ["fields_present_ratio", "schema_valid"]


def _get_metric(record: RunRecord, metric: str) -> float | None:
    """Extract a scalar metric value from a RunRecord."""
    # Try heuristic_scores first
    if metric in record.heuristic_scores:
        val = record.heuristic_scores[metric]
        if val is None:
            return None
        return float(val)
    # schema_valid is a top-level bool
    if metric == "schema_valid":
        return float(record.schema_valid)
    # latency
    if metric == "latency_ms_client":
        return record.latency_ms_client
    return None


def _flag(delta: float) -> str:
    if delta > 0.001:
        return "↑"
    if delta < -0.001:
        return "↓"
    return "="


def compare(
    path_a: Path,
    path_b: Path,
    must_not_regress: list[str],
    fmt: str,
) -> int:
    """Load two JSONL files, compute per-metric deltas, print a table.

    Returns:
        0 if no regression in guarded metrics (or no shared pairs found).
        1 if any guarded metric regressed.
    """
    records_a = load(path_a)
    records_b = load(path_b)

    # Index by (phase, fixture_id, difficulty)
    index_a: dict[tuple[str, str, str], list[RunRecord]] = defaultdict(list)
    index_b: dict[tuple[str, str, str], list[RunRecord]] = defaultdict(list)

    for r in records_a:
        index_a[(r.phase, r.fixture_id, r.difficulty)].append(r)
    for r in records_b:
        index_b[(r.phase, r.fixture_id, r.difficulty)].append(r)

    shared_keys = set(index_a.keys()) & set(index_b.keys())

    if not shared_keys:
        print(
            "Warning: no shared (phase, fixture, difficulty) pairs found between "
            f"{path_a.name} and {path_b.name}. Cannot compute deltas.",
            file=sys.stderr,
        )
        return 0

    # Collect all metrics present across both runs
    all_metrics: set[str] = set()
    for key in shared_keys:
        for r in index_a[key] + index_b[key]:
            all_metrics.update(r.heuristic_scores.keys())
            all_metrics.add("schema_valid")
    all_metrics.discard(None)  # type: ignore[arg-type]

    rows: list[dict[str, Any]] = []
    regression_detected = False

    for key in sorted(shared_keys):
        phase, fixture_id, difficulty = key
        recs_a = index_a[key]
        recs_b = index_b[key]

        for metric in sorted(all_metrics):
            vals_a = [_get_metric(r, metric) for r in recs_a if _get_metric(r, metric) is not None]
            vals_b = [_get_metric(r, metric) for r in recs_b if _get_metric(r, metric) is not None]

            if not vals_a or not vals_b:
                continue

            mean_a = sum(vals_a) / len(vals_a)
            mean_b = sum(vals_b) / len(vals_b)
            delta = mean_b - mean_a
            flag = _flag(delta)

            is_regression = delta < -0.001 and metric in must_not_regress
            if is_regression:
                regression_detected = True

            rows.append(
                {
                    "phase": phase,
                    "fixture": fixture_id,
                    "difficulty": difficulty,
                    "metric": metric,
                    "run_a": round(mean_a, 4),
                    "run_b": round(mean_b, 4),
                    "delta": round(delta, 4),
                    "flag": flag,
                    "regression": is_regression,
                }
            )

    if fmt == "json":
        print(json.dumps(rows, indent=2))
    else:
        _print_text_table(rows, path_a.stem, path_b.stem)

    return 1 if regression_detected else 0


def _print_text_table(
    rows: list[dict[str, Any]],
    label_a: str,
    label_b: str,
) -> None:
    col_w = {
        "phase": 10,
        "fixture": 28,
        "metric": 22,
        "run_a": 10,
        "run_b": 10,
        "delta": 10,
        "flag": 5,
    }
    header = (
        f"{'phase':<{col_w['phase']}} {'fixture':<{col_w['fixture']}} "
        f"{'metric':<{col_w['metric']}} {label_a[:10]:>{col_w['run_a']}} "
        f"{label_b[:10]:>{col_w['run_b']}} {'delta':>{col_w['delta']}} "
        f"{'flag':>{col_w['flag']}}"
    )
    sep = "-" * len(header)
    print(header)
    print(sep)

    prev_phase = ""
    for row in rows:
        phase = row["phase"] if row["phase"] != prev_phase else ""
        prev_phase = row["phase"]
        regr_marker = " !" if row["regression"] else ""
        print(
            f"{phase:<{col_w['phase']}} {row['fixture']:<{col_w['fixture']}} "
            f"{row['metric']:<{col_w['metric']}} {row['run_a']:>{col_w['run_a']}.4f} "
            f"{row['run_b']:>{col_w['run_b']}.4f} {row['delta']:>{col_w['delta']}.4f} "
            f"{row['flag']:>{col_w['flag']}}{regr_marker}"
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare two calibration run JSONL files.",
        prog="python -m calibration.compare",
    )
    parser.add_argument("run_a", help="Path to the first JSONL run file (baseline).")
    parser.add_argument("run_b", help="Path to the second JSONL run file (candidate).")
    parser.add_argument(
        "--must-not-regress",
        default=",".join(_DEFAULT_GUARDED),
        help=(
            "Comma-separated metric names that trigger exit code 1 on regression. "
            f"Default: {','.join(_DEFAULT_GUARDED)}"
        ),
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    guarded = [m.strip() for m in args.must_not_regress.split(",") if m.strip()]
    exit_code = compare(
        path_a=Path(args.run_a),
        path_b=Path(args.run_b),
        must_not_regress=guarded,
        fmt=args.format,
    )
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
