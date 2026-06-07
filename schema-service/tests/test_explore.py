"""Unit tests for the explore phase: schemas, registry entry, and route handler."""
from __future__ import annotations

import pytest
from pydantic import ValidationError
from unittest.mock import AsyncMock, patch

from app.schemas.explore import ExploreIn, ExploreOut, FileRef, Approach
from app.registry import PHASE_REGISTRY
from app.errors import ValidationExhausted


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


def test_explore_in_minimal_valid():
    payload = ExploreIn(context="some context text")
    assert payload.context == "some context text"


def test_explore_in_missing_context_raises():
    with pytest.raises(ValidationError):
        ExploreIn()  # type: ignore[call-arg]


def test_explore_out_minimal_valid():
    out = ExploreOut(
        summary="A brief summary.",
        current_state=["State one"],
        affected_files=[FileRef(path="app/foo.py", role="entry point")],
        approaches=[Approach(name="Approach A", pros=["pro1"], cons=["con1"])],
        risks=["Risk one"],
        recommendation="Use Approach A.",
        open_questions=["Question one?"],
    )
    assert out.summary == "A brief summary."
    assert len(out.current_state) == 1
    assert len(out.approaches) == 1


def test_explore_out_missing_field_raises():
    with pytest.raises(ValidationError):
        ExploreOut(
            # summary missing
            current_state=["state"],
            affected_files=[],
            approaches=[Approach(name="A", pros=["p"], cons=["c"])],
            risks=[],
            recommendation="Use A.",
            open_questions=[],
        )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


def test_registry_explore_entry_exists():
    assert "explore" in PHASE_REGISTRY, "PHASE_REGISTRY must contain an 'explore' entry"


def test_registry_explore_worker_alias():
    spec = PHASE_REGISTRY["explore"]
    assert spec.worker_alias == "local-hermes", (
        f"Expected worker_alias='local-hermes', got '{spec.worker_alias}'"
    )


def test_registry_explore_max_tokens():
    spec = PHASE_REGISTRY["explore"]
    assert spec.max_tokens == 4096, (
        f"Expected max_tokens=4096, got {spec.max_tokens}"
    )


def test_registry_explore_max_input_tokens():
    spec = PHASE_REGISTRY["explore"]
    assert spec.max_input_tokens == 28000, (
        f"Expected max_input_tokens=28000, got {spec.max_input_tokens}"
    )


def test_registry_explore_response_model():
    spec = PHASE_REGISTRY["explore"]
    assert spec.response_model is ExploreOut


# ---------------------------------------------------------------------------
# Route handler tests (mocked LLM)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_explore_route_returns_200_shape():
    """POST /v1/sdd/explore with a mocked _call_with_retry returns a valid ExploreOut."""
    from fastapi.testclient import TestClient
    from app.main import app

    expected_out = ExploreOut(
        summary="Exploration of the auth module.",
        current_state=["JWT tokens are HS256 signed"],
        affected_files=[FileRef(path="app/auth/jwt.py", role="token issuance")],
        approaches=[Approach(name="RS256 migration", pros=["public key shareable"], cons=["key management overhead"])],
        risks=["Key rotation requires coordinated deploys"],
        recommendation="Stay HS256 for now.",
        open_questions=["Do consumers outside this service need to verify tokens independently?"],
    )

    with patch("app.routes.sdd._call_with_retry", new=AsyncMock(return_value=expected_out)):
        with TestClient(app) as client:
            response = client.post(
                "/v1/sdd/explore",
                json={"context": "a short context brief"},
            )

    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert isinstance(data["current_state"], list)
    assert isinstance(data["approaches"], list)
    assert data["summary"] == "Exploration of the auth module."


@pytest.mark.asyncio
async def test_explore_route_422_on_missing_context():
    """POST /v1/sdd/explore without context returns 422."""
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        response = client.post("/v1/sdd/explore", json={})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_explore_route_422_on_validation_exhausted():
    """POST /v1/sdd/explore when _call_with_retry raises ValidationExhausted returns 422."""
    from fastapi.testclient import TestClient
    from app.main import app

    exc = ValidationExhausted(
        attempts=3,
        mode_history=["JSON", "JSON", "MD_JSON"],
        last_errors=[{"msg": "field required"}],
    )

    with patch("app.routes.sdd._call_with_retry", new=AsyncMock(side_effect=exc)):
        with TestClient(app) as client:
            response = client.post(
                "/v1/sdd/explore",
                json={"context": "some context"},
            )

    assert response.status_code == 422
    data = response.json()
    assert data.get("error") == "validation_failed"
    assert data.get("phase") == "explore"
