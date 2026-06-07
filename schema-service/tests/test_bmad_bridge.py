"""Tests for the ProposeIn BMAD bridge fields and _enrich_context ordering."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.propose import ProposeIn
from app.routes.sdd import _enrich_context
from app.schemas.spec import SpecIn


# ---------------------------------------------------------------------------
# ProposeIn BMAD field acceptance
# ---------------------------------------------------------------------------


def test_propose_in_accepts_bmad_fields():
    """ProposeIn must accept all 3 bmad_* optional fields."""
    payload = ProposeIn(
        context="a change",
        bmad_prd='{"overview":"PRD content"}',
        bmad_architect='{"architecture_overview":"Arch content"}',
        bmad_stories='{"epic":"Epic","stories":[]}',
    )
    assert payload.bmad_prd is not None
    assert payload.bmad_architect is not None
    assert payload.bmad_stories is not None


def test_propose_in_bmad_fields_default_none():
    """bmad_* fields default to None — not required."""
    payload = ProposeIn(context="a change")
    assert payload.bmad_prd is None
    assert payload.bmad_architect is None
    assert payload.bmad_stories is None


def test_propose_in_backward_compat_context_only():
    """Existing callers sending only context must still be valid."""
    payload = ProposeIn(context="x")
    assert payload.context == "x"


def test_propose_in_partial_bmad_fields():
    """Only some bmad_* fields present — must be valid, absent fields stay None."""
    payload = ProposeIn(context="x", bmad_prd='{"overview":"p"}')
    assert payload.bmad_prd is not None
    assert payload.bmad_architect is None
    assert payload.bmad_stories is None


# ---------------------------------------------------------------------------
# _enrich_context ordering — BMAD before SDD
# ---------------------------------------------------------------------------


def test_enrich_context_bmad_before_sdd_sections():
    """When all 3 bmad fields are present, BMAD sections must appear before SDD sections."""
    payload = ProposeIn(
        context="the change",
        bmad_prd='{"overview":"PRD content"}',
        bmad_architect='{"architecture_overview":"Arch content"}',
        bmad_stories='{"epic":"Epic","stories":[]}',
        exploration='{"summary":"Explore content"}',
    )
    enriched = _enrich_context(payload)

    idx_bmad_prd = enriched.index("## BMAD PRD")
    idx_bmad_arch = enriched.index("## BMAD Architecture")
    idx_bmad_stories = enriched.index("## BMAD Stories")
    idx_explore = enriched.index("## Explore Phase Output")

    assert idx_bmad_prd < idx_explore, "BMAD PRD must appear before Explore Phase Output"
    assert idx_bmad_arch < idx_explore, "BMAD Architecture must appear before Explore Phase Output"
    assert idx_bmad_stories < idx_explore, "BMAD Stories must appear before Explore Phase Output"
    assert idx_bmad_prd < idx_bmad_arch < idx_bmad_stories, (
        "BMAD sections must follow canonical order: prd, architect, stories"
    )


def test_enrich_context_no_bmad_labels_when_fields_absent():
    """When no bmad_* fields are present, no BMAD section labels appear in the output."""
    payload = ProposeIn(context="x")
    enriched = _enrich_context(payload)

    assert "## BMAD PRD" not in enriched
    assert "## BMAD Architecture" not in enriched
    assert "## BMAD Stories" not in enriched


def test_enrich_context_partial_bmad_only_populated_injected():
    """Only the populated bmad_* fields are injected — absent ones emit no section."""
    payload = ProposeIn(context="x", bmad_prd='{"overview":"p"}')
    enriched = _enrich_context(payload)

    assert "## BMAD PRD" in enriched
    assert "## BMAD Architecture" not in enriched
    assert "## BMAD Stories" not in enriched


def test_enrich_context_non_propose_payload_unchanged():
    """_enrich_context on a SpecIn (no bmad_* attrs) produces no BMAD sections — regression guard."""
    payload = SpecIn(context="spec context")
    enriched = _enrich_context(payload)

    assert "## BMAD PRD" not in enriched
    assert "## BMAD Architecture" not in enriched
    assert "## BMAD Stories" not in enriched
    # Base context must still be present
    assert "## Context" in enriched
    assert "spec context" in enriched
