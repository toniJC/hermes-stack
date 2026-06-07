"""Phase registry: maps SDD phase names to their PhaseSpec configuration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel

from app.prompts import load_prompt
from app.schemas.analyze import AnalyzeOut
from app.schemas.apply import ApplyOut
from app.schemas.architect import ArchitectOut
from app.schemas.design import DesignOut
from app.schemas.explore import ExploreOut
from app.schemas.prd import PRDOut
from app.schemas.propose import ProposalOut
from app.schemas.spec import SpecOut
from app.schemas.stories import StoriesOut
from app.schemas.tasks import TasksOut
from app.schemas.ux import UXOut
from app.schemas.verify import VerifyReportOut


@dataclass(frozen=True)
class PhaseSpec:
    """Configuration for a single SDD phase."""

    response_model: type[BaseModel]
    """Pydantic v2 model Instructor will validate against."""
    worker_alias: str
    """LiteLLM model alias, e.g. 'local-thinking'."""
    system_prompt: str
    """Phase-specific system instruction sent as the system message."""
    max_tokens: int
    """Output token budget for this phase."""
    temperature: float = 0.2
    """Sampling temperature. Reduced to 0.1 on the final retry attempt."""
    max_input_tokens: int = 28000
    """Input token budget. Caller (orchestrator) must trim inputs to this limit.
    Schema-service does NOT enforce truncation server-side."""


PHASE_REGISTRY: dict[str, PhaseSpec] = {
    "explore": PhaseSpec(
        response_model=ExploreOut,
        worker_alias="local-hermes",
        system_prompt=load_prompt("explore"),
        max_tokens=4096,
        max_input_tokens=28000,
        temperature=0.3,
    ),
    "propose": PhaseSpec(
        response_model=ProposalOut,
        worker_alias="local-thinking",
        system_prompt=load_prompt("propose"),
        max_tokens=3000,
        max_input_tokens=32768,
    ),
    "design": PhaseSpec(
        response_model=DesignOut,
        worker_alias="local-thinking",
        system_prompt=load_prompt("design"),
        max_tokens=3500,
        max_input_tokens=28000,
    ),
    "spec": PhaseSpec(
        response_model=SpecOut,
        worker_alias="local-coder",
        system_prompt=load_prompt("spec"),
        max_tokens=2500,
    ),
    "tasks": PhaseSpec(
        response_model=TasksOut,
        worker_alias="local-coder",
        system_prompt=load_prompt("tasks"),
        max_tokens=2000,
    ),
    "verify": PhaseSpec(
        response_model=VerifyReportOut,
        worker_alias="local-hermes",
        system_prompt=load_prompt("verify"),
        max_tokens=2000,
    ),
    "apply": PhaseSpec(
        response_model=ApplyOut,
        worker_alias="local-coder",
        system_prompt=load_prompt("apply"),
        max_tokens=4096,
        temperature=0.2,
    ),
    # ---------------------------------------------------------------------------
    # BMAD planning phases
    # ---------------------------------------------------------------------------
    "analyze": PhaseSpec(
        response_model=AnalyzeOut,
        worker_alias="local-thinking",
        system_prompt=load_prompt("bmad_analyze"),
        max_tokens=3000,
        max_input_tokens=28000,
        temperature=0.3,
    ),
    "prd": PhaseSpec(
        response_model=PRDOut,
        worker_alias="local-thinking",
        system_prompt=load_prompt("bmad_prd"),
        max_tokens=3500,
        max_input_tokens=28000,
    ),
    "ux": PhaseSpec(
        response_model=UXOut,
        worker_alias="local-hermes",
        system_prompt=load_prompt("bmad_ux"),
        max_tokens=3000,
        max_input_tokens=28000,
        temperature=0.3,
    ),
    "architect": PhaseSpec(
        response_model=ArchitectOut,
        worker_alias="local-thinking",
        system_prompt=load_prompt("bmad_architect"),
        max_tokens=4096,
        max_input_tokens=28000,
    ),
    "stories": PhaseSpec(
        response_model=StoriesOut,
        worker_alias="local-coder",
        system_prompt=load_prompt("bmad_stories"),
        max_tokens=4096,
        max_input_tokens=28000,
    ),
}
