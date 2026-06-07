"""Middleware: think-tag stripping and per-request structured logging."""
from __future__ import annotations

import asyncio
import json
import logging
import time
import re
import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("schema_service.access")

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def strip_think(text: str) -> str:
    """Remove all <think>...</think> blocks from *text*.

    Safe to call on any string: returns the input unchanged if no blocks are
    present.  Strips surrounding whitespace after removal.
    """
    return _THINK_RE.sub("", text).strip()


# ---------------------------------------------------------------------------
# Request-scoped state keys stored on request.state
# ---------------------------------------------------------------------------
# request.state.request_id   : str  (UUID hex)
# request.state.worker_alias : str | None
# request.state.mode_history : list[str]
# request.state.retries      : int
# request.state.validation_errors : list


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Emit one structured JSON log line per request after the response is sent.

    Fields logged:
        request_id, path, method, status_code, worker_alias, mode_history,
        retries, latency_ms, validation_errors
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        request.state.worker_alias = None
        request.state.mode_history = []
        request.state.retries = 0
        request.state.validation_errors = []

        start = time.monotonic()
        response = await call_next(request)
        latency_ms = int((time.monotonic() - start) * 1000)

        mode_history: list[str] = request.state.mode_history
        log_record = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "worker_alias": request.state.worker_alias,
            "mode": mode_history[-1] if mode_history else None,
            "retries": request.state.retries,
            "latency_ms": latency_ms,
            "validation_errors": request.state.validation_errors,
        }

        level = logging.WARNING if response.status_code >= 400 else logging.INFO
        logger.log(level, json.dumps(log_record))

        response.headers["X-SDD-Retries"] = str(request.state.retries)
        response.headers["X-SDD-Latency-Ms"] = str(latency_ms)

        return response
