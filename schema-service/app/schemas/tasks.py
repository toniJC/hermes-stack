"""Schemas for POST /v1/sdd/tasks."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class TasksIn(BaseModel):
    """Input payload for the tasks phase."""

    context: str
    spec: Optional[str] = None    # raw JSON from the spec phase
    design: Optional[str] = None  # raw JSON from the design phase


class TasksOut(BaseModel):
    """Validated output from the tasks phase."""

    tasks: list[str]
    estimated_files: list[str]
    pr_risk: str
