"""
Unit tests for SDD Pydantic validators.
Tests the validate_base retry/abort behavior directly (no LiteLLM calls needed
for the validation path — only the raw_json validation route is exercised).

Run: python3 test_validators.py
Exit code 0: all tests pass.
Exit code 1: one or more tests failed.
"""

import importlib.util
import json
import os
import sys
import traceback

# Load validate_base from same directory
_here = os.path.dirname(os.path.abspath(__file__))

def _load_module(name: str):
    path = os.path.join(_here, f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

base = _load_module("validate_base")
validate_with_retry = base.validate_with_retry
ValidationFailure = base.ValidationFailure

from pydantic import BaseModel, ConfigDict


class SimpleOut(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    count: int


PASS = 0
FAIL = 0

def ok(label: str):
    global PASS
    PASS += 1
    print(f"  PASS  {label}")

def fail(label: str, reason: str):
    global FAIL
    FAIL += 1
    print(f"  FAIL  {label}: {reason}")


# ─── Test 1: Valid JSON accepted on first try (no LiteLLM call) ───────────────

def test_valid_json_accepted_first_try():
    raw = '{"name": "hermes", "count": 42}'
    result = validate_with_retry(
        phase="test",
        worker="local-coder",
        schema_cls=SimpleOut,
        prompt="unused",
        raw_json=raw,
    )
    assert result["name"] == "hermes", f"name mismatch: {result}"
    assert result["count"] == 42, f"count mismatch: {result}"
    ok("valid JSON accepted on first try, no LiteLLM call")

try:
    test_valid_json_accepted_first_try()
except Exception as exc:
    fail("valid JSON accepted on first try", str(exc))


# ─── Test 2: Extra fields allowed (model_config extra=allow) ─────────────────

def test_extra_fields_allowed():
    raw = '{"name": "hermes", "count": 1, "extra_field": "should_pass"}'
    result = validate_with_retry(
        phase="test",
        worker="local-coder",
        schema_cls=SimpleOut,
        prompt="unused",
        raw_json=raw,
    )
    assert result["name"] == "hermes"
    ok("extra fields allowed (extra='allow')")

try:
    test_extra_fields_allowed()
except Exception as exc:
    fail("extra fields allowed", str(exc))


# ─── Test 3: Invalid JSON (bad syntax) causes retry loop ─────────────────────
# We monkey-patch _litellm_call to simulate 3 consecutive failures.

def test_malformed_json_retries_3_times():
    call_count = [0]
    original_call = base._litellm_call

    def mock_fail(worker, messages, attempt):
        call_count[0] += 1
        return "not json at all"

    base._litellm_call = mock_fail
    try:
        validate_with_retry(
            phase="test",
            worker="local-coder",
            schema_cls=SimpleOut,
            prompt="dummy",
            raw_json=None,  # force LiteLLM path
        )
        fail("malformed JSON retries 3 times", "expected ValidationFailure but got success")
    except ValidationFailure as exc:
        assert exc.attempt == 3, f"expected attempt=3, got {exc.attempt}"
        assert exc.phase == "test"
        assert exc.worker == "local-coder"
        assert call_count[0] == 3, f"expected 3 LiteLLM calls, got {call_count[0]}"
        ok(f"malformed JSON retried {call_count[0]} times then raised ValidationFailure(attempt=3)")
    except Exception as exc:
        fail("malformed JSON retries 3 times", f"unexpected exception: {exc}")
    finally:
        base._litellm_call = original_call

test_malformed_json_retries_3_times()


# ─── Test 4: Missing required field causes retry ──────────────────────────────

def test_missing_required_field_retries():
    call_count = [0]
    original_call = base._litellm_call

    def mock_missing_field(worker, messages, attempt):
        call_count[0] += 1
        # valid JSON but missing 'count' required field
        return '{"name": "hermes"}'

    base._litellm_call = mock_missing_field
    try:
        validate_with_retry(
            phase="test",
            worker="local-coder",
            schema_cls=SimpleOut,
            prompt="dummy",
            raw_json=None,
        )
        fail("missing required field retries", "expected ValidationFailure but got success")
    except ValidationFailure as exc:
        assert exc.attempt == 3, f"expected attempt=3, got {exc.attempt}"
        assert call_count[0] == 3, f"expected 3 calls, got {call_count[0]}"
        ok(f"missing required field: retried {call_count[0]} times then raised ValidationFailure")
    except Exception as exc:
        fail("missing required field retries", f"unexpected: {exc}")
    finally:
        base._litellm_call = original_call

test_missing_required_field_retries()


# ─── Test 5: Succeeds on 2nd attempt ─────────────────────────────────────────

def test_succeeds_on_second_attempt():
    call_count = [0]
    original_call = base._litellm_call

    def mock_second_attempt(worker, messages, attempt):
        call_count[0] += 1
        if call_count[0] == 1:
            return "bad json"
        return '{"name": "retry-success", "count": 7}'

    base._litellm_call = mock_second_attempt
    try:
        result = validate_with_retry(
            phase="test",
            worker="local-coder",
            schema_cls=SimpleOut,
            prompt="dummy",
            raw_json=None,
        )
        assert result["name"] == "retry-success"
        assert result["count"] == 7
        assert call_count[0] == 2, f"expected 2 calls, got {call_count[0]}"
        ok(f"succeeds on 2nd attempt after 1 failure ({call_count[0]} LiteLLM calls)")
    except Exception as exc:
        fail("succeeds on 2nd attempt", str(exc))
    finally:
        base._litellm_call = original_call

test_succeeds_on_second_attempt()


# ─── Test 6: MD_JSON extraction on attempt 3 ─────────────────────────────────

def test_md_json_extracted_on_attempt_3():
    call_count = [0]
    original_call = base._litellm_call

    def mock_md_json(worker, messages, attempt):
        call_count[0] += 1
        if call_count[0] <= 2:
            return "prose response without JSON"
        # Attempt 3: MD_JSON format
        return '```json\n{"name": "from-md", "count": 99}\n```'

    base._litellm_call = mock_md_json
    try:
        result = validate_with_retry(
            phase="test",
            worker="local-coder",
            schema_cls=SimpleOut,
            prompt="dummy",
            raw_json=None,
        )
        assert result["name"] == "from-md"
        assert result["count"] == 99
        assert call_count[0] == 3, f"expected 3 calls, got {call_count[0]}"
        ok(f"MD_JSON extraction succeeded on attempt 3 ({call_count[0]} LiteLLM calls)")
    except Exception as exc:
        fail("MD_JSON extraction on attempt 3", str(exc))
    finally:
        base._litellm_call = original_call

test_md_json_extracted_on_attempt_3()


# ─── Test 7: ValidationFailure has correct structured fields ──────────────────

def test_validation_failure_structured():
    original_call = base._litellm_call
    base._litellm_call = lambda w, m, a: "not json"
    try:
        validate_with_retry("spec", "local-coder", SimpleOut, "prompt", None)
        fail("ValidationFailure structured", "expected exception not raised")
    except ValidationFailure as exc:
        payload = json.loads(str(exc))
        assert payload["phase"] == "spec"
        assert payload["worker"] == "local-coder"
        assert payload["attempt"] == 3
        assert "last_error" in payload
        ok("ValidationFailure contains {phase, worker, attempt, last_error}")
    except Exception as exc:
        fail("ValidationFailure structured", str(exc))
    finally:
        base._litellm_call = original_call

test_validation_failure_structured()


# ─── Test 8: ProposalOut schema validation ────────────────────────────────────

def test_proposal_schema():
    prop = _load_module("validate_propose")
    raw = json.dumps({
        "intent": "Add dark mode",
        "scope_in": ["Toggle button"],
        "scope_out": ["Other features"],
        "risks": ["CSS conflicts"],
        "next_steps": ["Design CSS"],
    })
    result = validate_with_retry("propose", "local-thinking", prop.ProposalOut, "p", raw)
    assert result["intent"] == "Add dark mode"
    ok("ProposalOut: valid schema accepted")

try:
    test_proposal_schema()
except Exception as exc:
    fail("ProposalOut schema", str(exc))


# ─── Test 9: SpecOut schema validation ───────────────────────────────────────

def test_spec_schema():
    spe = _load_module("validate_spec")
    raw = json.dumps({
        "requirements": ["System must do X"],
        "scenarios": ["User does Y"],
        "out_of_scope": ["Z"],
    })
    result = validate_with_retry("spec", "local-coder", spe.SpecOut, "p", raw)
    assert len(result["requirements"]) == 1
    ok("SpecOut: valid schema accepted")

try:
    test_spec_schema()
except Exception as exc:
    fail("SpecOut schema", str(exc))


# ─── Test 10: DesignOut schema validation ─────────────────────────────────────

def test_design_schema():
    des = _load_module("validate_design")
    raw = json.dumps({
        "approach": "Use Redis",
        "decisions": [{"title": "Cache layer", "choice": "Redis", "rationale": "Fast"}],
    })
    result = validate_with_retry("design", "local-thinking", des.DesignOut, "p", raw)
    assert result["approach"] == "Use Redis"
    ok("DesignOut: valid schema accepted")

try:
    test_design_schema()
except Exception as exc:
    fail("DesignOut schema", str(exc))


# ─── Test 11: TasksOut schema validation ─────────────────────────────────────

def test_tasks_schema():
    tas = _load_module("validate_tasks")
    raw = json.dumps({
        "tasks": ["Create file X", "Add test Y"],
        "estimated_files": ["app/x.py"],
        "pr_risk": "low",
    })
    result = validate_with_retry("tasks", "local-coder", tas.TasksOut, "p", raw)
    assert len(result["tasks"]) == 2
    ok("TasksOut: valid schema accepted")

try:
    test_tasks_schema()
except Exception as exc:
    fail("TasksOut schema", str(exc))


# ─── Test 12: ApplyOut schema validation ─────────────────────────────────────

def test_apply_schema():
    apl = _load_module("validate_apply")
    raw = json.dumps({
        "changes": ["Created file A", "Modified file B"],
        "status": "complete",
        "notes": "Done",
    })
    result = validate_with_retry("apply", "local-coder", apl.ApplyOut, "p", raw)
    assert result["status"] == "complete"
    ok("ApplyOut: valid schema accepted")

try:
    test_apply_schema()
except Exception as exc:
    fail("ApplyOut schema", str(exc))


# ─── Summary ──────────────────────────────────────────────────────────────────
print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
