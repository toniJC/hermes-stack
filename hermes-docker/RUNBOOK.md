🇪🇸 Español | [🇬🇧 English](RUNBOOK.en.md)

# Local Agentic Stack — Runbook

HermesAgent (Docker) orquesta flujos de trabajo SDD usando MiniMax M2.7 como LLM principal. Delega cada fase SDD a modelos MLX locales a través de Schema Service (:8010) y LiteLLM (:8002). Los artefactos se persisten en Engram (:7437). Todas las requests LiteLLM se observan en Langfuse (:3000).

---

## Architecture

```
User
  │  Spotlight → HermesAgent.app  (selecciona workspace)
  ▼
HermesAgent (Docker container)
  LLM: MiniMax M2.7 via Together.ai API
  Config: hermes-config/config.yaml
  SOUL.md: hermes-config/soul.md (bind-mounted :ro)
  Dashboard web: http://localhost:9119  (--tui habilitado)
  Workspace: /workspace/<project> (montado dinámicamente)
  HERMES_PROJECT: <basename del workspace>
  │
  │  ┌──────────────────────────────────────────────────────────────────┐
  │  │  BMAD Planning Layer (idea → structured requirements)            │
  │  │  curl POST /v1/bmad/analyze                                      │
  │  │  curl POST /v1/bmad/prd                                          │
  │  │  curl POST /v1/bmad/ux  (optional — UI/UX changes only)          │
  │  │  curl POST /v1/bmad/architect                                    │
  │  │  curl POST /v1/bmad/stories  →  handoff to SDD propose           │
  │  └──────────────────────────────────────────────────────────────────┘
  │
  │  curl  POST http://host.docker.internal:8010/v1/sdd/<phase>
  │  curl  POST http://host.docker.internal:8010/v1/bmad/<phase>
  ▼
Schema Service :8010  (FastAPI + Instructor + Pydantic v2)
  ~/projects/schema-service/
  Routes:
    /v1/sdd/*   — SDD phases (explore, propose, spec, design, tasks, apply, verify)
    /v1/bmad/*  — BMAD planning phases (analyze, prd, ux, architect, stories)
  │
  │  via LiteLLM :8002  (OpenAI-compatible router)
  ▼
Local MLX models (mlx_lm.server):
  :8000  Qwen 2.5-Coder 32B   alias: local-coder      → spec, tasks, apply, archive, bmad-stories
  :8001  DeepSeek R1 32B       alias: local-thinking   → propose, design, bmad-analyze, bmad-prd, bmad-architect
  :8003  Llama 3.3 70B         alias: local-architect  → disponible, sin fase asignada
  :8005  Devstral 24B          alias: local-devstral   → fallback / tool calling
  :8006  Hermes 3 70B          alias: local-hermes     → explore, verify, bmad-ux  [MUST bind 0.0.0.0]
  │
  │  MCP  http://host.docker.internal:7438/mcp
  ▼
mcp-proxy :7438  (stdio→HTTP/SSE bridge — arranca desde el workspace)
  ~/projects/mlx-qwen/mlx_env/bin/mcp-proxy
  cwd = workspace elegido → Engram detecta el proyecto correcto
  │  stdio
  ▼
Engram :7437  (artifact persistence — MCP + REST)
  MCP desde Docker: http://host.docker.internal:7438/mcp
  REST desde host:  http://localhost:7437
  │
  └─── success_callback / failure_callback (async, non-blocking)
       ▼
      Langfuse :3000  (observability — traces, tokens, latency, cost)
        ~/projects/langfuse-docker/docker-compose.yml
```

---

## Quick Start

### Opción A — Spotlight (recomendado)

1. **AgenticStart** (Spotlight) — levanta todo el stack (Engram → mcp-proxy → Langfuse → MLX → Schema Service)
2. **HermesAgent** (Spotlight) — seleccionás el workspace → abre el dashboard en `http://localhost:9119`
3. Para cambiar de proyecto: **HermesStop** (Spotlight) → **HermesAgent** de nuevo

### Opción B — Terminal

```bash
agentic-up.sh
```

