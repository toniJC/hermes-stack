"""BMAD planning phase routes: one explicit POST endpoint per phase."""
from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app.registry import PHASE_REGISTRY
from app.routes.sdd import _build_messages, _call_with_retry, _with_meta
from app.schemas.analyze import AnalyzeIn
from app.schemas.architect import ArchitectIn
from app.schemas.prd import PRDIn
from app.schemas.stories import StoriesIn
from app.schemas.ux import UXIn

router = APIRouter(prefix="/v1/bmad", tags=["bmad"])


@router.post("/analyze")
async def analyze(body: AnalyzeIn, request: Request, response: Response) -> JSONResponse:
    """Run the BMAD analyze phase and return a validated AnalyzeOut."""
    phase_spec = PHASE_REGISTRY["analyze"]
    result = await _call_with_retry(phase_spec, _build_messages(phase_spec, body), request)
    return _with_meta(result, "analyze", phase_spec, response)


@router.post("/prd")
async def prd(body: PRDIn, request: Request, response: Response) -> JSONResponse:
    """Run the BMAD prd phase and return a validated PRDOut."""
    phase_spec = PHASE_REGISTRY["prd"]
    result = await _call_with_retry(phase_spec, _build_messages(phase_spec, body), request)
    return _with_meta(result, "prd", phase_spec, response)


@router.post("/ux")
async def ux(body: UXIn, request: Request, response: Response) -> JSONResponse:
    """Run the BMAD ux phase and return a validated UXOut."""
    phase_spec = PHASE_REGISTRY["ux"]
    result = await _call_with_retry(phase_spec, _build_messages(phase_spec, body), request)
    return _with_meta(result, "ux", phase_spec, response)


@router.post("/architect")
async def architect(body: ArchitectIn, request: Request, response: Response) -> JSONResponse:
    """Run the BMAD architect phase and return a validated ArchitectOut."""
    phase_spec = PHASE_REGISTRY["architect"]
    result = await _call_with_retry(phase_spec, _build_messages(phase_spec, body), request)
    return _with_meta(result, "architect", phase_spec, response)


@router.post("/stories")
async def stories(body: StoriesIn, request: Request, response: Response) -> JSONResponse:
    """Run the BMAD stories phase and return a validated StoriesOut."""
    phase_spec = PHASE_REGISTRY["stories"]
    result = await _call_with_retry(phase_spec, _build_messages(phase_spec, body), request)
    return _with_meta(result, "stories", phase_spec, response)
