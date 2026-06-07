"""SDD phase routes: one explicit POST endpoint per phase + shared retry loop."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from app.client import get_client, get_client_md_json
from app.errors import ErrorEnvelope, ValidationExhausted
from app.registry import PHASE_REGISTRY, PhaseSpec
from app.schemas.apply import ApplyIn, ApplyOut
from app.schemas.design import DesignIn, DesignOut
from app.schemas.explore import ExploreIn, ExploreOut
from app.schemas.propose import ProposeIn, ProposalOut
from app.schemas.spec import SpecIn, SpecOut
from app.schemas.tasks import TasksIn, TasksOut
from app.schemas.verify import VerifyIn, VerifyReportOut

logger = logging.getLogger("schema_service.routes")

router = APIRouter(prefix="/v1/sdd", tags=["sdd"])

# ---------------------------------------------------------------------------
# Retry / degradation loop
# ---------------------------------------------------------------------------
# Attempt schedule:
#   1: JSON mode,  temperature = phase default
#   2: MD_JSON,    temperature = phase default
#   3: MD_JSON,    temperature = max(0.1, phase default - 0.1)
# ---------------------------------------------------------------------------

_MODE_JSON = "JSON"
_MODE_MD_JSON = "MD_JSON"


async def _call_with_retry(
    phase_spec: PhaseSpec,
    messages: list[dict],
    request: Request,
) -> BaseModel:
    """Call LiteLLM via Instructor with a 3-attempt degradation strategy.

    Attempts:
        1  — instructor.Mode.JSON (primary)
        2  — instructor.Mode.MD_JSON (mode degradation)
        3  — instructor.Mode.MD_JSON, temperature reduced by 0.1 (last resort)

    Args:
        phase_spec: Configuration for the target phase.
        messages:   Full messages list (system + user).
        request:    Starlette request for state mutation (logging context).

    Returns:
        Validated Pydantic model on success.

    Raises:
        ValidationExhausted: If all 3 attempts fail Pydantic validation.
    """
    mode_history: list[str] = []
    all_errors: list[dict] = []

    attempt_configs = [
        (get_client, _MODE_JSON, phase_spec.temperature),
        (get_client, _MODE_JSON, phase_spec.temperature),
        (get_client_md_json, _MODE_MD_JSON, phase_spec.temperature),
    ]

    for attempt_num, (client_factory, mode_label, temperature) in enumerate(
        attempt_configs, start=1
    ):
        # Brief backoff before attempts 2 and 3
        if attempt_num == 3:
            await asyncio.sleep(0.2)

        mode_history.append(mode_label)
        client = client_factory()

        try:
            result = await client.chat.completions.create(
                model=phase_spec.worker_alias,
                messages=messages,
                response_model=phase_spec.response_model,
                max_tokens=phase_spec.max_tokens,
                temperature=temperature,
                max_retries=1,
            )

            # Update request state for logging middleware
            request.state.worker_alias = phase_spec.worker_alias
            request.state.mode_history = mode_history
            request.state.retries = attempt_num - 1
            request.state.validation_errors = []

            logger.info(
                "Phase '%s' succeeded on attempt %d (mode=%s)",
                request.url.path,
                attempt_num,
                mode_label,
            )
            return result

        except Exception as exc:  # noqa: BLE001
            # Instructor raises ValidationError or wraps it; capture .errors()
            errors: list[dict] = []
            if hasattr(exc, "errors"):
                try:
                    raw = exc.errors()
                    errors = [
                        {k: str(v) for k, v in e.items()} for e in (raw[:5] if raw else [])
                    ]
                except Exception:  # noqa: BLE001
                    errors = [{"raw": str(exc)}]
            else:
                errors = [{"raw": str(exc)}]

            all_errors.extend(errors)

            logger.warning(
                "Phase '%s' attempt %d failed (mode=%s): %s",
                request.url.path,
                attempt_num,
                mode_label,
                errors,
            )

    # All attempts exhausted
    request.state.worker_alias = phase_spec.worker_alias
    request.state.mode_history = mode_history
    request.state.retries = 2
    request.state.validation_errors = all_errors

    raise ValidationExhausted(
        attempts=3,
        mode_history=mode_history,
        last_errors=all_errors,
    )


def _with_meta(
    result: BaseModel,
    phase: str,
    phase_spec: PhaseSpec,
    response: Response,
) -> JSONResponse:
    """Wrap a validated Pydantic result with _meta provenance info.

    Also sets X-SDD-Phase and X-SDD-Worker HTTP headers on the response
    as a fallback source of provenance for callers that cannot inspect
    the JSON body (e.g. streaming proxies, SOUL.md curl blocks).
    """
    data = result.model_dump()
    data["_meta"] = {"phase": phase, "worker": phase_spec.worker_alias}
    response.headers["X-SDD-Phase"] = phase
    response.headers["X-SDD-Worker"] = phase_spec.worker_alias
    return JSONResponse(content=data, headers=dict(response.headers))


def _enrich_context(payload: BaseModel) -> str:
    """Build an enriched user context string from a payload's optional artifact fields.

    For phases that carry structured artifact fields (exploration, proposal,
    spec, design, tasks, apply_progress), we append each present field as a
    clearly labelled section.  The base `context` field is always included
    first.  If no optional fields are present, the result is identical to
    ``payload.context`` — full back-compat with legacy callers.
    """
    parts: list[str] = []

    context = getattr(payload, "context", None)
    if context:
        parts.append(f"## Context\n{context}")

    # Optional structured artifact fields — order matters for the LLM.
    # BMAD planning context (the WHY/WHAT) must precede SDD execution context (the HOW).
    # getattr(..., None) is safe for payloads that lack bmad_* fields (e.g. SpecIn, DesignIn).
    artifact_fields = [
        ("bmad_prd", "## BMAD PRD"),
        ("bmad_architect", "## BMAD Architecture"),
        ("bmad_stories", "## BMAD Stories"),
        ("exploration", "## Explore Phase Output"),
        ("proposal", "## Proposal Phase Output"),
        ("spec", "## Spec Phase Output"),
        ("design", "## Design Phase Output"),
        ("tasks", "## Tasks Phase Output"),
        ("apply_progress", "## Apply Progress"),
    ]
    for field_name, label in artifact_fields:
        value = getattr(payload, field_name, None)
        if value:
            parts.append(f"{label}\n{value}")

    return "\n\n".join(parts) if parts else ""


def _build_messages(phase_spec: PhaseSpec, payload: BaseModel) -> list[dict]:
    """Build the messages list for the LLM call.

    Uses _enrich_context to fold any optional structured artifact fields
    into the user message alongside the base context string.
    """
    user_content = _enrich_context(payload)
    return [
        {"role": "system", "content": phase_spec.system_prompt},
        {"role": "user", "content": user_content},
    ]


# ---------------------------------------------------------------------------
# Explicit per-phase endpoints
# ---------------------------------------------------------------------------


@router.post("/explore")
async def explore(body: ExploreIn, request: Request, response: Response) -> JSONResponse:
    """Run the SDD explore phase and return a validated ExploreOut."""
    phase_spec = PHASE_REGISTRY["explore"]
    result = await _call_with_retry(phase_spec, _build_messages(phase_spec, body), request)
    return _with_meta(result, "explore", phase_spec, response)


@router.post("/design")
async def design(body: DesignIn, request: Request, response: Response) -> JSONResponse:
    """Run the SDD design phase and return a validated DesignOut."""
    phase_spec = PHASE_REGISTRY["design"]
    result = await _call_with_retry(phase_spec, _build_messages(phase_spec, body), request)
    return _with_meta(result, "design", phase_spec, response)


@router.post("/propose")
async def propose(body: ProposeIn, request: Request, response: Response) -> JSONResponse:
    """Run the SDD propose phase and return a validated ProposalOut."""
    phase_spec = PHASE_REGISTRY["propose"]
    result = await _call_with_retry(phase_spec, _build_messages(phase_spec, body), request)
    return _with_meta(result, "propose", phase_spec, response)


@router.post("/spec")
async def spec(body: SpecIn, request: Request, response: Response) -> JSONResponse:
    """Run the SDD spec phase and return a validated SpecOut."""
    phase_spec = PHASE_REGISTRY["spec"]
    result = await _call_with_retry(phase_spec, _build_messages(phase_spec, body), request)
    return _with_meta(result, "spec", phase_spec, response)


@router.post("/tasks")
async def tasks(body: TasksIn, request: Request, response: Response) -> JSONResponse:
    """Run the SDD tasks phase and return a validated TasksOut."""
    phase_spec = PHASE_REGISTRY["tasks"]
    result = await _call_with_retry(phase_spec, _build_messages(phase_spec, body), request)
    return _with_meta(result, "tasks", phase_spec, response)


@router.post("/verify")
async def verify(body: VerifyIn, request: Request, response: Response) -> JSONResponse:
    """Run the SDD verify phase and return a validated VerifyReportOut."""
    phase_spec = PHASE_REGISTRY["verify"]
    result = await _call_with_retry(phase_spec, _build_messages(phase_spec, body), request)
    return _with_meta(result, "verify", phase_spec, response)


@router.post("/apply")
async def apply(body: ApplyIn, request: Request, response: Response) -> JSONResponse:
    """Run the SDD apply phase and return a validated ApplyOut."""
    phase_spec = PHASE_REGISTRY["apply"]
    result = await _call_with_retry(phase_spec, _build_messages(phase_spec, body), request)
    return _with_meta(result, "apply", phase_spec, response)
