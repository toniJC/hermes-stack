"""Tests for calibration/scorer.py."""
import pytest

from calibration.scorer import estimate_tokens, score


# ---------------------------------------------------------------------------
# Helper: build full valid responses per phase
# ---------------------------------------------------------------------------

def _full_propose() -> dict:
    return {
        "intent": "Add dark mode toggle to user settings page with localStorage persistence",
        "scope_in": ["dark mode CSS", "toggle component", "localStorage hook"],
        "scope_out": ["system theme detection", "per-component theme overrides"],
        "risks": ["WCAG contrast requirements", "flash of unstyled content on load"],
        "next_steps": ["create useTheme hook", "update CSS variables", "add toggle UI"],
    }


def _full_spec() -> dict:
    return {
        "requirements": ["toggle must persist across sessions", "support both themes"],
        "scenarios": ["user toggles to dark and reloads — dark persists"],
        "out_of_scope": ["system-level theme detection", "per-page overrides"],
    }


def _full_design() -> dict:
    return {
        "approach": "CSS custom properties with a data-theme attribute on document root controlled by React context",
        "decisions": ["use localStorage for persistence", "CSS variables over styled-components"],
        "file_changes": ["src/hooks/useTheme.ts", "src/components/ThemeToggle.tsx", "src/styles/tokens.css"],
        "testing_strategy": ["unit test hook", "snapshot test toggle", "axe accessibility check"],
        "data_flow": "User clicks toggle -> useTheme sets localStorage + updates context -> components re-render via CSS vars",
    }


def _full_tasks() -> dict:
    return {
        "tasks": ["Create useTheme hook", "Build ThemeToggle component", "Update CSS tokens"],
        "estimated_files": ["src/hooks/useTheme.ts", "src/components/ThemeToggle.tsx"],
        "pr_risk": "low",
    }


def _full_verify() -> dict:
    return {
        "status": "pass",
        "critical": ["placeholder critical item to satisfy non-empty list requirement"],
        "warnings": ["no E2E test for theme persistence"],
        "suggestions": ["add axe accessibility check to CI"],
    }


def _full_explore() -> dict:
    return {
        "summary": "Exploring caching options for the GET /products endpoint to reduce database load",
        "current_state": ["no caching", "200ms avg latency", "PostgreSQL on every request"],
        "affected_files": [
            {"path": "app/routes/products.py", "role": "endpoint"},
            {"path": "app/cache.py", "role": "new module"},
        ],
        "approaches": [
            {"name": "Redis cache-aside", "pros": ["fast", "simple"], "cons": ["cache invalidation"]},
            {"name": "In-process LRU", "pros": ["no network hop"], "cons": ["no TTL, memory bound"]},
        ],
        "risks": ["stale product data", "cache stampede on cold start"],
        "open_questions": ["what is the acceptable staleness window?"],
        "recommendation": "Use Redis cache-aside with a 60-second TTL and explicit invalidation on product updates",
    }


_FULL_RESPONSES = {
    "propose": _full_propose,
    "spec": _full_spec,
    "design": _full_design,
    "tasks": _full_tasks,
    "verify": _full_verify,
    "explore": _full_explore,
}


# ---------------------------------------------------------------------------
# Full output tests (ratio == 1.0)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("phase", ["propose", "spec", "design", "tasks", "verify", "explore"])
def test_full_output_ratio_is_1(phase: str):
    """Scenario: Full output scored — fields_present_ratio == 1.0."""
    response = _FULL_RESPONSES[phase]()
    scores = score(phase, response, latency_ms=100.0)  # type: ignore[arg-type]
    assert scores["fields_present_ratio"] == 1.0, (
        f"Expected 1.0 for {phase}, got {scores['fields_present_ratio']}"
    )


@pytest.mark.parametrize("phase", ["propose", "spec", "design", "tasks", "verify", "explore"])
def test_full_output_list_min_length_true(phase: str):
    """Scenario: Full output scored — list_min_length is True."""
    response = _FULL_RESPONSES[phase]()
    scores = score(phase, response, latency_ms=100.0)  # type: ignore[arg-type]
    assert scores["list_min_length"] is True