Levanta todo el stack en orden con health-gating entre tiers. LiteLLM arranca automáticamente vía launchd.

Luego arranca HermesAgent en modo chat:
```bash
cd ~/projects/hermes-docker && \
  WORKSPACE_PATH=/ruta/al/proyecto docker compose run --rm hermes hermes chat
```

O en modo dashboard:
```bash
WORKSPACE_PATH=/ruta/al/proyecto docker compose run --rm -p 9119:9119 hermes \
  hermes dashboard --tui --host 0.0.0.0 --insecure --no-open
```

### Opción B — Manual (si necesitás control por componente)

**El orden importa.** Inicia los servicios de arriba a abajo.

| # | Servicio | Comando | Verificación |
|---|---------|---------|--------|
| auto | **LiteLLM** | *(arranca automáticamente con el Mac vía launchd)* | `curl -s http://localhost:8002/v1/models` |
| 1 | Engram | `engram` | `curl -s http://localhost:7437/health` |
| 2 | **Langfuse** | `cd ~/projects/langfuse-docker && docker compose up -d` | `curl -s http://localhost:3000/api/public/health` |
| 3 | MLX model :8000 (coder) | `mlx_lm.server --model ~/models/qwen2.5-coder-32b-mlx --port 8000` | `curl -s http://localhost:8000/v1/models` |
| 4 | MLX model :8001 (thinking) | `mlx_lm.server --model ~/models/deepseek-r1-32b-mlx --port 8001` | `curl -s http://localhost:8001/v1/models` |
| 5 | MLX model :8005 (devstral) | `mlx_lm.server --model devstral --port 8005` | `curl -s http://localhost:8005/v1/models` |
| 6 | MLX model :8006 (hermes) | `mlx_lm.server --model ~/models/hermes3-70b-mlx --port 8006 --host 0.0.0.0` | `curl -s http://localhost:8006/v1/models` |
| 7 | Schema Service | `cd ~/projects/schema-service && uvicorn app.main:app --port 8010` | `curl -s http://localhost:8010/health` |
| 8 | HermesAgent | `cd ~/projects/hermes-docker && docker compose run --rm hermes hermes chat` | aparece el CLI interactivo |

> **Crítico:** Hermes 3 :8006 **debe** iniciarse con `--host 0.0.0.0` — el contenedor Docker lo alcanza a través de `host.docker.internal` y el binding predeterminado `127.0.0.1` no es accesible desde dentro del contenedor.

> **LiteLLM**: si no arrancó automáticamente (p. ej. tras un fallo del launchd), inícialo manualmente: `launchctl start com.pirito.litellm` o comprueba los logs en `~/Library/Logs/litellm/stderr.log`.

> **Langfuse**: el callback LiteLLM es async y no-bloqueante — si Langfuse no está corriendo, LiteLLM sigue funcionando normal. Las trazas se pierden silenciosamente.

### Cambiar el workspace

```bash
WORKSPACE_PATH=/path/to/your/project docker compose run --rm hermes hermes chat
```

---

## Quick Stop / Cleanup

```bash
# Detener todos los servidores MLX en ejecución (Ctrl+C en cada terminal, o matar por puerto)
lsof -ti :8000,:8001,:8003,:8005,:8006,:8002,:8010 | xargs kill -9

# Detener Langfuse (datos persistidos en volumen Docker — no se pierden)
cd ~/projects/langfuse-docker && docker compose down

# HermesAgent termina cuando cierras la sesión del CLI (restart: "no" — no es un daemon)

# Eliminar un contenedor huérfano si se quedó bloqueado
docker rm -f hermes-agent

# Borrar el volumen hermes-data (elimina memorias/logs del agente — destructivo)
docker volume rm hermes-data

# Borrar el volumen de Langfuse (elimina TODAS las trazas — destructivo)
docker volume rm langfuse-postgres-data
```

---

## SDD Workflow

MiniMax M2.7 (HermesAgent) orquesta todas las fases. Nunca genera contenido SDD por sí mismo — llama a Schema Service vía curl y persiste los artefactos en Engram vía MCP-native tools (`mem_save`, `mem_search`, `mem_get_observation`, `mem_session_summary`).

