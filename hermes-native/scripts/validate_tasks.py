"""
Pydantic validator for SDD 'tasks' phase output.
Usage:
  python3 validate_tasks.py --worker local-coder --prompt "..."
  echo '{"tasks":["..."]}' | python3 validate_tasks.py --worker local-coder
  python3 validate_tasks.py --worker local-coder --input '{"tasks":["..."]}'

Exit code 0: valid JSON returned to stdout.
Exit code 1: 3-attempt loop exhausted; error on stderr.
"""

import argparse
import json
import sys
from typing import Union

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


class TasksOut(BaseModel):
    model_config = ConfigDict(extra="allow")

    # Tasks can be a list of strings or list of dicts depending on model output
    tasks: list[Union[str, dict]]
    estimated_files: list[str] = []
    pr_risk: str = "low"


PHASE = "tasks"


def main():
    parser = argparse.ArgumentParser(description="Validate SDD tasks phase output")
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
        "You are an SDD tasks worker. Given the change context, produce an ordered task checklist "
        "with fields: tasks (list of task strings or dicts with id/title/status/acceptance), "
        "estimated_files (list[str]), pr_risk (low|medium|high). "
        "Respond with valid JSON only."
    )

    try:
        result = validate_with_retry(
            phase=PHASE,
            worker=args.worker,
            schema_cls=TasksOut,
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
