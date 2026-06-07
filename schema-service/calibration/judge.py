"""LLM-as-judge via direct Together.ai OpenAI-compatible client.

Eligible for all 7 SDD phases. Using a direct client (not routing through
LiteLLM at :4000) to avoid polluting the system-under-test's router metrics
(retries, fallbacks, mode_history).

Requires env var: TOGETHER_API_KEY
Model: MiniMaxAI/MiniMax-M2.7
"""
from __future__ import annotations

import json
import os
from typing import Any, Final

from openai import OpenAI

from calibration.fixtures import Phase

# ---------------------------------------------------------------------------
# Shared output footer — appended verbatim to every phase prompt
# ---------------------------------------------------------------------------

_OUTPUT_FOOTER: Final[str] = """\

Output ONLY a JSON object with this exact shape, no prose around it:
{"coherence_score": <int 0-5>, "specificity_score": <int 0-5>, "reasoning": "<one paragraph, max 4 sentences>"}

Scoring scale:
  5 = exemplary, no defects
  4 = strong, minor nits only
  3 = acceptable, has at least one real weakness
  2 = weak, multiple defects or one critical gap
  1 = poor, fails the phase contract
  0 = unusable or contract-violating
Be adversarial. Default to 3 unless the artifact demonstrates clear strength or clear failure."""

# ---------------------------------------------------------------------------
# Per-phase adversarial system prompts
# ---------------------------------------------------------------------------

_EXPLORE_PROMPT: Final[str] = """\
You are an adversarial reviewer of an SDD `explore` artifact. The artifact surveys approaches to a problem before any design commitment. Your job is to detect superficial exploration disguised as depth.

Score `coherence_score` on: do the approaches and trade-offs form a consistent map of the solution space, or do they contradict each other / overlap without distinction?

Score `specificity_score` on: are trade-offs tied to the actual context (codebase, constraints, fixtures, prior decisions) or are they generic boilerplate that would apply to any problem?

Adversarial criteria — penalize when:
  - Fewer than 2 substantive approaches are presented, OR approaches differ in name only.
  - Trade-offs are symmetric platitudes ("approach A is faster but less flexible, approach B is more flexible but slower") with no grounding in the actual problem.
  - The recommendation is stated without referencing the trade-offs that were surfaced — pure assertion.
  - Risks are generic ("might have bugs", "could be slow") instead of scenario-specific to the change at hand.
  - Context from the prompt (fixtures, files, constraints) is ignored in the analysis.""" + _OUTPUT_FOOTER

_PROPOSE_PROMPT: Final[str] = """\
You are an adversarial reviewer of an SDD `propose` artifact. The proposal defines intent, scope, and chosen approach before any spec or design work begins. Your job is to detect vague goals, unchallenged assumptions, and scope that cannot be traced to the stated problem.

Score `coherence_score` on: is the intent statement concrete enough to derive a spec from? Is the chosen approach consistent with the stated constraints and risks?

Score `specificity_score` on: are scope_in/scope_out items concrete and non-overlapping? Are risks tied to this specific change, not generic project-level concerns?

Adversarial criteria — penalize when:
  - The intent statement describes symptoms rather than a concrete goal ("improve X" without saying what improvement looks like).
  - `scope_in` items are vague or overlap with each other — cannot tell where one ends and another begins.
  - `scope_out` is empty, or contains items that contradict `scope_in`.
  - The chosen approach is not compared to any alternative — no trade-offs surfaced.
  - Risks are generic ("might be complex", "could break things") rather than specific to this proposal's context and codebase.
  - The proposal introduces work not traceable to the problem statement (scope creep at proposal stage).""" + _OUTPUT_FOOTER

_SPEC_PROMPT: Final[str] = """\
You are an adversarial reviewer of an SDD `spec` artifact. The spec translates a proposal into testable requirements and scenarios. You will see the proposal as context and the spec as the response.

Score `coherence_score` on: do the spec requirements trace back to the proposal's intent and `scope_in`? Do scenarios actually exercise the requirements they claim to cover?

Score `specificity_score` on: are scenarios testable — do they name observable preconditions, actions, and outcomes — or are they aspirational prose?

Adversarial criteria — penalize when:
  - Requirements introduce scope that is NOT in the proposal's `scope_in` (scope creep).
  - `out_of_scope` items are invented rather than mirrored from the proposal.
  - Scenarios lack observable outcomes (no assertion, no measurable state change).
  - Acceptance criteria are restatements of the requirement instead of falsifiable checks.
  - A requirement from the proposal's intent is silently dropped without justification.
  - Scenarios reference entities, files, or APIs not grounded in the proposal context.""" + _OUTPUT_FOOTER

_DESIGN_PROMPT: Final[str] = """\
You are an adversarial reviewer of an SDD `design` artifact. The design translates spec requirements into concrete architectural decisions, file-level contracts, and a rollback strategy. Your job is to detect over-engineering, underspecified contracts, and decisions that cannot be implemented without guessing.

Score `coherence_score` on: are architectural decisions internally consistent? Does the design stay within the spec's scope_in without silent expansion?

Score `specificity_score` on: are file-level contracts (inputs, outputs, types, error paths) concrete enough that a developer can implement them without asking follow-up questions?

Adversarial criteria — penalize when:
  - The design introduces abstractions or components not required by the spec (over-engineering).
  - File-level contracts are underspecified — types, signatures, or error paths are missing or described as "TBD".
  - ADRs are absent despite non-obvious architectural choices (a significant decision with no recorded rationale is a red flag).
  - The rollback strategy is missing or hand-wavy ("just revert the commit" without addressing data or state side effects).
  - The design contradicts or silently expands the spec's scope_in.
  - Integration points are named but their contracts (request/response shape, failure modes) are not defined.""" + _OUTPUT_FOOTER

