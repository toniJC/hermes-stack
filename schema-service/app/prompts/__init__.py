"""Prompt loader: reads phase system prompts from filesystem at startup."""
from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


def load_prompt(phase: str) -> str:
    """Load a phase system prompt from ``app/prompts/{phase}.txt``.

    Reads at call time (eager-load callers invoke this at module level so the
    process fails loudly on startup if any file is absent).

    Args:
        phase: Phase name, e.g. ``"explore"``.

    Returns:
        The prompt string with trailing newlines stripped.

    Raises:
        RuntimeError: If the expected ``.txt`` file does not exist.
    """
    path = _PROMPTS_DIR / f"{phase}.txt"
    if not path.exists():
        raise RuntimeError(f"Missing prompt file: {path}")
    return path.read_text(encoding="utf-8").rstrip("\n")
