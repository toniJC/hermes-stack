"""Unit tests for the design phase: schemas, registry entry, and route handler."""
from __future__ import annotations

import pytest
from pydantic import ValidationError
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.design import DesignIn, DesignOut
from app.registry import PHASE_REGISTRY


# ---------------------------------------------------------------------------
# Task 4.1 — DesignIn / DesignOut validation
# ---------------------------------------------------------------------------


def test_design_in_minimal_valid():
    payload = DesignIn(context="some context text")
    assert payload.context == "some context text"


def test_design_in_missing_context_raises():
    with pytest.raises(ValidationError):
        DesignIn()  # type: ignore[call-arg]


def test_design_in_extra_fields_ignored():
    # Pydantic v2 default: extra fields are ignored, no error
    payload = DesignIn(context="ctx", unexpected_field="oops")  # type: ignore[call-arg]
    assert payload.context == "ctx"


def test_design_out_minimal_valid():
    out = DesignOut(
        approach="Mirror propose surface.",
        decisions=["D1: choice — rationale"],
        file_changes=["create app/schemas/design.py: DesignIn/DesignOut"],
        data_flow="1. Client calls /design. 2. Service calls R1.",
        testing_strategy=["Unit: schema validation — pytest"],
    )
    assert out.approach == "Mirror propose surface."
    assert len(out.decisions) == 1
    assert len(out.file_changes) == 1
    assert len(out.testing_strategy) == 1


def test_design_out_missing_field_raises():
    with pytest.raises(ValidationError):
        DesignOut(
            approach="x",
            decisions=[],
            # file_changes missing
            data_flow="y",
            testing_strategy=[],
        )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Task 4.2 — PHASE_REGISTRY["design"] entry assertions
# ---------------------------------------------------------------------------


def test_registry_design_entry_exists():
    assert "design" in PHASE_REGISTRY, "PHASE_REGISTRY must contain a 'design' entry"


def test_registry_design_worker_alias():
    spec = PHASE_REGISTRY["design"]
    assert spec.worker_alias == "local-thinking", (
        f"Expected worker_alias='local-thinking', got '{spec.worker_alias}'"
    )


def test_registry_design_max_input_tokens():
    spec = PHASE_REGISTRY["design"]
    assert spec.max_input_tokens == 28000, (
        f"Expected max_input_tokens=28000, got {spec.max_input_tokens}"
    )


def test_registry_design_max_tokens():
    spec = PHASE_REGISTRY["design"]
    assert spec.max_tokens == 3500, (
        f"Expected max_tokens=3500, got {spec.max_tokens}"
    )


def test_registry_propose_max_input_tokens():
    spec = PHASE_REGISTRY["propose"]
    assert spec.max_input_tokens == 32768, (
        f"Expected propose max_input_tokens=32768, got {spec.max_input_tokens}"
    )


# ---------------------------------------------------------------------------
# Task 4.3 — POST /v1/sdd/design route (mocked LiteLLM)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_design_route_returns_200_shape():
    """POST /v1/sdd/design with a mocked _call_with_retry returns a valid DesignOut."""
    from fastapi.testclient import TestClient
    from app.main import app

    expected_out = DesignOut(
        approach="Mirror propose.",
        decisions=["D: choice — why"],
        file_changes=["create schemas/design.py: schemas"],
        data_flow="1. Call design. 2. R1 responds.",
        testing_strategy=["Unit: validation — pytest"],
    )

    with patch("app.routes.sdd._call_with_retry", new=AsyncMock(return_value=expected_out)):
        with TestClient(app) as client:
            response = client.post(
                "/v1/sdd/design",
                json={"context": "a short context"},
            )

    assert response.status_code == 200
    data = response.json()
    assert "approach" in data
    assert isinstance(data["decisions"], list)
    assert isinstance(data["file_changes"], list)
    assert isinstance(data["testing_strategy"], list)
    assert data["approach"] == "Mirror propose."


@pytest.mark.asyncio
async def test_design_route_422_on_missing_context():
    """POST /v1/sdd/design without context returns 422."""
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        response = client.post("/v1/sdd/design", json={})

    assert response.status_code == 422
