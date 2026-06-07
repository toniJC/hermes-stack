"""Unit tests for ErrorEnvelope field contract."""
from app.errors import ErrorEnvelope, ValidationExhausted


def test_error_envelope_fields():
    env = ErrorEnvelope(
        error="validation_failed",
        code="something went wrong",
        phase="propose",
        attempts=3,
        last_errors=[{"msg": "field required"}],
        request_id="abc",
    )
    data = env.model_dump()
    assert "code" in data
    assert "message" not in data
    assert "last_errors" in data
    assert "last_validation_errors" not in data


def test_validation_exhausted_stores_attempts():
    exc = ValidationExhausted(attempts=3, mode_history=["JSON", "JSON", "MD_JSON"], last_errors=[])
    assert exc.attempts == 3
    assert exc.mode_history[-1] == "MD_JSON"