### Mapa de fases

| Fase | Endpoint | Model alias | Modelo worker |
|-------|----------|-------------|--------------|
| explore | `POST /v1/sdd/explore` | `local-hermes` | Hermes 3 70B :8006 |
| propose | `POST /v1/sdd/propose` | `local-thinking` | DeepSeek R1 32B :8001 |
| spec | `POST /v1/sdd/spec` | `local-coder` | Qwen 2.5-Coder 32B :8000 |
| design | `POST /v1/sdd/design` | `local-thinking` | DeepSeek R1 32B :8001 |
| tasks | `POST /v1/sdd/tasks` | `local-coder` | Qwen 2.5-Coder 32B :8000 |
| apply | `POST /v1/sdd/apply` | `local-coder` | Qwen 2.5-Coder 32B :8000 |
| verify | `POST /v1/sdd/verify` | `local-hermes` | Hermes 3 70B :8006 |

### Estrategia de reintentos (Schema Service)

Cada endpoint tiene un bucle de degradación de 3 intentos:
1. Intento 1 — `instructor.Mode.JSON` a la temperatura de la fase
2. Intento 2 — `instructor.Mode.JSON` (repetición)
3. Intento 3 — `instructor.Mode.MD_JSON` a la temperatura de la fase

Fallbacks del router LiteLLM: `local-thinking → local-devstral → local-coder`

### Persistencia de artefactos (Engram)

HermesAgent captura la respuesta JSON en bruto de cada fase y la persiste en Engram vía MCP-native tools (no REST directo):

| Tool | Cuándo usarlo |
|------|--------------|
| `mem_save` | Guardar artefacto de cada fase; siempre con `project: "$HERMES_PROJECT"` |
| `mem_search` + `mem_get_observation` | Recuperar artefactos de fases previas |
| `mem_session_summary` | Cierre de sesión — obligatorio antes de "listo" |

```
topic key format:  sdd/<change-name>/<phase>
examples:
  sdd/my-feature/explore
  sdd/my-feature/proposal
  sdd/my-feature/spec
  sdd/my-feature/design
  sdd/my-feature/tasks
  sdd/my-feature/apply-progress
  sdd/my-feature/verify-report
```

Acceso Engram desde el contenedor: MCP SSE vía `http://host.docker.internal:7438/mcp` (no REST directo `:7437`).

---

## BMAD Workflow

BMAD (Business, Methodology, Architecture, Design) is the planning layer that precedes SDD. Run BMAD when starting from an idea or requirement — it produces structured artifacts that feed directly into SDD propose.

Full pipeline: `idea → analyze → prd → [ux] → architect → stories → SDD propose → implement`

### Mapa de fases BMAD

| Fase | Endpoint | Model alias | Modelo worker |
|-------|----------|-------------|--------------|
| analyze | `POST /v1/bmad/analyze` | `local-thinking` | DeepSeek R1 32B :8001 |
| prd | `POST /v1/bmad/prd` | `local-thinking` | DeepSeek R1 32B :8001 |
| ux | `POST /v1/bmad/ux` | `local-hermes` | Hermes 3 70B :8006 |
| architect | `POST /v1/bmad/architect` | `local-thinking` | DeepSeek R1 32B :8001 |
| stories | `POST /v1/bmad/stories` | `local-coder` | Qwen 2.5-Coder 32B :8000 |

**UX phase**: MANDATORY for UI/UX changes. SKIPPABLE for pure backend/API-only changes.

### Persistencia de artefactos BMAD (Engram)

```
topic key format:  bmad/<change-name>/<phase>
examples:
  bmad/my-feature/analyze
  bmad/my-feature/prd
  bmad/my-feature/ux
  bmad/my-feature/architect
  bmad/my-feature/stories
```

### Handoff a SDD

Después de completar `stories`, los artefactos BMAD se pasan como campos opcionales al endpoint `/v1/sdd/propose`:
- `bmad_prd` → contenido de `bmad/{change}/prd`
- `bmad_architect` → contenido de `bmad/{change}/architect`
- `bmad_stories` → contenido de `bmad/{change}/stories`

