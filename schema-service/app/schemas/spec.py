"""Schemas for POST /v1/sdd/spec."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SpecIn(BaseModel):
    """Input payload for the spec phase."""

    context: str
    proposal: Optional[str] = None  # raw JSON from the propose phase


class SpecOut(BaseModel):
    """Validated output from the spec phase."""

    requirements: list[str]
    scenarios: list[str]
    out_of_scope: list[str]