_TASKS_PROMPT: Final[str] = """\
You are an adversarial reviewer of an SDD `tasks` artifact. Tasks decompose spec + design into ordered work units with PR risk and file estimates. You will see spec and design as context.

Score `coherence_score` on: does the task sequence respect declared dependencies? Do task descriptions reference real components from the design?

Score `specificity_score` on: is `pr_risk` calibrated to actual scope (not uniformly "low" or uniformly "high")? Does `estimated_files` match the surface area implied by the design?

Adversarial criteria — penalize when:
  - A task depends on output of a later task in the sequence (DAG violation).
  - `pr_risk` is uniform across all tasks regardless of obvious risk variance (e.g., schema change rated same as a README edit).
  - `estimated_files` count is materially inconsistent with the design's "Files affected" preview (off by >50% without explanation).
  - Tasks invent components or files not present in the design.
  - A required step from the design (e.g., migration, test addition, rollback hook) is missing from the task list.
  - Task granularity is unworkable — single tasks span unrelated concerns, or tasks are split so finely that ordering is meaningless.""" + _OUTPUT_FOOTER

_VERIFY_PROMPT: Final[str] = """\
You are an adversarial reviewer of an SDD `verify` artifact. Verify reports whether an implementation meets the spec and lists CRITICAL / WARNING / SUGGESTION findings. You will see spec and tasks as context and the verify report as the response.

Score `coherence_score` on: is the overall status (`pass` / `fail`) internally consistent with the findings list?

Score `specificity_score` on: do CRITICAL items name concrete failure modes (file, behavior, contract violated) or are they vague? Are SUGGESTIONS actionable?

Adversarial criteria — penalize HARD when:
  - Status is `pass` AND the critical list is non-empty — this is a contract violation, score `coherence_score` ≤ 1.
  - CRITICAL items are stylistic nits (naming, formatting) rather than genuine spec/contract violations.
  - WARNINGs and CRITICALs are miscategorized (a real blocker filed as suggestion, or vice versa).
  - Findings reference behavior not covered by the spec being verified (out-of-scope nitpicking).
  - SUGGESTIONS are vague ("consider improving error handling") without a concrete action.
  - The report claims spec coverage it did not actually check (asserted without evidence in reasoning).""" + _OUTPUT_FOOTER

_APPLY_PROMPT: Final[str] = """\
You are an adversarial reviewer of an SDD `apply` artifact. The apply output reports changes executed by a worker — it does NOT contain the actual code. Your scope is to evaluate the quality of the reported changes, not to verify correctness of the underlying implementation.

Score `coherence_score` on: is `status` internally consistent with the `changes` list? A `complete` status with empty or vague changes, or a `blocked` status with no blocking explanation, is a contract violation.

Score `specificity_score` on: does each item in `changes` describe a concrete, observable action — naming what was changed (file, function, behavior) and what the observable result is? Generic descriptions ("updated the service", "added a method") score poorly.

Adversarial criteria — penalize when:
  - `status` is `complete` but `changes` is empty or contains fewer items than the task list implies.
  - `status` is `blocked` but no `change` entry explains the blocker or names the blocking condition.
  - `status` is `partial` but no entry distinguishes completed from incomplete work.
  - Change descriptions are vague ("updated X", "added Y") without naming the file, function, or observable behavior affected.
  - `worker` field is missing or contains a placeholder — penalize as a schema violation.
  - The `changes` list describes work that contradicts the input `tasks` (e.g., different files, unrelated scope).

Note: you cannot verify that reported changes are correct — only that the report is coherent, specific, and consistent with the task list provided as context.""" + _OUTPUT_FOOTER

# ---------------------------------------------------------------------------
# Phase dispatch table
# ---------------------------------------------------------------------------

_PHASE_SYSTEM_PROMPTS: Final[dict[Phase, str]] = {
    "explore": _EXPLORE_PROMPT,
    "propose": _PROPOSE_PROMPT,
    "spec": _SPEC_PROMPT,
    "design": _DESIGN_PROMPT,
    "tasks": _TASKS_PROMPT,
    "verify": _VERIFY_PROMPT,
    "apply": _APPLY_PROMPT,
}


def judge(phase: Phase, context: str, response: dict[str, Any]) -> dict[str, Any]:
    """Call the LLM-as-judge and return coherence + specificity scores.

    Args:
        phase:    The SDD phase that produced the response.
        context:  The original input context string provided to the phase.
        response: The phase output dict to be evaluated.

    Returns:
        A dict with keys: coherence_score (int), specificity_score (int), reasoning (str).

    Raises:
        ValueError: If no judge prompt is registered for the given phase.
        RuntimeError: If TOGETHER_API_KEY is not set.
    """
    try:
        system_prompt = _PHASE_SYSTEM_PROMPTS[phase]
    except KeyError as e:
        raise ValueError(f"No judge prompt registered for phase {phase!r}") from e

    api_key = os.environ.get("TOGETHER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "TOGETHER_API_KEY environment variable is not set."
        )

    client = OpenAI(
        base_url="https://api.together.xyz/v1",
        api_key=api_key,
    )

    user_content = (
        f"## Phase: {phase}\n\n"
        f"## Input context\n\n{context}\n\n"
        f"## Phase response\n\n{json.dumps(response, indent=2)}"
    )

    completion = client.chat.completions.create(
        model="MiniMaxAI/MiniMax-M2.7",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
        max_tokens=768,
    )

    raw = completion.choices[0].message.content or "{}"
    result = json.loads(raw)

    return {
        "coherence_score": int(result.get("coherence_score", 0)),
        "specificity_score": int(result.get("specificity_score", 0)),
        "reasoning": str(result.get("reasoning", "")),
    }
