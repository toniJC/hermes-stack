"""Unit tests for BMAD phase routes: schemas, registry entries, and route handlers."""
from __future__ import annotations

import pytest
from pydantic import ValidationError
from unittest.mock import AsyncMock, patch

from app.registry import PHASE_REGISTRY
from app.errors import ValidationExhausted
from app.schemas.analyze import AnalyzeIn, AnalyzeOut
from app.schemas.prd import PRDIn, PRDOut, Requirement
from app.schemas.ux import UXIn, UXOut, UXFlow
from app.schemas.architect import ArchitectIn, ArchitectOut
from app.schemas.stories import StoriesIn, StoriesOut, Story


# ===========================================================================
# analyze
# ===========================================================================


class TestAnalyzeSchema:
    def test_analyze_in_minimal_valid(self):
        payload = AnalyzeIn(context="raw business idea")
        assert payload.context == "raw business idea"

    def test_analyze_in_missing_context_raises(self):
        with pytest.raises(ValidationError):
            AnalyzeIn()  # type: ignore[call-arg]

    def test_analyze_out_minimal_valid(self):
        out = AnalyzeOut(
            problem_statement="Users waste 3h/week on manual data entry.",
            target_users=["Small business owners"],
            goals=["Reduce manual entry to 0h/week"],
        )
        assert out.problem_statement == "Users waste 3h/week on manual data entry."
        assert len(out.target_users) == 1
        assert len(out.goals) == 1

    def test_analyze_out_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            AnalyzeOut(
                # problem_statement missing
                target_users=["Small business owners"],
                goals=["Reduce manual entry"],
            )  # type: ignore[call-arg]

    def test_analyze_out_target_users_min_length_raises(self):
        with pytest.raises(ValidationError):
            AnalyzeOut(
                problem_statement="A problem.",
                target_users=[],  # violates min_length=1
                goals=["A goal"],
            )

    def test_analyze_out_goals_min_length_raises(self):
        with pytest.raises(ValidationError):
            AnalyzeOut(
                problem_statement="A problem.",
                target_users=["A user"],
                goals=[],  # violates min_length=1
            )


class TestAnalyzeRegistry:
    def test_entry_exists(self):
        assert "analyze" in PHASE_REGISTRY

    def test_worker_alias(self):
        assert PHASE_REGISTRY["analyze"].worker_alias == "local-thinking"

    def test_max_tokens(self):
        assert PHASE_REGISTRY["analyze"].max_tokens == 3000

    def test_max_input_tokens(self):
        assert PHASE_REGISTRY["analyze"].max_input_tokens == 28000

    def test_response_model(self):
        assert PHASE_REGISTRY["analyze"].response_model is AnalyzeOut


class TestAnalyzeRoute:
    def _make_out(self) -> AnalyzeOut:
        return AnalyzeOut(
            problem_statement="Problem.",
            target_users=["User segment"],
            goals=["Goal one"],
        )

    @pytest.mark.asyncio
    async def test_returns_200_with_meta(self):
        from fastapi.testclient import TestClient
        from app.main import app

        with patch("app.routes.sdd._call_with_retry", new=AsyncMock(return_value=self._make_out())):
            with TestClient(app) as client:
                response = client.post("/v1/bmad/analyze", json={"context": "an idea"})

        assert response.status_code == 200
        data = response.json()
        assert data["_meta"]["phase"] == "analyze"
        assert "problem_statement" in data

    @pytest.mark.asyncio
    async def test_422_on_missing_context(self):
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            response = client.post("/v1/bmad/analyze", json={})

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_422_on_validation_exhausted(self):
        from fastapi.testclient import TestClient
        from app.main import app

        exc = ValidationExhausted(
            attempts=3,
            mode_history=["JSON", "JSON", "MD_JSON"],
            last_errors=[{"msg": "field required"}],
        )

        with patch("app.routes.sdd._call_with_retry", new=AsyncMock(side_effect=exc)):
            with TestClient(app) as client:
                response = client.post("/v1/bmad/analyze", json={"context": "an idea"})

        assert response.status_code == 422
        data = response.json()
        assert data.get("error") == "validation_failed"
        assert data.get("phase") == "analyze"


# ===========================================================================
# prd
# ===========================================================================


