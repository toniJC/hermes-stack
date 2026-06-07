"""Schemas for POST /v1/bmad/ux."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class UXFlow(BaseModel):
    """A named user flow with ordered steps."""

    name: str
    steps: list[str] = Field(min_length=1)


class UXIn(BaseModel):
    """Context sent to the ux endpoint."""

    context: str
    prd: Optional[str] = None  # raw JSON from bmad/prd


class UXOut(BaseModel):
    """Validated output from the BMAD ux phase (Sally — UX Expert)."""

    design_principles: list[str] = Field(min_length=1)
    user_flows: list[UXFlow] = Field(min_length=1)
    key_screens: list[str] = Field(default_factory=list)
    accessibility_notes: list[str] = Field(default_factory=list)
    interaction_notes: list[str] = Field(default_factory=list)
