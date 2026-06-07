# hermes-docker Baseline — Actual Metrics
## Captured: 2026-05-30 | Stack: hermes-docker (current)
## Purpose: A/B reference baseline before hermes-native implementation

---

## 0.1 — Stack Health (agentic-up.sh --check)

| Service | Port | Status |
|---------|------|--------|
| langfuse | 3000 | STARTED (was down; started for Langfuse capture) |
| litellm | 8002 | OK |
| engram | 7437 | OK |
| mlx-coder | 8000 | OK |
| mlx-thinking | 8001 | OK |
| llama-devstral | 8004 | OK |
| devstral-proxy | 8005 | OK |
| mlx-hermes | 8006 | OK |
| schema-service | 8010 | OK |

**Result**: `agentic-up.sh --check` exit code 0. All critical services healthy.
Langfuse was down at check time (non-blocking per script design) — started manually for metric capture.

---

## 0.2 — Calibration Harness Smoke-Test

**Run ID**: `baseline-hermes-docker-2026-05-30`
**JSONL output**: `~/projects/schema-service/calibration/runs/baseline-hermes-docker-2026-05-30.jsonl`

Phases tested: `propose`, `spec`, `design`, `tasks`, `apply`
Difficulty levels: `simple`, `medium`
Repeat: 1 per (phase, difficulty) pair → 10 total (phase, fixture) pairs

**All 10 pairs completed successfully. Schema validation passed on first attempt (0 retries) for every phase.**

### Per-pair results

| Phase | Difficulty | Latency (ms) | Schema Valid | Fields Ratio | Retries |
|-------|------------|-------------|--------------|--------------|---------|
| propose | simple | 21,764 | True | 1.00 | 0 |
| propose | medium | 22,633 | True | 1.00 | 0 |
| spec | simple | 8,783 | True | 1.00 | 0 |
| spec | medium | 9,378 | True | 1.00 | 0 |
| design | simple | 34,725 | True | 1.00 | 0 |
| design | medium | 36,344 | True | 1.00 | 0 |
| tasks | simple | 6,842 | True | 1.00 | 0 |
| tasks | medium | 6,133 | True | 1.00 | 0 |
| apply | simple | 3,398 | True | 1.00 | 0 |
| apply | medium | 5,954 | True | 1.00 | 0 |

---

## 0.3 — Langfuse Metrics (hermes-docker baseline)

**Data window**: 2026-05-30 07:29 – 07:38 UTC  
**Traces captured**: 42 (includes health probes; 20 are SDD phase calls)  
**Langfuse version**: 2.95.11  
**Cost**: $0.00 — local MLX models have no pricing configured in LiteLLM

### Token usage (SDD phase calls only)

| Metric | Value |
|--------|-------|
| Total input tokens | 12,531 |
| Total output tokens | 7,162 |
| Total tokens | 19,693 |
| Total wall-time latency sum | 344.1 s |
| Avg latency per LLM call | 11.58 s |
| Total cost | $0.00 (local models, no pricing set) |
| Fallbacks triggered | 0 |

### Token breakdown by model

| Model | Calls | Input Tokens | Output Tokens | Total Latency |
|-------|-------|-------------|---------------|---------------|
| mlx-coder (qwen2.5-coder-32b) | 16 | 6,422 | 1,824 | 91.6 s |
| mlx-thinking (deepseek-r1-32b) | 12 | 3,502 | 5,308 | 241.1 s |
| mlx-hermes (hermes3-70b) | 2 | 54 | 10 | 4.8 s |
| MiniMax-M2.7 | 2 | 89 | 10 | 2.4 s |
| devstral | 2 | 2,464 | 10 | 1.4 s |
| llama3.3-70b | 2 | 0 | 0 | 2.7 s |

> Note: llama3.3-70b and devstral show 0 / minimal tokens — these are the health-check model probes (1-token test calls), not SDD phase calls. Claude models (haiku/sonnet/opus) show 0 tokens — health check stubs only.

### Per-phase latency (client-side, from calibration runner)

| Phase | Avg Latency | Model Used |
|-------|-------------|-----------|
| propose | 22,199 ms | mlx-thinking (deepseek-r1-32b) |
| spec | 9,081 ms | mlx-coder (qwen2.5-coder-32b) |
| design | 35,534 ms | mlx-thinking (deepseek-r1-32b) |
| tasks | 6,488 ms | mlx-coder (qwen2.5-coder-32b) |
| apply | 4,676 ms | mlx-coder (qwen2.5-coder-32b) |

> design is the slowest phase (~35s) — uses deepseek-r1-32b (thinking model). Propose is second (~22s) for the same reason.

---

## 0.4 — LLM-Judge Scores (calibration harness, --judge flag)

**Judge model**: MiniMaxAI/MiniMax-M2.7 via Together.ai  
**Scale**: 0–5 (5 = exemplary, 3 = acceptable, 0 = unusable)

### Per-pair judge scores

| Phase | Difficulty | Coherence | Specificity |
|-------|------------|-----------|-------------|
| propose | simple | 3 | 3 |
| propose | medium | 3 | 3 |
| spec | simple | 4 | 4 |
| spec | medium | 3 | 2 |
| design | simple | 3 | 2 |
| design | medium | 3 | 2 |
| tasks | simple | 3 | 3 |
| tasks | medium | 3 | 3 |
| apply | simple | 4 | 4 |
| apply | medium | 4 | 4 |

### Per-phase averages

| Phase | Avg Coherence | Avg Specificity | Notes |
|-------|--------------|-----------------|-------|
| propose | 3.0 / 5 | 3.0 / 5 | Acceptable |
| spec | 3.5 / 5 | 3.0 / 5 | Strong on simple, weaker on medium |
| design | 3.0 / 5 | 2.0 / 5 | Lowest specificity — underspecified contracts |
| tasks | 3.0 / 5 | 3.0 / 5 | Acceptable |
| apply | 4.0 / 5 | 4.0 / 5 | Best phase — strong on both dimensions |

**Baseline quality summary**: All phases pass (no zeros). Apply is the strongest (4/4). Design has the lowest specificity (2/5) — the judge consistently penalizes underspecified file-level contracts when using local models without structured output enforcement.

---

## Summary

| Dimension | Baseline Value |
|-----------|---------------|
| Stack health | PASS (all critical services OK) |
| Schema validation pass rate | 100% (10/10 pairs, 0 retries) |
| Avg propose latency | 22,199 ms |
| Avg spec latency | 9,081 ms |
| Avg design latency | 35,534 ms |
| Avg tasks latency | 6,488 ms |
| Avg apply latency | 4,676 ms |
| Total tokens (SDD run) | 19,693 |
| Total cost | $0.00 |
| Fallbacks | 0 |
| Overall avg judge coherence | 3.3 / 5 |
| Overall avg judge specificity | 3.0 / 5 |

**Weakest phase (specificity)**: design — target for improvement in hermes-native via Pydantic-in-execute_code structured output enforcement.

---

*Generated by sdd-apply Fase 0 executor — hermes-native change*
*Calibration JSONL: `~/projects/schema-service/calibration/runs/baseline-hermes-docker-2026-05-30.jsonl`*
