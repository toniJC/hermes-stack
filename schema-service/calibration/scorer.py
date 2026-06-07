"""Deterministic heuristic scorer for SDD phase responses.

Computes the following metrics without any external API call:

    fields_present_ratio : float  — non-empty required fields / total required fields
    list_min_length      : bool   — all required list fields have >= 1 item
    str_min_length       : bool   — all required string fields have >= 20 chars
    enum_valid           : bool | null — pr_risk valid for tasks; status valid for verify
    approach_count       : bool | null — explore.approaches >= 2 (null for other phases)

Note: token estimation uses tiktoken cl100k_base, which is an approximation
for billing purposes — not accurate for every model, but STABLE across runs,
which is all a relative-delta harness needs.
"""
from __future__ import annotations

from typing import Any

import tiktoken

from calibration.fixtures import Phase

_ENCODING = tiktoken.get_encoding("cl100k_base")

# ---------------------------------------------------------------------------
# Required fields per phase
# format: (field_name, field_type) where type is "str" | "list" | "enum"
# ---------------------------------------------------------------------------

_PHASE_FIELDS: dict[Phase, list[tuple[str, str]]] = {
    "propose": [
        ("intent", "str"),
        ("scope_in", "list"),
        ("scope_out", "list"),
        ("risks", "list"),
        ("next_steps", "list"),
    ],
    "spec": [
        ("requirements", "list"),
        ("scenarios", "list"),
        ("out_of_scope", "list"),
    ],
    "design": [
        ("approach", "str"),
        ("decisions", "list"),
        ("file_changes", "list"),
        ("testing_strategy", "list"),
        ("data_flow", "str"),
    ],
    "tasks": [
        ("tasks", "list"),
        ("estimated_files", "list"),
        ("pr_risk", "enum"),
    ],
    "verify": [
        ("status", "enum"),
        ("critical", "list"),
        ("warnings", "list"),
        ("suggestions", "list"),
    ],
    "explore": [
        ("summary", "str"),
        ("current_state", "list"),
        ("affected_files", "list"),
        ("approaches", "list"),
        ("risks", "list"),
        ("open_questions", "list"),
        ("recommendation", "str"),
    ],
    "apply": [
        ("changes", "list"),
        ("status", "enum"),
        ("worker", "str"),
    ],
}

_TASKS_ENUM_VALUES = {"low", "medium", "high"}
_VERIFY_ENUM_VALUES = {"pass", "fail", "partial"}


def _is_present(value: Any, field_type: str) -> bool:
    """Return True when *value* is non-empty for its field type."""
    if value is None:
        return False
    if field_type in ("str", "enum"):
        return isinstance(value, str) and len(value.strip()) > 0
    if field_type == "list":
        return isinstance(value, list) and len(value) > 0
    return False


def score(phase: Phase, response: dict[str, Any], latency_ms: float) -> dict[str, Any]:
    """Score a phase response deterministically.

    Args:
        phase:      One of the 6 SDD phase names.
        response:   The raw response dict (already parsed from JSON).
        latency_ms: End-to-end client-side latency in milliseconds.

    Returns:
        A dict with keys:
            fields_present_ratio, list_min_length, str_min_length,
            enum_valid (bool|None), approach_count (bool|None),
            coherence_score (None), specificity_score (None)
    """
    fields = _PHASE_FIELDS[phase]
    total = len(fields)

    present_count = 0
    list_ok = True
    str_ok = True

    for name, ftype in fields:
        value = response.get(name)
        if _is_present(value, ftype):
            present_count += 1
        else:
            if ftype == "list":
                list_ok = False
            elif ftype == "str":
                str_ok = False

        # String minimum length check (>= 20 chars)
        if ftype == "str" and isinstance(value, str):
            if len(value.strip()) < 20:
                str_ok = False

        # List minimum length check (>= 1 item)
        if ftype == "list" and isinstance(value, list):
            if len(value) == 0:
                list_ok = False

    fields_present_ratio = present_count / total if total > 0 else 0.0

    # enum_valid: only applicable for tasks (pr_risk) and verify (status)
    enum_valid: bool | None = None
    if phase == "tasks":
        pr_risk = response.get("pr_risk")
        enum_valid = isinstance(pr_risk, str) and pr_risk in _TASKS_ENUM_VALUES
    elif phase == "verify":
        status = response.get("status")
        enum_valid = isinstance(status, str) and status in _VERIFY_ENUM_VALUES
    elif phase == "apply":
        status = response.get("status")
        enum_valid = isinstance(status, str) and status in {"complete", "partial", "blocked"}

    # approach_count: only applicable for explore
    approach_count: bool | None = None
    if phase == "explore":
        approaches = response.get("approaches")
        approach_count = isinstance(approaches, list) and len(approaches) >= 2

    return {
        "fields_present_ratio": fields_present_ratio,
        "list_min_length": list_ok,
        "str_min_length": str_ok,
        "enum_valid": enum_valid,
        "approach_count": approach_count,
        "coherence_score": None,
        "specificity_score": None,
    }


def estimate_tokens(text: str) -> int:
    """Estimate token count using tiktoken cl100k_base.

    This is an approximation — not billing-accurate — but stable across runs.
    """
    return len(_ENCODING.encode(text))
