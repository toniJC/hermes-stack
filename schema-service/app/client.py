"""Instructor client factory with think-tag stripping for DeepSeek R1."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

import instructor
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from app.middleware import strip_think

LITELLM_BASE_URL = "http://localhost:8002/v1"
import os
LITELLM_API_KEY = os.environ.get("LITELLM_API_KEY", "hermes-local-dev")


class ThinkStrippingAsyncOpenAI(AsyncOpenAI):
    """AsyncOpenAI subclass that strips <think>...</think> blocks from
    completion content before returning the response to Instructor.

    Stripping is applied unconditionally — it is a no-op for completions
    that contain no think tags (i.e. all non-R1 workers are unaffected).
    """

    async def _strip_completion(self, response: ChatCompletion) -> ChatCompletion:
        """Mutate choices[i].message.content in-place and return the response."""
        for choice in response.choices:
            if choice.message.content is not None:
                choice.message.content = strip_think(choice.message.content)
        return response

    # Override the async create path used by Instructor.
    # Instructor calls client.chat.completions.create(...) and expects a
    # ChatCompletion-like object back.  We intercept the returned coroutine,
    # strip, and forward.
    #
    # Note: we cannot simply override __init_subclass__ or __call__ — we
    # must hook chat.completions.create specifically because that is the
    # single code path Instructor uses.
    #
    # We do this by wrapping the completions resource after initialisation.

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Patch create on the chat.completions resource so Instructor
        # transparently receives stripped completions.
        original_create = self.chat.completions.create

        async def _patched_create(*a: Any, **kw: Any) -> Any:
            result = await original_create(*a, **kw)
            model_alias = kw.get("model", "")
            is_r1 = "thinking" in model_alias or "r1" in model_alias.lower()
            if hasattr(result, "choices") and is_r1:
                return await self._strip_completion(result)
            return result

        # Monkey-patch only for this instance — does not affect other clients
        self.chat.completions.create = _patched_create  # type: ignore[method-assign]


@lru_cache(maxsize=1)
def get_client() -> instructor.AsyncInstructor:
    """Return the shared Instructor client using JSON mode (primary)."""
    raw = ThinkStrippingAsyncOpenAI(
        base_url=LITELLM_BASE_URL,
        api_key=LITELLM_API_KEY,
    )
    return instructor.from_openai(raw, mode=instructor.Mode.JSON)


@lru_cache(maxsize=1)
def get_client_md_json() -> instructor.AsyncInstructor:
    """Return the shared Instructor client using MD_JSON mode (fallback)."""
    raw = ThinkStrippingAsyncOpenAI(
        base_url=LITELLM_BASE_URL,
        api_key=LITELLM_API_KEY,
    )
    return instructor.from_openai(raw, mode=instructor.Mode.MD_JSON)
