"""Schemas for POST /v1/bmad/prd."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Requirement(BaseModel):
    """A single functional requirement with MoSCoW priority."""

    id: str                 # e.g. "FR-1"
    description: str
    priority: str           # "must" | "should" | "could"


class PRDIn(BaseModel):
    """Context sent to the prd endpoint."""

    context: str
    analyze: Optional[str] = None  # raw JSON from bmad/analyze


class PRDOut(BaseModel):
    """Validated output from the BMAD prd phase (John — Product Manager)."""

    overview: str
    functional_requirements: list[Requirement] = Field(min_length=1)
    non_functional_requirements: list[str] = Field(default_factory=list)
    user_personas: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
