"""FastAPI application factory for schema-service."""
from __future__ import annotations

import logging
import traceback
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.errors import ErrorEnvelope, ValidationExhausted
from app.middleware import RequestLoggingMiddleware
from app.routes import bmad, health, sdd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    app = FastAPI(
        title="Schema Service",
        description="Typed middleware between the SDD orchestrator and local LLM workers.",
        version="0.1.0",
    )

    # --- Middleware ---
    app.add_middleware(RequestLoggingMiddleware)

    # --- Routes ---
    app.include_router(health.router)
    app.include_router(sdd.router)
    app.include_router(bmad.router)

    # --- Exception handlers ---

    @app.exception_handler(ValidationExhausted)
    async def validation_exhausted_handler(
        request: Request, exc: ValidationExhausted
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        phase = request.url.path.split("/")[-1]
        worker_alias = getattr(request.state, "worker_alias", None)

        envelope = ErrorEnvelope(
            error="validation_failed",
            code=f"LLM output failed schema validation after {exc.attempts} attempts.",
            phase=phase,
            worker_alias=worker_alias,
            attempts=exc.attempts,
            mode_history=exc.mode_history,
            last_errors=exc.last_errors[:5] if exc.last_errors else None,
            request_id=request_id,
        )
        return JSONResponse(status_code=422, content=envelope.model_dump())

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        phase = request.url.path.split("/")[-1]

        # Log full traceback to service logs only — never in the response body
        logging.getLogger("schema_service.errors").error(
            "Unhandled exception on %s [request_id=%s]:\n%s",
            request.url.path,
            request_id,
            traceback.format_exc(),
        )

        envelope = ErrorEnvelope(
            error="internal_error",
            code="An unexpected error occurred. See service logs for details.",
            phase=phase,
            request_id=request_id,
        )
        return JSONResponse(status_code=500, content=envelope.model_dump())

    return app


# Expose top-level `app` object for uvicorn
app = create_app()