Ver Section 17 de soul.md para el procedimiento completo con snippet jq.

---

## Component Reference

### HermesAgent

- **Qué es**: Agente CLI en contenedor. No es un daemon — se ejecuta de forma interactiva y termina cuando se cierra la sesión.
- **Dónde**: `~/projects/hermes-docker/`
- **Imagen**: `nousresearch/hermes-agent` (digest fijado mediante `HERMES_IMAGE` en `.env`)
- **Comportamiento de Compose**: `restart: "no"` es intencional. Usa `docker compose run --rm hermes hermes chat`.
- **Config**: `hermes-config/config.yaml` — define el endpoint del LLM, rutas de almacenamiento, workspace y ruta del config MCP
- **System prompt**: `hermes-config/soul.md` — bind-mounted en modo lectura en `/opt/data/SOUL.md`
- **Volumen de datos**: `hermes-data` (named volume) — almacena memorias, logs y skills del agente
- **Workspace**: bind-mounted desde `WORKSPACE_PATH` (variable de entorno) → `/workspace` dentro del contenedor
- **Red**: `extra_hosts: host.docker.internal:host-gateway` — así el contenedor alcanza los servicios del host

### Schema Service

- **Qué es**: Aplicación FastAPI que despacha cada fase SDD al modelo local correspondiente a través de LiteLLM. Usa Instructor para salida estructurada (Pydantic v2).
- **Dónde**: `~/projects/schema-service/`
- **Puerto**: `:8010`
- **Inicio**: `uvicorn app.main:app --port 8010` (desde la raíz del repositorio)
- **Registro de fases**: `app/registry.py` — mapea fase → model alias, system prompt, token budget, temperatura
- **System prompts**: `app/prompts/*.txt` — un archivo por fase (cargados mediante `load_prompt()`)
- **Rutas**: `app/routes/sdd.py` — un `POST /v1/sdd/<phase>` por fase

### LiteLLM

- **Qué es**: Proxy compatible con OpenAI que enruta los model aliases a los backends reales (MLX local o APIs remotas).
- **Config**: `~/litellm_config.yaml`
- **Puerto**: `:8002`
- **Inicio**: automático vía launchd (`com.pirito.litellm`) al arrancar el Mac
- **Plist**: `~/Library/LaunchAgents/com.pirito.litellm.plist`
- **Wrapper script**: `~/bin/litellm-launch.sh` (carga env vars desde `~/.config/litellm/env`)
- **API keys**: `~/.config/litellm/env` (chmod 600) — editarlo para añadir/rotar keys
- **Logs**: `~/Library/Logs/litellm/stdout.log` y `stderr.log`
- **Fallbacks configurados**: `local-thinking → local-devstral → local-coder`
- **Comandos de control**:
  ```bash
  launchctl start com.pirito.litellm   # arrancar manualmente
  launchctl stop com.pirito.litellm    # parar
  launchctl list | grep litellm        # ver estado y PID
  ```

### Local MLX Models

- **Runtime**: `mlx_lm.server` — inicia un servidor compatible con OpenAI en el puerto especificado
- **Directorio de modelos**: `~/models/`

| Puerto | Modelo | Alias | Notas |
|------|-------|-------|-------|
| :8000 | Qwen 2.5-Coder 32B | `local-coder` | |
| :8001 | DeepSeek R1 32B | `local-thinking` | Tiene tokens de razonamiento interno antes de la salida visible |
| :8003 | Llama 3.3 70B | `local-architect` | |
| :8005 | Devstral 24B | `local-devstral` | fallback / tool calling |
| :8006 | Hermes 3 70B | `local-hermes` | **Debe iniciarse con `--host 0.0.0.0`** |

### mcp-proxy

- **Qué es**: Bridge stdio→HTTP/SSE que expone Engram MCP a los contenedores Docker.
- **Puerto**: `:7438`
- **Binary**: `~/projects/mlx-qwen/mlx_env/bin/mcp-proxy`
- **Arranque**: gestionado por `agentic-up.sh` (Tier 1b) y por `HermesAgent.app` (reinicio por workspace)
- **Crítico**: debe arrancar desde el directorio del workspace activo — Engram usa ese cwd para detectar el proyecto
- **URL desde el contenedor**: `http://host.docker.internal:7438/mcp` (streamable HTTP)
- **Logs**: `~/Library/Logs/agentic-stack/engram-mcp-proxy.log`

