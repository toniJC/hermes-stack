🇪🇸 Español | [🇬🇧 English](README.md)

# schema-service

Middleware tipado entre el orquestador SDD y los workers LLM locales vía LiteLLM.

## Requisitos

- Python 3.11+
- LiteLLM corriendo en `localhost:8002` con aliases: `local-thinking`, `local-coder`, `local-hermes`
- Virtualenv en `/Users/pirito/projects/mlx-qwen/mlx_env/`

## Ejecución

```bash
cd /Users/pirito/projects/schema-service
/Users/pirito/projects/mlx-qwen/mlx_env/bin/uvicorn app.main:app \
    --host 127.0.0.1 --port 8010 --log-level info
```

## Smoke Tests

Con el servicio y LiteLLM corriendo:

```bash
/Users/pirito/projects/mlx-qwen/mlx_env/bin/python scripts/smoke.py
```

## Endpoints

| Método | Path | Descripción |
|--------|------|-------------|
| GET | /healthz | Control de liveness |
| POST | /v1/sdd/propose | Fase de propuesta SDD (DeepSeek R1) |
| POST | /v1/sdd/spec | Fase de spec SDD (Qwen Coder) |
| POST | /v1/sdd/tasks | Fase de tasks SDD (Qwen Coder) |
| POST | /v1/sdd/verify | Fase de verify SDD (Hermes 3) |

Todos los endpoints POST aceptan `{"context": "<string>"}` como payload mínimo.

## Estrategia de Reintentos

1. Intento 1: `instructor.Mode.JSON`
2. Intento 2: `instructor.Mode.MD_JSON`
3. Intento 3: `instructor.Mode.MD_JSON` con temperature -0.1

Al agotar los intentos → `422` con `ErrorEnvelope`.