class TestPrdSchema:
    def test_prd_in_minimal_valid(self):
        payload = PRDIn(context="product context")
        assert payload.context == "product context"
        assert payload.analyze is None

    def test_prd_in_with_optional_analyze(self):
        payload = PRDIn(context="x", analyze='{"problem_statement":"p"}')
        assert payload.analyze is not None

    def test_prd_in_missing_context_raises(self):
        with pytest.raises(ValidationError):
            PRDIn()  # type: ignore[call-arg]

    def test_prd_out_minimal_valid(self):
        req = Requirement(id="FR-1", description="User can log in", priority="must")
        out = PRDOut(overview="A product overview.", functional_requirements=[req])
        assert out.overview == "A product overview."
        assert len(out.functional_requirements) == 1

    def test_prd_out_missing_overview_raises(self):
        req = Requirement(id="FR-1", description="Login", priority="must")
        with pytest.raises(ValidationError):
            PRDOut(functional_requirements=[req])  # type: ignore[call-arg]

    def test_prd_out_functional_requirements_min_length_raises(self):
        with pytest.raises(ValidationError):
            PRDOut(overview="Overview.", functional_requirements=[])

    def test_requirement_missing_field_raises(self):
        with pytest.raises(ValidationError):
            Requirement(id="FR-1", description="Login")  # type: ignore[call-arg]


class TestPrdRegistry:
    def test_entry_exists(self):
        assert "prd" in PHASE_REGISTRY

    def test_worker_alias(self):
        assert PHASE_REGISTRY["prd"].worker_alias == "local-thinking"

    def test_max_tokens(self):
        assert PHASE_REGISTRY["prd"].max_tokens == 3500

    def test_max_input_tokens(self):
        assert PHASE_REGISTRY["prd"].max_input_tokens == 28000

    def test_response_model(self):
        assert PHASE_REGISTRY["prd"].response_model is PRDOut


class TestPrdRoute:
    def _make_out(self) -> PRDOut:
        req = Requirement(id="FR-1", description="User can do X", priority="must")
        return PRDOut(overview="Product overview.", functional_requirements=[req])

    @pytest.mark.asyncio
    async def test_returns_200_with_meta(self):
        from fastapi.testclient import TestClient
        from app.main import app

        with patch("app.routes.sdd._call_with_retry", new=AsyncMock(return_value=self._make_out())):
            with TestClient(app) as client:
                response = client.post("/v1/bmad/prd", json={"context": "a brief"})

        assert response.status_code == 200
        data = response.json()
        assert data["_meta"]["phase"] == "prd"
        assert "overview" in data

    @pytest.mark.asyncio
    async def test_422_on_missing_context(self):
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            response = client.post("/v1/bmad/prd", json={})

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_422_on_validation_exhausted(self):
        from fastapi.testclient import TestClient
        from app.main import app

        exc = ValidationExhausted(
            attempts=3,
            mode_history=["JSON", "JSON", "MD_JSON"],
            last_errors=[{"msg": "field required"}],
        )

        with patch("app.routes.sdd._call_with_retry", new=AsyncMock(side_effect=exc)):
            with TestClient(app) as client:
                response = client.post("/v1/bmad/prd", json={"context": "a brief"})

        assert response.status_code == 422
        data = response.json()
        assert data.get("phase") == "prd"


# ===========================================================================
# ux
# ===========================================================================


class TestUxSchema:
    def test_ux_in_minimal_valid(self):
        payload = UXIn(context="product context")
        assert payload.context == "product context"
        assert payload.prd is None

    def test_ux_in_missing_context_raises(self):
        with pytest.raises(ValidationError):
            UXIn()  # type: ignore[call-arg]

    def test_ux_out_minimal_valid(self):
        flow = UXFlow(name="Login flow", steps=["User opens app", "User enters credentials"])
        out = UXOut(design_principles=["Minimal interruption"], user_flows=[flow])
        assert len(out.design_principles) == 1
        assert len(out.user_flows) == 1

    def test_ux_out_missing_design_principles_raises(self):
        flow = UXFlow(name="Login", steps=["Step 1"])
        with pytest.raises(ValidationError):
            UXOut(user_flows=[flow])  # type: ignore[call-arg]

    def test_ux_out_user_flows_min_length_raises(self):
        with pytest.raises(ValidationError):
            UXOut(design_principles=["Minimal"], user_flows=[])

    def test_ux_flow_steps_min_length_raises(self):
        with pytest.raises(ValidationError):
            UXFlow(name="Empty flow", steps=[])


