"""Schemas for POST /v1/sdd/explore."""
from __future__ import annotations

from pydantic import BaseModel, Field


class FileRef(BaseModel):
    """Reference to a file affected by the explored change."""

    path: str
    role: str


class Approach(BaseModel):
    """A candidate approach for implementing the explored change."""

    name: str
    pros: list[str] = Field(min_length=1)
    cons: list[str] = Field(min_length=1)


class ExploreIn(BaseModel):
    """Input payload for the explore phase."""

    context: str


class ExploreOut(BaseModel):
    """Validated output from the explore phase."""

    summary: str
    current_state: list[str] = Field(min_length=1)
    affected_files: list[FileRef] = Field(default_factory=list)
    approaches: list[Approach] = Field(min_length=1)
    risks: list[str] = Field(default_factory=list)
    recommendation: str
    open_questions: list[str] = Field(default_factory=list)
