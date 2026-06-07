"""Append-only JSONL store for calibration run records.

File layout: one RunRecord per line, JSON-serialised via dataclasses.asdict.
Run IDs are formatted as yyyymmdd-hhmmss-<short-uuid> for easy sorting.
"""
from __future__ import annotations

import dataclasses
import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from io import TextIOWrapper
from pathlib import Path
from typing import Any, Generator

from calibration.fixtures import Difficulty, Phase


@dataclasses.dataclass
class RunRecord:
    run_id: str
    timestamp: str            # ISO-8601 UTC
    phase: Phase
    fixture_id: str
    difficulty: Difficulty
    latency_ms_client: float
    latency_ms_server: float | None   # from X-SDD-Latency-Ms header
    retries: int | None               # from X-SDD-Retries header
    input_tokens_est: int
    output_tokens_est: int
    schema_valid: bool
    schema_errors: list[str]
    heuristic_scores: dict[str, Any]  # phase-specific metrics
    judge_scores: dict[str, Any] | None  # None unless --judge
    raw_response: dict[str, Any] | None
    error: str | None


def new_run_id() -> str:
    """Generate a sortable run ID: yyyymmdd-hhmmss-<8-char uuid fragment>."""
    now = datetime.now(tz=timezone.utc)
    short = uuid.uuid4().hex[:8]
    return now.strftime("%Y%m%d-%H%M%S") + f"-{short}"


@contextmanager
def open_writer(path: Path) -> Generator[TextIOWrapper, None, None]:
    """Context manager that opens *path* in append mode for JSONL writing.

    The caller is responsible for serialising each RunRecord via
    ``json.dumps(dataclasses.asdict(record))`` and writing one line at a time.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        yield fh  # type: ignore[misc]


def write_record(fh: TextIOWrapper, record: RunRecord) -> None:
    """Serialise *record* and append it as a single JSON line."""
    fh.write(json.dumps(dataclasses.asdict(record), ensure_ascii=False) + "\n")
    fh.flush()


def load(path: Path) -> list[RunRecord]:
    """Read every JSON line from *path* and return a list of RunRecord instances."""
    records: list[RunRecord] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            records.append(RunRecord(**data))
    return records
