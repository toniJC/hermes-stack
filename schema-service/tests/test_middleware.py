"""Unit tests for think-tag stripping and response headers."""
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.middleware import strip_think


def test_strips_single_block():
    assert strip_think("<think>reasoning</think>answer") == "answer"


def test_strips_multiline_block():
    assert strip_think("<think>\nline1\nline2\n</think>result") == "result"


def test_strips_multiple_blocks():
    assert strip_think("<think>a</think>mid<think>b</think>end") == "midend"


def test_case_insensitive():
    assert strip_think("<THINK>x</THINK>y") == "y"


def test_noop_on_clean_text():
    assert strip_think("no think tags here") == "no think tags here"


def test_noop_on_empty():
    assert strip_think("") == ""


# ---------------------------------------------------------------------------
# Middleware response header tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    app = create_app()
    return TestClient(app)


def test_x_sdd_retries_header_present(client):
    """X-SDD-Retries must be present and non-empty on any response."""
    resp = client.get("/healthz")
    assert "x-sdd-retries" in resp.headers, "X-SDD-Retries header missing"
    assert resp.headers["x-sdd-retries"] != "", "X-SDD-Retries header is empty"


def test_x_sdd_latency_ms_header_present(client):
    """X-SDD-Latency-Ms must be present and non-empty on any response."""
    resp = client.get("/healthz")
    assert "x-sdd-latency-ms" in resp.headers, "X-SDD-Latency-Ms header missing"
    assert resp.headers["x-sdd-latency-ms"] != "", "X-SDD-Latency-Ms header is empty"


def test_x_sdd_retries_is_integer(client):
    """X-SDD-Retries must be parseable as an integer."""
    resp = client.get("/healthz")
    value = resp.headers["x-sdd-retries"]
    assert int(value) >= 0, f"Expected non-negative int, got: {value!r}"


def test_x_sdd_latency_ms_is_numeric(client):
    """X-SDD-Latency-Ms must be parseable as a number."""
    resp = client.get("/healthz")
    value = resp.headers["x-sdd-latency-ms"]
    assert float(value) >= 0, f"Expected non-negative float, got: {value!r}"
