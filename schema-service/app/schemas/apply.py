"""Schemas for POST /v1/sdd/apply."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ApplyIn(BaseModel):
    """Input payload for the apply phase."""

    tasks: list[str] = Field(..., min_length=1, description="List of tasks to execute")
    context: str = Field(..., min_length=1, description="Change context (spec/design refs or code)")


class ApplyOut(BaseModel):
    """Validated output from the apply phase."""

    changes: list[str] = Field(..., description="Plain-language descriptions of changes made")
    status: Literal["complete", "partial", "blocked"]
    worker: str = Field(..., description="Model identifier that executed this response")
