"""Error types and response envelopes for schema-service."""
from __future__ import annotations

from pydantic import BaseModel


class ValidationExhausted(Exception):
    """Raised when all retry attempts are exhausted and validation still fails."""

    def __init__(
        self,
        *,
        attempts: int,
        mode_history: list[str],
        last_errors: list[dict],
    ) -> None:
        self.attempts = attempts
        self.mode_history = mode_history
        self.last_errors = last_errors
        super().__init__(f"Validation exhausted after {attempts} attempts")


class ErrorEnvelope(BaseModel):
    """Consistent JSON error shape returned for all non-2xx responses."""

    error: str
    """Machine-readable code: 'validation_failed', 'upstream_unavailable', 'internal_error'."""
    code: str
    """Human-readable summary."""
    phase: str
    """Which endpoint was called, e.g. 'propose'."""
    worker_alias: str | None = None
    """LiteLLM alias targeted (None if resolution failed before dispatch)."""
    attempts: int = 0
    """Number of LLM calls made (1..3)."""
    mode_history: list[str] = []
    """Instructor modes used per attempt, e.g. ['JSON', 'MD_JSON', 'MD_JSON']."""
    last_errors: list[dict] | None = None
    """Pydantic .errors() from the final attempt, truncated to first 5."""
    request_id: str = ""
    """UUID for log correlation."""
