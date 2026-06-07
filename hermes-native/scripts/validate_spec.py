"""
Pydantic validator for SDD 'spec' phase output.
Usage:
  python3 validate_spec.py --worker local-coder --prompt "..."
  echo '{"requirements":["..."]}' | python3 validate_spec.py --worker local-coder
  python3 validate_spec.py --worker local-coder --input '{"requirements":["..."]}'

Exit code 0: valid JSON returned to stdout.
Exit code 1: 3-attempt loop exhausted; error on stderr.
"""

import argparse
import json
import sys

try:
    from validate_base import validate_with_retry, ValidationFailure
except ImportError:
    import importlib.util, os
    spec = importlib.util.spec_from_file_location(
        "validate_base",
        os.path.join(os.path.dirname(__file__), "validate_base.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    validate_with_retry = mod.validate_with_retry
    ValidationFailure = mod.ValidationFailure

from pydantic import BaseModel, ConfigDict


class SpecOut(BaseModel):
    model_config = ConfigDict(extra="allow")

    requirements: list[str]
    scenarios: list[str]
    out_of_scope: list[str] = []


PHASE = "spec"


def main():
    parser = argparse.ArgumentParser(description="Validate SDD spec phase output")
    parser.add_argument("--worker", default="local-coder", help="LiteLLM alias")
    parser.add_argument("--prompt", default="", help="Prompt to send to LiteLLM (if no --input)")
    parser.add_argument("--input", default="", help="Pre-generated JSON string to validate")
    args = parser.parse_args()

    raw_json = None
    if args.input:
        raw_json = args.input
    elif not sys.stdin.isatty():
        raw_json = sys.stdin.read().strip()

    prompt = args.prompt or (
        "You are an SDD spec worker. Given the change context, produce a specification "
        "with fields: requirements (list[str]), scenarios (list[str]), out_of_scope (list[str]). "
        "Respond with valid JSON only."
    )

    try:
        result = validate_with_retry(
            phase=PHASE,
            worker=args.worker,
            schema_cls=SpecOut,
            prompt=prompt,
            raw_json=raw_json,
        )
        print(json.dumps(result))
        sys.exit(0)
    except ValidationFailure as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
