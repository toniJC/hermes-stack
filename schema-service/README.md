# schema-service

Typed middleware between the SDD orchestrator and local LLM workers via LiteLLM.

## Requirements

- Python 3.11+
- LiteLLM running on `localhost:8002` with aliases: `local-thinking`, `local-coder`, `local-hermes`
- Virtualenv at `/Users/pirito/projects/mlx-qwen/mlx_env/`

## Run

```bash
cd /Users/pirito/projects/schema-service
/Users/pirito/projects/mlx-qwen/mlx_env/bin/uvicorn app.main:app \
    --host 127.0.0.1 --port 8010 --log-level info
```

## Smoke Tests

With the service and LiteLLM running:

```bash
/Users/pirito/projects/mlx-qwen/mlx_env/bin/python scripts/smoke.py
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /healthz | Liveness check |
| POST | /v1/sdd/propose | SDD proposal phase (DeepSeek R1) |
| POST | /v1/sdd/spec | SDD spec phase (Qwen Coder) |
| POST | /v1/sdd/tasks | SDD tasks phase (Qwen Coder) |
| POST | /v1/sdd/verify | SDD verify phase (Hermes 3) |

All POST endpoints accept `{"context": "<string>"}` as the minimum payload.

## Retry Strategy

1. Attempt 1: `instructor.Mode.JSON`
2. Attempt 2: `instructor.Mode.MD_JSON`
3. Attempt 3: `instructor.Mode.MD_JSON` with temperature -0.1

On exhaustion → `422` with `ErrorEnvelope`.
