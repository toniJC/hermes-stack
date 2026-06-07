"""
Shared base for SDD phase Pydantic validators.
Implements the 3-attempt degradation loop:
  Attempt 1: call LiteLLM with response_format=json_object
  Attempt 2: same + prompt nudge
  Attempt 3: MD_JSON — ask model to produce JSON inside ```json``` block, then extract
  Failure: raise with {phase, worker, attempt: 3, last_error}

No curl to :8010. Self-contained. Called from per-phase scripts or execute_code.
"""

import json
import re
import sys
import urllib.request
from typing import Any, Optional, Type

from pydantic import BaseModel, ValidationError

LITELLM_BASE = "http://host.docker.internal:8002"
SCHEMA_FALLBACK = False  # D1: disabled by default; set SCHEMA_FALLBACK=true to enable


class ValidationFailure(Exception):
    def __init__(self, phase: str, worker: str, attempt: int, last_error: str):
        self.phase = phase
        self.worker = worker
        self.attempt = attempt
        self.last_error = last_error
        super().__init__(
            json.dumps(
                {
                    "phase": phase,
                    "worker": worker,
                    "attempt": attempt,
                    "last_error": last_error,
                }
            )
        )


def _litellm_call(worker: str, messages: list[dict], attempt: int) -> str:
    """Call LiteLLM at :8002 and return the raw text content."""
    payload: dict[str, Any] = {
        "model": worker,
        "messages": messages,
        "max_tokens": 4096,
    }
    # Attempt 1 and 2: request JSON mode
    if attempt <= 2:
        payload["response_format"] = {"type": "json_object"}

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{LITELLM_BASE}/v1/chat/completions",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=120)
    body = json.loads(resp.read())
    return body["choices"][0]["message"]["content"]


def _extract_json_from_md(text: str) -> str:
    """Extract JSON from a ```json ... ``` block, or return text as-is."""
    match = re.search(r"```json\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Fallback: try to find a bare {...} block
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def validate_with_retry(
    phase: str,
    worker: str,
    schema_cls: Type[BaseModel],
    prompt: str,
    raw_json: Optional[str] = None,
) -> dict:
    """
    Validate output against a Pydantic schema with 3-attempt degradation.

    If raw_json is provided (pre-generated text), attempts to validate it directly
    before making LiteLLM calls. This enables the unit-test path.

    Returns: validated dict on success.
    Raises: ValidationFailure on 3 consecutive failures.
    """
    last_error = ""

    for attempt in range(1, 4):
        try:
            if raw_json is not None and attempt == 1:
                # Validate pre-generated text without calling LiteLLM
                candidate = raw_json
            else:
                # Build messages for the attempt
                if attempt == 1:
                    messages = [{"role": "user", "content": prompt}]
                elif attempt == 2:
                    messages = [
                        {"role": "user", "content": prompt},
                        {
                            "role": "assistant",
                            "content": last_error,
                        },
                        {
                            "role": "user",
                            "content": (
                                "Your previous response was not valid JSON. "
                                "Respond with ONLY valid JSON, no prose, no markdown fences."
                            ),
                        },
                    ]
                else:  # attempt 3: MD_JSON mode
                    messages = [
                        {
                            "role": "user",
                            "content": (
                                f"{prompt}\n\n"
                                "IMPORTANT: Wrap your JSON response inside a ```json``` block. "
                                "Example:\n```json\n{\"key\": \"value\"}\n```"
                            ),
                        }
                    ]

                candidate = _litellm_call(worker, messages, attempt)

            # For attempt 3, extract from MD block first
            if attempt == 3:
                candidate = _extract_json_from_md(candidate)

            parsed = json.loads(candidate)
            validated = schema_cls.model_validate(parsed)
            return validated.model_dump()

        except (json.JSONDecodeError, ValidationError, Exception) as exc:
            last_error = str(exc)
            print(
                f"[validate:{phase}] attempt {attempt} failed: {last_error[:200]}",
                file=sys.stderr,
            )

    raise ValidationFailure(
        phase=phase,
        worker=worker,
        attempt=3,
        last_error=last_error,
    )