class TestUxRegistry:
    def test_entry_exists(self):
        assert "ux" in PHASE_REGISTRY

    def test_worker_alias(self):
        assert PHASE_REGISTRY["ux"].worker_alias == "local-hermes"

    def test_max_tokens(self):
        assert PHASE_REGISTRY["ux"].max_tokens == 3000

    def test_max_input_tokens(self):
        assert PHASE_REGISTRY["ux"].max_input_tokens == 28000

    def test_response_model(self):
        assert PHASE_REGISTRY["ux"].response_model is UXOut


class TestUxRoute:
    def _make_out(self) -> UXOut:
        flow = UXFlow(name="Main flow", steps=["Open app", "Do thing"])
        return UXOut(design_principles=["Clarity"], user_flows=[flow])

    @pytest.mark.asyncio
    async def test_returns_200_with_meta(self):
        from fastapi.testclient import TestClient
        from app.main import app

        with patch("app.routes.sdd._call_with_retry", new=AsyncMock(return_value=self._make_out())):
            with TestClient(app) as client:
                response = client.post("/v1/bmad/ux", json={"context": "a product"})

        assert response.status_code == 200
        data = response.json()
        assert data["_meta"]["phase"] == "ux"
        assert "user_flows" in data

    @pytest.mark.asyncio
    async def test_422_on_missing_context(self):
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            response = client.post("/v1/bmad/ux", json={})

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_422_on_validation_exhausted(self):
        from fastapi.testclient import TestClient
        from app.main import app

        exc = ValidationExhausted(
            attempts=3,
            mode_history=["JSON", "JSON", "MD_JSON"],
            last_errors=[{"msg": "field required"}],
        )

        with patch("app.routes.sdd._call_with_retry", new=AsyncMock(side_effect=exc)):
            with TestClient(app) as client:
                response = client.post("/v1/bmad/ux", json={"context": "a product"})

        assert response.status_code == 422
        data = response.json()
        assert data.get("phase") == "ux"


# ===========================================================================
# architect
# ===========================================================================


class TestArchitectSchema:
    def test_architect_in_minimal_valid(self):
        payload = ArchitectIn(context="product context")
        assert payload.context == "product context"
        assert payload.prd is None
        assert payload.ux is None

    def test_architect_in_missing_context_raises(self):
        with pytest.raises(ValidationError):
            ArchitectIn()  # type: ignore[call-arg]

    def test_architect_out_minimal_valid(self):
        out = ArchitectOut(
            architecture_overview="A local-first macOS app.",
            components=["MenuBarController — owns the status bar icon"],
            tech_stack=["Swift 5.10 — native macOS"],
        )
        assert out.architecture_overview == "A local-first macOS app."
        assert len(out.components) == 1
        assert len(out.tech_stack) == 1

    def test_architect_out_missing_overview_raises(self):
        with pytest.raises(ValidationError):
            ArchitectOut(
                components=["Component A"],
                tech_stack=["Swift"],
            )  # type: ignore[call-arg]

    def test_architect_out_components_min_length_raises(self):
        with pytest.raises(ValidationError):
            ArchitectOut(
                architecture_overview="Overview.",
                components=[],
                tech_stack=["Swift"],
            )

    def test_architect_out_tech_stack_min_length_raises(self):
        with pytest.raises(ValidationError):
            ArchitectOut(
                architecture_overview="Overview.",
                components=["Component A"],
                tech_stack=[],
            )


class TestArchitectRegistry:
    def test_entry_exists(self):
        assert "architect" in PHASE_REGISTRY

    def test_worker_alias(self):
        assert PHASE_REGISTRY["architect"].worker_alias == "local-thinking"

    def test_max_tokens(self):
        assert PHASE_REGISTRY["architect"].max_tokens == 4096

    def test_max_input_tokens(self):
        assert PHASE_REGISTRY["architect"].max_input_tokens == 28000

    def test_response_model(self):
        assert PHASE_REGISTRY["architect"].response_model is ArchitectOut