### Engram

- **Qué es**: Servicio de memoria persistente. Accesible via REST (host) y via MCP (Docker → mcp-proxy).
- **Puerto REST**: `:7437` — `http://localhost:7437` (host) / `http://host.docker.internal:7437` (Docker, no recomendado)
- **Puerto MCP**: `:7438` vía mcp-proxy — `http://host.docker.internal:7438/mcp` (Docker)
- **Detección de proyecto**: usa el cwd del proceso `engram mcp` (= cwd de mcp-proxy). Por eso HermesAgent.app reinicia mcp-proxy desde el workspace.
- **Configurado en hermes-docker**: `hermes mcp add engram --url http://host.docker.internal:7438/mcp` (persiste en hermes-data volume)

### Langfuse

- **Qué es**: Observabilidad para LLMs. Registra cada request LiteLLM como traza con modelo, tokens, latencia y coste.
- **Dónde**: `~/projects/langfuse-docker/` (Docker Compose — Langfuse v2 + Postgres 15)
- **Puerto**: `:3000` — UI en `http://localhost:3000`
- **Imagen**: `langfuse/langfuse:2` (pinada a v2 — NO actualizar a v3, requiere ClickHouse)
- **Integración LiteLLM**: `success_callback` + `failure_callback` en `~/litellm_config.yaml`
- **API keys**: `~/.config/litellm/env` — `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`
- **Secrets del servidor**: `~/projects/langfuse-docker/.env` (chmod 600 — generados con `openssl rand -hex 32`)
- **Comportamiento ante caída**: el callback es async y no-bloqueante — LiteLLM nunca falla por Langfuse caído
- **Inicio**:
  ```bash
  cd ~/projects/langfuse-docker && docker compose up -d
  ```
- **Verificación**: `curl -s http://localhost:3000/api/public/health`

### macOS Apps (Spotlight)

| App | Acción |
|-----|--------|
| **AgenticStart** | Levanta todo el stack (agentic-up.sh) |
| **AgenticStop** | Para MLX models, Langfuse, Schema Service |
| **HermesAgent** | Selecciona workspace → reinicia mcp-proxy desde ese dir → lanza dashboard web en :9119 |
| **HermesStop** | Mata el contenedor hermes-docker + mcp-proxy |

**Flujo cambio de proyecto**: HermesStop → HermesAgent → seleccionás nueva carpeta.

**Por qué reinicia mcp-proxy**: Engram detecta el proyecto actual desde el cwd del proceso mcp-proxy (HOST). Al reiniciarlo desde la carpeta del workspace elegido, `mem_context` / `mem_search` filtran automáticamente por ese proyecto.

### agentic-up.sh

- **Qué es**: Script de arranque unificado para todo el stack. Idempotente — se puede re-ejecutar sin romper nada.
- **Dónde**: `~/bin/agentic-up.sh`
- **Tiers** (en orden):
  - T0: Docker Desktop (auto-start si no está corriendo)
  - T1: Engram (:7437)
  - T1b: mcp-proxy (:7438) — bridge stdio→HTTP/SSE para Docker
  - T2: MLX models (:8000, :8001, :8003, :8004, :8005, :8006) — en paralelo con health-gating
  - T3: devstral-proxy (:8005)
  - T4: Schema Service (:8010)
- **LiteLLM no lo gestiona** — arranca vía launchd al encender el Mac
- **Modo check**: `agentic-up.sh --check` — verifica estado sin arrancar nada

---

## Configuration Files Cheatsheet

