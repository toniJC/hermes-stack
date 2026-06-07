"""Schemas for POST /v1/sdd/verify."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class VerifyIn(BaseModel):
    """Input payload for the verify phase."""

    context: str
    tasks: Optional[str] = None                    # raw JSON from the tasks phase
    apply_progress: Optional[str] = None           # raw JSON from the apply phase
    implementation_notes: Optional[str] = None     # free-form notes from the implementer


class VerifyReportOut(BaseModel):
    """Validated output from the verify phase."""

    status: str
    critical: list[str]
    warnings: list[str]
    suggestions: list[str]