class TestArchitectRoute:
    def _make_out(self) -> ArchitectOut:
        return ArchitectOut(
            architecture_overview="A local-first app.",
            components=["ServiceA — does X"],
            tech_stack=["Python — simple"],
        )

    @pytest.mark.asyncio
    async def test_returns_200_with_meta(self):
        from fastapi.testclient import TestClient
        from app.main import app

        with patch("app.routes.sdd._call_with_retry", new=AsyncMock(return_value=self._make_out())):
            with TestClient(app) as client:
                response = client.post("/v1/bmad/architect", json={"context": "a product"})

        assert response.status_code == 200
        data = response.json()
        assert data["_meta"]["phase"] == "architect"
        assert "architecture_overview" in data

    @pytest.mark.asyncio
    async def test_422_on_missing_context(self):
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            response = client.post("/v1/bmad/architect", json={})

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_422_on_validation_exhausted(self):
        from fastapi.testclient import TestClient
        from app.main import app

        exc = ValidationExhausted(
            attempts=3,
            mode_history=["JSON", "JSON", "MD_JSON"],
            last_errors=[{"msg": "field required"}],
        )

        with patch("app.routes.sdd._call_with_retry", new=AsyncMock(side_effect=exc)):
            with TestClient(app) as client:
                response = client.post("/v1/bmad/architect", json={"context": "a product"})

        assert response.status_code == 422
        data = response.json()
        assert data.get("phase") == "architect"


# ===========================================================================
# stories
# ===========================================================================


class TestStoriesSchema:
    def test_stories_in_minimal_valid(self):
        payload = StoriesIn(context="product context")
        assert payload.context == "product context"
        assert payload.prd is None
        assert payload.architect is None

    def test_stories_in_missing_context_raises(self):
        with pytest.raises(ValidationError):
            StoriesIn()  # type: ignore[call-arg]

    def test_stories_out_minimal_valid(self):
        story = Story(
            id="STORY-1",
            title="Implement OAuth",
            as_a="consultant",
            i_want="to connect my calendar",
            so_that="the app detects sessions",
            acceptance_criteria=["Given X, when Y, then Z"],
        )
        out = StoriesOut(epic="Calendar Connection", stories=[story])
        assert out.epic == "Calendar Connection"
        assert len(out.stories) == 1

    def test_stories_out_missing_epic_raises(self):
        story = Story(
            id="STORY-1",
            title="T",
            as_a="a",
            i_want="w",
            so_that="b",
            acceptance_criteria=["AC"],
        )
        with pytest.raises(ValidationError):
            StoriesOut(stories=[story])  # type: ignore[call-arg]

    def test_stories_out_min_length_raises(self):
        with pytest.raises(ValidationError):
            StoriesOut(epic="Epic", stories=[])

    def test_story_acceptance_criteria_min_length_raises(self):
        with pytest.raises(ValidationError):
            Story(
                id="STORY-1",
                title="T",
                as_a="a",
                i_want="w",
                so_that="b",
                acceptance_criteria=[],  # violates min_length=1
            )


class TestStoriesRegistry:
    def test_entry_exists(self):
        assert "stories" in PHASE_REGISTRY

    def test_worker_alias(self):
        assert PHASE_REGISTRY["stories"].worker_alias == "local-coder"

    def test_max_tokens(self):
        assert PHASE_REGISTRY["stories"].max_tokens == 4096

    def test_max_input_tokens(self):
        assert PHASE_REGISTRY["stories"].max_input_tokens == 28000

    def test_response_model(self):
        assert PHASE_REGISTRY["stories"].response_model is StoriesOut


class TestStoriesRoute:
    def _make_out(self) -> StoriesOut:
        story = Story(
            id="STORY-1",
            title="T",
            as_a="a",
            i_want="w",
            so_that="b",
            acceptance_criteria=["AC one"],
        )
        return StoriesOut(epic="Epic One", stories=[story])

    @pytest.mark.asyncio
    async def test_returns_200_with_meta(self):
        from fastapi.testclient import TestClient
        from app.main import app

        with patch("app.routes.sdd._call_with_retry", new=AsyncMock(return_value=self._make_out())):
            with TestClient(app) as client:
                response = client.post("/v1/bmad/stories", json={"context": "a product"})

        assert response.status_code == 200
        data = response.json()
        assert data["_meta"]["phase"] == "stories"
        assert "stories" in data

    @pytest.mark.asyncio
    async def test_422_on_missing_context(self):
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            response = client.post("/v1/bmad/stories", json={})

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_422_on_validation_exhausted(self):
        from fastapi.testclient import TestClient
        from app.main import app

        exc = ValidationExhausted(
            attempts=3,
            mode_history=["JSON", "JSON", "MD_JSON"],
            last_errors=[{"msg": "field required"}],
        )

        with patch("app.routes.sdd._call_with_retry", new=AsyncMock(side_effect=exc)):
            with TestClient(app) as client:
                response = client.post("/v1/bmad/stories", json={"context": "a product"})

        assert response.status_code == 422
        data = response.json()
        assert data.get("phase") == "stories"