| Archivo | Controla | Cuándo editarlo |
|------|----------|-----------|
| `hermes-docker/docker-compose.yml` | Config del contenedor, volúmenes, límites de recursos, variables de entorno | Al cambiar la imagen, la ruta del workspace o los límites de recursos |
| `hermes-docker/hermes-config/config.yaml` | Endpoint del LLM de HermesAgent, rutas de almacenamiento, config MCP | Al cambiar el modelo principal del agente o las rutas de datos |
| `hermes-docker/hermes-config/soul.md` | System prompt (SOUL.md) inyectado en HermesAgent | Al actualizar las instrucciones de orquestación SDD |
| `hermes-docker/hermes-config/mcp_servers.yaml` | Conexiones a servidores MCP para HermesAgent | Al añadir o eliminar herramientas MCP |
| `~/litellm_config.yaml` | Model aliases, API keys, callbacks de observabilidad, fallbacks | Al añadir modelos, cambiar puertos, ajustar fallbacks o cambiar callbacks |
| `~/.config/litellm/env` | API keys de LiteLLM + credenciales Langfuse (chmod 600) | Al rotar keys de Anthropic, Together.ai o Langfuse |
| `~/projects/langfuse-docker/.env` | Secrets del servidor Langfuse (NEXTAUTH_SECRET, SALT, POSTGRES_PASSWORD) (chmod 600) | Solo si perdés acceso o necesitás rotar secrets — requiere `docker compose down -v` |
| `~/projects/langfuse-docker/docker-compose.yml` | Imagen Langfuse, puerto, Postgres | Al pinear a una versión menor específica de Langfuse |
| `schema-service/app/registry.py` | Fase → model alias, token budgets, temperatura | Al reasignar qué modelo gestiona cada fase SDD |
| `schema-service/app/prompts/*.txt` | System prompts por fase SDD | Al ajustar las instrucciones del modelo para una fase |
| `.env` (hermes-docker) | `HERMES_IMAGE`, `MINIMAX_API_KEY`, `OPENAI_API_KEY`, `WORKSPACE_PATH` | Al rotar API keys, cambiar la imagen o el workspace por defecto |

---

## Troubleshooting

### ❌ LiteLLM no conecta / Schema Service devuelve 500

**Causa**: LiteLLM no está en ejecución, o se inició después de HermesAgent.

**Solución**:
```bash
# Comprobar si LiteLLM está activo
curl -s http://localhost:8002/v1/models

# Arrancar o reiniciar vía launchd
launchctl start com.pirito.litellm
# Si no responde, forzar restart:
launchctl kickstart -k gui/$(id -u)/com.pirito.litellm

# Logs
tail -f ~/Library/Logs/litellm/stderr.log

# Reiniciar Schema Service después de confirmar que LiteLLM está sano
```

---

### ❌ Trazas no aparecen en Langfuse

**Causa**: Langfuse no estaba corriendo cuando LiteLLM envió el callback, o las API keys en `~/.config/litellm/env` son incorrectas.

**Diagnóstico**:
```bash
# ¿Está Langfuse corriendo?
curl -s http://localhost:3000/api/public/health

# ¿Las keys están cargadas en LiteLLM?
launchctl list | grep litellm   # debe mostrar PID activo

# Verificar que hay trazas vía API
curl -s http://localhost:3000/api/public/traces?limit=5 \
  -u "pk-lf-...:sk-lf-..."
```

**Solución si Langfuse estaba caído**: levantar Langfuse, reiniciar LiteLLM para que recargue las keys:
```bash
cd ~/projects/langfuse-docker && docker compose up -d
launchctl kickstart -k gui/$(id -u)/com.pirito.litellm
```

---

### ❌ Hermes 3 :8006 no es accesible desde Docker

**Causa**: `mlx_lm.server` para :8006 se inició sin `--host 0.0.0.0`. El binding predeterminado `127.0.0.1` no es accesible vía `host.docker.internal`.

**Solución**:
```bash
# Matar el servidor actual en :8006
lsof -ti :8006 | xargs kill -9

# Reiniciar con el binding correcto
mlx_lm.server --model ~/models/hermes3-70b-mlx --port 8006 --host 0.0.0.0
```

**Verificación** (desde dentro del contenedor):
```bash
docker compose run --rm hermes curl -s http://host.docker.internal:8006/v1/models
```

---

### ❌ MiniMax ejecutando fases SDD por sí mismo (no enruta a modelos locales)

