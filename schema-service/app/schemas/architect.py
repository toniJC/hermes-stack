"""Schemas for POST /v1/bmad/architect."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ArchitectIn(BaseModel):
    """Context sent to the architect endpoint."""

    context: str
    prd: Optional[str] = None  # raw JSON from bmad/prd
    ux: Optional[str] = None   # raw JSON from bmad/ux (optional phase)


class ArchitectOut(BaseModel):
    """Validated output from the BMAD architect phase (Winston — Software Architect)."""

    architecture_overview: str
    components: list[str] = Field(min_length=1)
    data_models: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(min_length=1)
    integration_points: list[str] = Field(default_factory=list)
    architectural_decisions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
