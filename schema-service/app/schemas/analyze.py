"""Schemas for POST /v1/bmad/analyze."""
from __future__ import annotations

from pydantic import BaseModel, Field


class AnalyzeIn(BaseModel):
    """Raw business idea / brief sent to the analyze endpoint."""

    context: str


class AnalyzeOut(BaseModel):
    """Validated output from the BMAD analyze phase (Mary — Business Analyst)."""

    problem_statement: str
    target_users: list[str] = Field(min_length=1)
    market_context: list[str] = Field(default_factory=list)
    goals: list[str] = Field(min_length=1)
    success_metrics: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