**Causa**: Schema Service (:8010) o LiteLLM (:8002) no está en marcha cuando HermesAgent arranca. MiniMax cae en el fallback de generar contenido por su cuenta.

**Solución**: Levanta siempre Schema Service y LiteLLM **antes** de iniciar HermesAgent. Verifica ambos:
```bash
curl -s http://localhost:8010/health
curl -s http://localhost:8002/v1/models
```

---

### ❌ Contenedor hermes-agent en bucle de reinicios

**Causa**: Una sesión anterior se inició con `docker compose up` en lugar de `docker compose run`, o con un CMD inválido o desactualizado. El contenedor no tiene un punto de entrada válido cuando se ejecuta como daemon.

**Solución**:
```bash
# Detener y eliminar el contenedor bloqueado
docker stop hermes-agent && docker rm hermes-agent

# Iniciar siempre con run, no con up
docker compose run --rm hermes hermes chat
```

**Verificar que no hay ningún contenedor en ejecución**:
```bash
docker ps --filter name=hermes-agent
```

---

### ⚠️ SOUL.md perdido o que no se actualiza

**Causa**: Anteriormente, SOUL.md vivía únicamente en el named volume `hermes-data` y podía sobreescribirse al reiniciar el contenedor. La corrección (Fase 8 quick wins) lo movió al repositorio como bind-mount.

**Estado actual**: `hermes-config/soul.md` está bind-mounted en modo lectura en `/opt/data/SOUL.md` en `docker-compose.yml`. Los cambios en el archivo del host tienen efecto inmediatamente en la siguiente sesión — no es necesario `docker cp`.

**Si el contenedor lee un SOUL.md desactualizado**:
```bash
# Confirmar que el bind-mount está en su lugar
docker inspect hermes-agent | jq '.[].Mounts[] | select(.Destination == "/opt/data/SOUL.md")'

# Si falta, recrear con compose run (no docker run)
docker rm -f hermes-agent
docker compose run --rm hermes hermes chat
```

**Para recuperar SOUL.md desde el volumen** (solo en emergencia, si el archivo del repositorio se ha perdido):
```bash
docker run --rm -v hermes-data:/data alpine cat /data/SOUL.md
```

---

## Changelog

### ✅ hermes-bmad — BMAD planning phases (2026-06-03)

- **5 BMAD phases** added to Schema Service: `/v1/bmad/analyze`, `/v1/bmad/prd`, `/v1/bmad/ux`, `/v1/bmad/architect`, `/v1/bmad/stories`
- **5 Pydantic v2 schema modules**: `analyze.py`, `prd.py`, `ux.py`, `architect.py`, `stories.py` — each with dedicated `*In` + `*Out` models
- **5 system prompts**: `bmad_analyze.txt` (Mary/BA), `bmad_prd.txt` (John/PM), `bmad_ux.txt` (Sally/UX), `bmad_architect.txt` (Winston/Architect), `bmad_stories.txt` (Scrum Master/PO)
- **Registry**: 5 PhaseSpec entries added to `registry.py` — `local-thinking` for analyze/prd/architect, `local-hermes` for ux, `local-coder` for stories
- **bmad.py router** registered in `main.py` — shares `_call_with_retry`, `_with_meta`, `_build_messages` from `sdd.py` (no duplication)
- **SDD bridge**: `ProposeIn` extended with `bmad_prd`, `bmad_architect`, `bmad_stories` optional fields; `_enrich_context` injects BMAD context before SDD context
- **soul.md**: Sections 12–17 added — BMAD model table, dependency graph + UX skip rule, endpoints, topic keys, phase flow, SDD handoff procedure
- **RUNBOOK**: Architecture diagram updated to show BMAD layer; BMAD Workflow section added

### ✅ hermes-gentle-ai — Orquestación gentle-ai en soul.md (2026-06-03)