@pytest.mark.parametrize("phase", ["propose", "spec", "design", "tasks", "verify", "explore"])
def test_full_output_str_min_length_true(phase: str):
    """Scenario: Full output scored — str_min_length is True for phases with str fields."""
    response = _FULL_RESPONSES[phase]()
    scores = score(phase, response, latency_ms=100.0)  # type: ignore[arg-type]
    assert scores["str_min_length"] is True


# ---------------------------------------------------------------------------
# Partial output tests
# ---------------------------------------------------------------------------

def test_partial_propose_scope_out_empty():
    """Scenario: Partial output scored — scope_out=[] reduces ratio and list_min_length."""
    response = _full_propose()
    response["scope_out"] = []
    scores = score("propose", response, latency_ms=50.0)
    assert scores["fields_present_ratio"] < 1.0
    assert scores["list_min_length"] is False


def test_partial_spec_missing_requirements():
    """Missing requirements list gives ratio < 1.0."""
    response = _full_spec()
    del response["requirements"]
    scores = score("spec", response, latency_ms=50.0)
    assert scores["fields_present_ratio"] < 1.0


def test_partial_design_short_approach_string():
    """Approach string < 20 chars gives str_min_length=False."""
    response = _full_design()
    response["approach"] = "too short"  # < 20 chars
    scores = score("design", response, latency_ms=50.0)
    assert scores["str_min_length"] is False


# ---------------------------------------------------------------------------
# enum_valid tests
# ---------------------------------------------------------------------------

def test_enum_valid_null_for_propose():
    """Scenario: enum_valid is null for non-applicable phases (propose)."""
    scores = score("propose", _full_propose(), latency_ms=50.0)
    assert scores["enum_valid"] is None


def test_enum_valid_null_for_spec():
    scores = score("spec", _full_spec(), latency_ms=50.0)
    assert scores["enum_valid"] is None


def test_enum_valid_null_for_design():
    scores = score("design", _full_design(), latency_ms=50.0)
    assert scores["enum_valid"] is None


def test_enum_valid_null_for_explore():
    scores = score("explore", _full_explore(), latency_ms=50.0)
    assert scores["enum_valid"] is None


def test_enum_valid_true_for_tasks_low():
    scores = score("tasks", _full_tasks(), latency_ms=50.0)
    assert scores["enum_valid"] is True


def test_enum_valid_false_for_tasks_invalid():
    response = _full_tasks()
    response["pr_risk"] = "critical"  # not in {low,medium,high}
    scores = score("tasks", response, latency_ms=50.0)
    assert scores["enum_valid"] is False


def test_enum_valid_true_for_verify_pass():
    scores = score("verify", _full_verify(), latency_ms=50.0)
    assert scores["enum_valid"] is True


def test_enum_valid_false_for_verify_invalid():
    response = _full_verify()
    response["status"] = "unknown"
    scores = score("verify", response, latency_ms=50.0)
    assert scores["enum_valid"] is False


# ---------------------------------------------------------------------------
# approach_count tests
# ---------------------------------------------------------------------------

def test_approach_count_null_for_non_explore():
    """Scenario: approach_count is null for non-explore phases."""
    for phase, builder in _FULL_RESPONSES.items():
        if phase == "explore":
            continue
        scores = score(phase, builder(), latency_ms=50.0)  # type: ignore[arg-type]
        assert scores["approach_count"] is None, (
            f"Expected approach_count=None for phase '{phase}', got {scores['approach_count']}"
        )


def test_approach_count_true_for_explore_with_2():
    scores = score("explore", _full_explore(), latency_ms=50.0)
    assert scores["approach_count"] is True


def test_approach_count_false_for_explore_with_1():
    response = _full_explore()
    response["approaches"] = [response["approaches"][0]]
    scores = score("explore", response, latency_ms=50.0)
    assert scores["approach_count"] is False


# ---------------------------------------------------------------------------
# coherence / specificity default to None
# ---------------------------------------------------------------------------

def test_judge_scores_default_null():
    """coherence_score and specificity_score must be None without --judge."""
    scores = score("propose", _full_propose(), latency_ms=50.0)
    assert scores["coherence_score"] is None
    assert scores["specificity_score"] is None


# ---------------------------------------------------------------------------
# Token estimation smoke test
# ---------------------------------------------------------------------------

def test_estimate_tokens_nonzero():
    count = estimate_tokens("Hello world this is a test sentence for token counting")
    assert count > 0
