"""Schemas for POST /v1/sdd/design."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class DesignIn(BaseModel):
    """Pre-trimmed context sent to the design endpoint.

    The caller (orchestrator) is responsible for trimming the combined
    proposal + spec content to ≤28K tokens before sending this payload.
    Schema-service does NOT truncate server-side.
    """

    context: str
    proposal: Optional[str] = None      # raw JSON from the propose phase
    spec: Optional[str] = None          # raw JSON from the spec phase
    constraints: Optional[str] = None  # additional constraints or context


class DesignOut(BaseModel):
    """Validated output from the design phase."""

    approach: str
    decisions: list[str]
    file_changes: list[str]
    data_flow: str
    testing_strategy: list[str]