- **soul.md reescrito** con 11 secciones: principios de orquestación de gentle-ai adaptados a primitivas hermes (curl + MCP)
- **Engram migrado REST→MCP**: `curl POST :7437` reemplazado por `mem_save`/`mem_search`/`mem_get_observation`/`mem_session_summary`
- **Tabla de modelos LiteLLM**: `local-thinking` (propose/design), `local-hermes` (explore/verify/default), `local-coder` (spec/tasks/apply/archive)
- **DAG completo**: `explore → propose → spec/design → tasks → apply → verify → archive` con reglas de dependencia explícitas
- **Reglas de delegación/coste** adaptadas a curl/bash — sin referencias a Agent/Task/Skill tool
- **Protocolo de cierre de sesión** (`mem_session_summary`) ahora obligatorio
- **CLAUDE.md** etiquetado con 5 sync-tags (`gentle-ai:hermes-portable`) para facilitar el diff entre soul.md y su fuente

### ✅ Dashboard web + macOS apps (2026-05-31)

- **HermesAgent.app**: lanza `hermes dashboard --tui` en :9119 — browser abre automáticamente con chat TUI embebido
- **HermesStop.app**: mata el contenedor hermes-docker + mcp-proxy limpiamente
- **mcp-proxy**: nuevo Tier 1b en `agentic-up.sh` — bridge stdio→HTTP/SSE en :7438 para MCP desde Docker
- **Engram MCP configurado** en hermes-docker: `hermes mcp add engram --url .../mcp`
- **Detección de proyecto dinámica**: HermesAgent.app reinicia mcp-proxy desde el workspace elegido + pasa `HERMES_PROJECT` env var al contenedor
- **docker-compose.yml**: puerto 9119:9119, volumen `hermes-tui-dist` (writable para build TUI)
- **SOUL.md**: usa `$HERMES_PROJECT` para nombrar el proyecto en todas las llamadas Engram MCP

### ✅ hermes-native — experimento A/B (archivado 2026-05-31)

- Experimento: segundo contenedor con capacidades nativas (execute_code + MCP Engram) vs hermes-docker + schema-service
- Resultado: **STAY** — hermes-docker gana en calidad (+15% coherence, +27% specificity)
- hermes-native es más rápido en workers (-45% latencia) pero el orquestador MiniMax consume ~2M tokens/sesión (coste API real)
- Archivado en Engram: `sdd/hermes-native/archive-report`

### ✅ Fase 9 — hermes-stack-improvements (archivada 2026-05-29)

- **Slice 1**: Autoarranque LiteLLM vía launchd — `~/bin/litellm-launch.sh` + plist + `~/.config/litellm/env`
- **Slice 2**: Inputs estructurados en Schema Service — `ProposeIn`, `SpecIn`, etc. con fallback `context: str`
- **Slice 3**: Preservación de `_meta` en Engram — `jq` en SOUL.md + headers `X-SDD-Phase`/`X-SDD-Worker`

### ✅ Fase 10a — LLM judge para todas las fases (archivada 2026-05-29)

LLM judge extendido de 2 fases (propose, design) a las 6 fases SDD. Rúbricas adversariales por fase en `calibration/judge.py`.

### ✅ Fase 10b — Script de startup unificado (archivada 2026-05-29)

`~/bin/agentic-up.sh` — arranca los 8 componentes del stack en 4 tiers con health-gating paralelo. Idempotente, modo `--check`.

### ✅ Fase 10c — Observabilidad LiteLLM vía Langfuse (archivada 2026-05-29)

Langfuse v2 self-hosted en `~/projects/langfuse-docker/`. Callbacks async en LiteLLM. Trazas con modelo, tokens, latencia y coste. Integrado en `agentic-up.sh` como tier T0.

### ✅ Fase 10d — Mejoras en schemas de output SDD (archivada 2026-05-29)

- **TasksOut**: bloque YAML al final del artifact con `id`, `status` (pending/in_progress/done/skipped), `deps`
- **VerifyReportOut**: sección Issues como tabla `| severity | path | description |`
- **sdd-apply**: regla YAML-first con fallback a checklist para artifacts anteriores

---

## Pending / Roadmap

Sin fases pendientes. Stack productivo y estable.

Posibles mejoras futuras:
- **Open WebUI** — alternativa de chat sin terminal (mencionado, nunca decidido)
- **Icono HermesStop.app** — diferenciarlo visualmente de HermesAgent en Spotlight
