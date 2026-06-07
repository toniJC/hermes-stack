"""Tests for calibration/judge.py."""
from __future__ import annotations

import json
from typing import get_args
from unittest.mock import MagicMock, patch

import pytest

from calibration.fixtures import Phase
from calibration.judge import _PHASE_SYSTEM_PROMPTS, judge


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ALL_PHASES: tuple[str, ...] = get_args(Phase)

_VALID_VERDICT = json.dumps({
    "coherence_score": 4,
    "specificity_score": 3,
    "reasoning": "The artifact is well-structured but lacks specificity in one area.",
})


def _make_mock_client(raw_content: str = _VALID_VERDICT) -> MagicMock:
    """Return a mock OpenAI client whose completions.create returns *raw_content*."""
    message = MagicMock()
    message.content = raw_content

    choice = MagicMock()
    choice.message = message

    completion = MagicMock()
    completion.choices = [choice]

    client = MagicMock()
    client.chat.completions.create.return_value = completion
    return client


# ---------------------------------------------------------------------------
# T1 — Registry completeness: all 6 phases are registered
# ---------------------------------------------------------------------------

def test_registry_completeness():
    """Every Phase literal must be a key in _PHASE_SYSTEM_PROMPTS."""
    missing = [p for p in _ALL_PHASES if p not in _PHASE_SYSTEM_PROMPTS]
    assert missing == [], f"Phases missing from registry: {missing}"


# ---------------------------------------------------------------------------
# T2 — Prompt dispatch: correct system prompt used per phase
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("phase", _ALL_PHASES)
def test_prompt_dispatch(phase: str, monkeypatch: pytest.MonkeyPatch):
    """judge() must pass the phase-specific system prompt to the client."""
    mock_client = _make_mock_client()

    monkeypatch.setenv("TOGETHER_API_KEY", "test-key")

    with patch("calibration.judge.OpenAI", return_value=mock_client):
        judge(phase, context="ctx", response={})  # type: ignore[arg-type]

    call_kwargs = mock_client.chat.completions.create.call_args
    messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs["messages"]
    system_message = next(m for m in messages if m["role"] == "system")
    assert system_message["content"] == _PHASE_SYSTEM_PROMPTS[phase]


# ---------------------------------------------------------------------------
# T3 — Return shape: int scores and non-empty reasoning
# ---------------------------------------------------------------------------

def test_return_shape(monkeypatch: pytest.MonkeyPatch):
    """judge() must return coherence_score (int), specificity_score (int), reasoning (str)."""
    mock_client = _make_mock_client(_VALID_VERDICT)

    monkeypatch.setenv("TOGETHER_API_KEY", "test-key")

    with patch("calibration.judge.OpenAI", return_value=mock_client):
        result = judge("propose", context="ctx", response={})

    assert isinstance(result["coherence_score"], int)
    assert isinstance(result["specificity_score"], int)
    assert isinstance(result["reasoning"], str)
    assert len(result["reasoning"]) > 0


# ---------------------------------------------------------------------------
# T4 — Unknown phase raises ValueError with expected message
# ---------------------------------------------------------------------------

def test_unknown_phase_raises_value_error(monkeypatch: pytest.MonkeyPatch):
    """judge() on an unregistered phase must raise ValueError with 'No judge prompt registered'."""
    monkeypatch.setenv("TOGETHER_API_KEY", "test-key")

    with pytest.raises(ValueError, match="No judge prompt registered"):
        judge("nonexistent", context="ctx", response={})  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# T5 — max_tokens regression: must be 768
# ---------------------------------------------------------------------------

def test_max_tokens_is_768(monkeypatch: pytest.MonkeyPatch):
    """The client must be called with max_tokens=768 (not 512 or any other value)."""
    mock_client = _make_mock_client()

    monkeypatch.setenv("TOGETHER_API_KEY", "test-key")

    with patch("calibration.judge.OpenAI", return_value=mock_client):
        judge("propose", context="ctx", response={})

    call_kwargs = mock_client.chat.completions.create.call_args
    # Support both positional and keyword argument passing
    kwargs = call_kwargs.kwargs if call_kwargs.kwargs else {}
    assert kwargs.get("max_tokens") == 768, (
        f"Expected max_tokens=768 but got {kwargs.get('max_tokens')}"
    )
