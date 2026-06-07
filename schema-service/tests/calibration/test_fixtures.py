"""Tests for calibration/fixtures.py."""
import pytest

from calibration.fixtures import (
    Fixture,
    FIXTURES,
    Phase,
    get_fixtures,
)

_ALL_PHASES = ["propose", "spec", "design", "tasks", "verify", "explore"]
_VALID_DIFFICULTIES = {"simple", "medium", "complex"}


def test_all_phases_have_fixtures():
    """Scenario: All phases have fixtures — get_fixtures returns >= 1 per phase."""
    for phase in _ALL_PHASES:
        fixtures = get_fixtures(phase)  # type: ignore[arg-type]
        assert len(fixtures) >= 1, f"Phase '{phase}' has no fixtures"


def test_fixture_difficulty_in_valid_set():
    """Each fixture's difficulty must be in {simple, medium, complex}."""
    for phase in _ALL_PHASES:
        for fix in get_fixtures(phase):  # type: ignore[arg-type]
            assert fix.difficulty in _VALID_DIFFICULTIES, (
                f"Fixture '{fix.id}' has invalid difficulty '{fix.difficulty}'"
            )


def test_fixture_phase_matches_catalogue_key():
    """Each fixture's phase field must match its catalogue key."""
    for phase, fixtures in FIXTURES.items():
        for fix in fixtures:
            assert fix.phase == phase, (
                f"Fixture '{fix.id}' is under key '{phase}' but has phase='{fix.phase}'"
            )


def test_fixture_context_non_empty():
    """Every fixture context string must be non-empty."""
    for phase in _ALL_PHASES:
        for fix in get_fixtures(phase):  # type: ignore[arg-type]
            assert len(fix.context.strip()) > 0, (
                f"Fixture '{fix.id}' has an empty context string"
            )


def test_oversized_fixture_raises():
    """Scenario: Oversized fixture rejected — Fixture.__post_init__ raises ValueError."""
    oversized_context = "word " * 30_000  # well above the 28K token limit

    with pytest.raises(ValueError, match="exceeds.*token limit"):
        Fixture(
            id="test-oversized",
            phase="propose",
            difficulty="simple",
            context=oversized_context,
        )


def test_get_fixtures_unknown_phase_raises():
    """get_fixtures with an unknown phase raises KeyError."""
    with pytest.raises(KeyError):
        get_fixtures("unknown_phase")  # type: ignore[arg-type]
