"""Schemas for POST /v1/sdd/propose."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ProposeIn(BaseModel):
    """Free-form context sent to the propose endpoint."""

    context: str
    exploration: Optional[str] = None       # raw JSON from the explore phase
    bmad_prd: Optional[str] = None          # raw JSON from bmad/prd
    bmad_architect: Optional[str] = None    # raw JSON from bmad/architect
    bmad_stories: Optional[str] = None      # raw JSON from bmad/stories


class ProposalOut(BaseModel):
    """Validated output from the propose phase."""

    intent: str
    scope_in: list[str]
    scope_out: list[str]
    risks: list[str]
    next_steps: list[str]
