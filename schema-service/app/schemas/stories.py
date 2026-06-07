"""Schemas for POST /v1/bmad/stories."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Story(BaseModel):
    """A dev-ready user story with acceptance criteria."""

    id: str                                             # e.g. "STORY-1"
    title: str
    as_a: str                                           # role
    i_want: str                                         # capability
    so_that: str                                        # benefit
    acceptance_criteria: list[str] = Field(min_length=1)


class StoriesIn(BaseModel):
    """Context sent to the stories endpoint."""

    context: str
    prd: Optional[str] = None       # raw JSON from bmad/prd
    architect: Optional[str] = None  # raw JSON from bmad/architect


class StoriesOut(BaseModel):
    """Validated output from the BMAD stories phase (Scrum Master / PO)."""

    epic: str
    stories: list[Story] = Field(min_length=1)
    sequencing_notes: list[str] = Field(default_factory=list)
