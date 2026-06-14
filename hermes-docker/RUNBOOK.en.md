[🇪🇸 Español](RUNBOOK.md) | 🇬🇧 English

# Local Agentic Stack — Runbook

HermesAgent (Docker) orchestrates SDD workflows using MiniMax M2.7 as the primary LLM. It delegates each SDD phase to local MLX models through Schema Service (:8010) and LiteLLM (:8002). Artifacts are persisted in Engram (:7437). All LiteLLM requests are observed in Langfuse (:3000).

---

## Architecture

```
User
  │  Spotlight → HermesAgent.app  (selects workspace)
  ▼
HermesAgent (Docker container)
  LLM: MiniMax M2.7 via Together.ai API
  Config: hermes-config/config.yaml
  SOUL.md: hermes-config/soul.md (bind-mounted :ro)
  Dashboard web: http://localhost:9119  (--tui enabled)
  Workspace: /workspace/<project> (dynamically mounted)
  HERMES_PROJECT: <workspace basename>
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
  :8006  Qwen3 32B             alias: local-hermes     → explore, verify, bmad-ux  [MUST bind 0.0.0.0]
  │
  │  MCP  http://host.docker.internal:7438/mcp
  ▼
mcp-proxy :7438  (stdio→HTTP/SSE bridge — starts from workspace)
  ~/projects/mlx-qwen/mlx_env/bin/mcp-proxy
  cwd = chosen workspace → Engram detects the correct project
  │  stdio
  ▼
Engram :7437  (artifact persistence — MCP + REST)
  MCP from Docker: http://host.docker.internal:7438/mcp
  REST from host:  http://localhost:7437
  │
  └─── success_callback / failure_callback (async, non-blocking)
       ▼
      Langfuse :3000  (observability — traces, tokens, latency, cost)
        ~/projects/langfuse-docker/docker-compose.yml
```

---

## Quick Start

### Option A — Spotlight (recommended)

1. **AgenticStart** (Spotlight) — brings up the full stack (Engram → mcp-proxy → Langfuse → MLX → Schema Service)
2. **HermesAgent** (Spotlight) — select workspace → opens dashboard at `http://localhost:9119`
3. To switch projects: **HermesStop** (Spotlight) → **HermesAgent** again

### Option B — Terminal

```bash
agentic-up.sh
```

Brings up the full stack in order with health-gating between tiers. LiteLLM starts automatically via launchd.

Then start HermesAgent in chat mode:
```bash
cd ~/projects/hermes-docker && \
  WORKSPACE_PATH=/path/to/project docker compose run --rm hermes hermes chat
```

Or in dashboard mode:
```bash
WORKSPACE_PATH=/path/to/project docker compose run --rm -p 9119:9119 hermes \
  hermes dashboard --tui --host 0.0.0.0 --insecure --no-open
```

### Option C — Manual (if you need per-component control)

**Order matters.** Start services top to bottom.

| # | Service | Command | Verification |
|---|---------|---------|--------|
| auto | **LiteLLM** | *(starts automatically on Mac boot via launchd)* | `curl -s http://localhost:8002/v1/models` |
| 1 | Engram | `engram` | `curl -s http://localhost:7437/health` |
| 2 | **Langfuse** | `cd ~/projects/langfuse-docker && docker compose up -d` | `curl -s http://localhost:3000/api/public/health` |
| 3 | MLX model :8000 (coder) | `mlx_lm.server --model ~/models/qwen2.5-coder-32b-mlx --port 8000` | `curl -s http://localhost:8000/v1/models` |
| 4 | MLX model :8001 (thinking) | `mlx_lm.server --model ~/models/deepseek-r1-32b-mlx --port 8001` | `curl -s http://localhost:8001/v1/models` |
| 5 | MLX model :8006 (hermes) | `mlx_lm.server --model ~/models/qwen3-32b-mlx --port 8006 --host 0.0.0.0` | `curl -s http://localhost:8006/v1/models` |
| 7 | Schema Service | `cd ~/projects/schema-service && uvicorn app.main:app --port 8010` | `curl -s http://localhost:8010/health` |
| 8 | HermesAgent | `cd ~/projects/hermes-docker && docker compose run --rm hermes hermes chat` | interactive CLI appears |

> **Critical:** Qwen3 32B :8006 **must** be started with `--host 0.0.0.0` — the Docker container reaches it via `host.docker.internal` and the default `127.0.0.1` binding is not reachable from inside the container.

> **LiteLLM**: if it didn't start automatically (e.g. after a launchd failure), start it manually: `launchctl start com.pirito.litellm` or check logs at `~/Library/Logs/litellm/stderr.log`.

> **Langfuse**: the LiteLLM callback is async and non-blocking — if Langfuse is not running, LiteLLM continues working normally. Traces are silently lost.

### Switching the workspace

```bash
WORKSPACE_PATH=/path/to/your/project docker compose run --rm hermes hermes chat
```

---

## Quick Stop / Cleanup

```bash
# Stop all running MLX servers (Ctrl+C in each terminal, or kill by port)
lsof -ti :8000,:8001,:8006,:8002,:8010 | xargs kill -9

# Stop Langfuse (data persisted in Docker volume — not lost)
cd ~/projects/langfuse-docker && docker compose down

# HermesAgent exits when you close the CLI session (restart: "no" — not a daemon)

# Remove an orphan container if it got stuck
docker rm -f hermes-agent

# Delete the hermes-data volume (removes agent memories/logs — destructive)
docker volume rm hermes-data

# Delete the Langfuse volume (removes ALL traces — destructive)
docker volume rm langfuse-postgres-data
```

---

## SDD Workflow

MiniMax M2.7 (HermesAgent) orchestrates all phases. It never generates SDD content itself — it calls Schema Service via curl and persists artifacts in Engram via MCP-native tools (`mem_save`, `mem_search`, `mem_get_observation`, `mem_session_summary`).

### Phase map

| Phase | Endpoint | Model alias | Worker model |
|-------|----------|-------------|--------------|
| explore | `POST /v1/sdd/explore` | `local-hermes` | Qwen3 32B :8006 |
| propose | `POST /v1/sdd/propose` | `local-thinking` | DeepSeek R1 32B :8001 |
| spec | `POST /v1/sdd/spec` | `local-coder` | Qwen 2.5-Coder 32B :8000 |
| design | `POST /v1/sdd/design` | `local-thinking` | DeepSeek R1 32B :8001 |
| tasks | `POST /v1/sdd/tasks` | `local-coder` | Qwen 2.5-Coder 32B :8000 |
| apply | `POST /v1/sdd/apply` | `local-coder` | Qwen 2.5-Coder 32B :8000 |
| verify | `POST /v1/sdd/verify` | `local-hermes` | Qwen3 32B :8006 |

### Retry strategy (Schema Service)

Each endpoint has a 3-attempt degradation loop:
1. Attempt 1 — `instructor.Mode.JSON` at the phase temperature
2. Attempt 2 — `instructor.Mode.JSON` (repeat)
3. Attempt 3 — `instructor.Mode.MD_JSON` at the phase temperature

LiteLLM router fallbacks: `local-thinking → local-coder`

### Artifact persistence (Engram)

HermesAgent captures the raw JSON response from each phase and persists it in Engram via MCP-native tools (not direct REST):

| Tool | When to use |
|------|-------------|
| `mem_save` | Save each phase artifact; always with `project: "$HERMES_PROJECT"` |
| `mem_search` + `mem_get_observation` | Retrieve artifacts from previous phases |
| `mem_session_summary` | Session close — mandatory before "done" |

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

Engram access from container: MCP SSE via `http://host.docker.internal:7438/mcp` (not direct REST `:7437`).

---

## BMAD Workflow

BMAD (Business, Methodology, Architecture, Design) is the planning layer that precedes SDD. Run BMAD when starting from an idea or requirement — it produces structured artifacts that feed directly into SDD propose.

Full pipeline: `idea → analyze → prd → [ux] → architect → stories → SDD propose → implement`

### BMAD phase map

| Phase | Endpoint | Model alias | Worker model |
|-------|----------|-------------|--------------|
| analyze | `POST /v1/bmad/analyze` | `local-thinking` | DeepSeek R1 32B :8001 |
| prd | `POST /v1/bmad/prd` | `local-thinking` | DeepSeek R1 32B :8001 |
| ux | `POST /v1/bmad/ux` | `local-hermes` | Qwen3 32B :8006 |
| architect | `POST /v1/bmad/architect` | `local-thinking` | DeepSeek R1 32B :8001 |
| stories | `POST /v1/bmad/stories` | `local-coder` | Qwen 2.5-Coder 32B :8000 |

**UX phase**: MANDATORY for UI/UX changes. SKIPPABLE for pure backend/API-only changes.

### BMAD artifact persistence (Engram)

```
topic key format:  bmad/<change-name>/<phase>
examples:
  bmad/my-feature/analyze
  bmad/my-feature/prd
  bmad/my-feature/ux
  bmad/my-feature/architect
  bmad/my-feature/stories
```

### Handoff to SDD

After completing `stories`, BMAD artifacts are passed as optional fields to the `/v1/sdd/propose` endpoint:
- `bmad_prd` → content from `bmad/{change}/prd`
- `bmad_architect` → content from `bmad/{change}/architect`
- `bmad_stories` → content from `bmad/{change}/stories`

See Section 17 of soul.md for the complete procedure with jq snippet.

---

## Component Reference

### HermesAgent

- **What it is**: CLI agent in a container. Not a daemon — runs interactively and exits when the session is closed.
- **Where**: `~/projects/hermes-docker/`
- **Image**: `nousresearch/hermes-agent` (digest pinned via `HERMES_IMAGE` in `.env`)
- **Compose behavior**: `restart: "no"` is intentional. Use `docker compose run --rm hermes hermes chat`.
- **Config**: `hermes-config/config.yaml` — defines the LLM endpoint, storage paths, workspace, and MCP config path
- **System prompt**: `hermes-config/soul.md` — bind-mounted read-only at `/opt/data/SOUL.md`
- **Data volume**: `hermes-data` (named volume) — stores agent memories, logs, and skills
- **Workspace**: bind-mounted from `WORKSPACE_PATH` (env var) → `/workspace` inside the container
- **Network**: `extra_hosts: host.docker.internal:host-gateway` — allows the container to reach host services

### Schema Service

- **What it is**: FastAPI application that dispatches each SDD phase to the corresponding local model via LiteLLM. Uses Instructor for structured output (Pydantic v2).
- **Where**: `~/projects/schema-service/`
- **Port**: `:8010`
- **Start**: `uvicorn app.main:app --port 8010` (from repo root)
- **Phase registry**: `app/registry.py` — maps phase → model alias, system prompt, token budget, temperature
- **System prompts**: `app/prompts/*.txt` — one file per phase (loaded via `load_prompt()`)
- **Routes**: `app/routes/sdd.py` — one `POST /v1/sdd/<phase>` per phase

### LiteLLM

- **What it is**: OpenAI-compatible proxy that routes model aliases to real backends (local MLX or remote APIs).
- **Config**: `~/litellm_config.yaml`
- **Port**: `:8002`
- **Start**: automatic via launchd (`com.pirito.litellm`) on Mac boot
- **Plist**: `~/Library/LaunchAgents/com.pirito.litellm.plist`
- **Wrapper script**: `~/bin/litellm-launch.sh` (loads env vars from `~/.config/litellm/env`)
- **API keys**: `~/.config/litellm/env` (chmod 600) — edit to add/rotate keys
- **Logs**: `~/Library/Logs/litellm/stdout.log` and `stderr.log`
- **Configured fallbacks**: `local-thinking → local-coder`
- **Control commands**:
  ```bash
  launchctl start com.pirito.litellm   # start manually
  launchctl stop com.pirito.litellm    # stop
  launchctl list | grep litellm        # check status and PID
  ```

### Local MLX Models

- **Runtime**: `mlx_lm.server` — starts an OpenAI-compatible server on the specified port
- **Model directory**: `~/models/`

| Port | Model | Alias | Notes |
|------|-------|-------|-------|
| :8000 | Qwen 2.5-Coder 32B | `local-coder` | |
| :8001 | DeepSeek R1 32B | `local-thinking` | Has internal reasoning tokens before visible output |
| :8006 | Qwen3 32B | `local-hermes` | **Must be started with `--host 0.0.0.0`** |

### mcp-proxy

- **What it is**: stdio→HTTP/SSE bridge that exposes Engram MCP to Docker containers.
- **Port**: `:7438`
- **Binary**: `~/projects/mlx-qwen/mlx_env/bin/mcp-proxy`
- **Startup**: managed by `agentic-up.sh` (Tier 1b) and by `HermesAgent.app` (workspace restart)
- **Critical**: must start from the active workspace directory — Engram uses that cwd to detect the project
- **URL from container**: `http://host.docker.internal:7438/mcp` (streamable HTTP)
- **Logs**: `~/Library/Logs/agentic-stack/engram-mcp-proxy.log`

### Engram

- **What it is**: Persistent memory service. Accessible via REST (host) and via MCP (Docker → mcp-proxy).
- **REST port**: `:7437` — `http://localhost:7437` (host) / `http://host.docker.internal:7437` (Docker, not recommended)
- **MCP port**: `:7438` via mcp-proxy — `http://host.docker.internal:7438/mcp` (Docker)
- **Project detection**: uses the cwd of the `engram mcp` process (= mcp-proxy cwd). That is why HermesAgent.app restarts mcp-proxy from the workspace.
- **Configured in hermes-docker**: `hermes mcp add engram --url http://host.docker.internal:7438/mcp` (persisted in hermes-data volume)

### Langfuse

- **What it is**: LLM observability. Records every LiteLLM request as a trace with model, tokens, latency, and cost.
- **Where**: `~/projects/langfuse-docker/` (Docker Compose — Langfuse v2 + Postgres 15)
- **Port**: `:3000` — UI at `http://localhost:3000`
- **Image**: `langfuse/langfuse:2` (pinned to v2 — DO NOT upgrade to v3, requires ClickHouse)
- **LiteLLM integration**: `success_callback` + `failure_callback` in `~/litellm_config.yaml`
- **API keys**: `~/.config/litellm/env` — `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`
- **Server secrets**: `~/projects/langfuse-docker/.env` (chmod 600 — generated with `openssl rand -hex 32`)
- **Failure behavior**: callback is async and non-blocking — LiteLLM never fails due to Langfuse being down
- **Start**:
  ```bash
  cd ~/projects/langfuse-docker && docker compose up -d
  ```
- **Verification**: `curl -s http://localhost:3000/api/public/health`

### macOS Apps (Spotlight)

| App | Action |
|-----|--------|
| **AgenticStart** | Brings up the full stack (agentic-up.sh) |
| **AgenticStop** | Stops MLX models, Langfuse, Schema Service |
| **HermesAgent** | Select workspace → restarts mcp-proxy from that dir → launches web dashboard at :9119 |
| **HermesStop** | Kills hermes-docker container + mcp-proxy |

**Project switch flow**: HermesStop → HermesAgent → select new folder.

**Why it restarts mcp-proxy**: Engram detects the current project from the cwd of the mcp-proxy process (HOST). By restarting it from the chosen workspace folder, `mem_context` / `mem_search` automatically filter by that project.

### agentic-up.sh

- **What it is**: Unified startup script for the full stack. Idempotent — can be re-run without breaking anything.
- **Where**: `~/bin/agentic-up.sh`
- **Tiers** (in order):
  - T0: Docker Desktop (auto-start if not running)
  - T1: Engram (:7437)
  - T1b: mcp-proxy (:7438) — stdio→HTTP/SSE bridge for Docker
  - T2: MLX models (:8000, :8001, :8006) — in parallel with health-gating
  - T4: Schema Service (:8010)
- **LiteLLM is not managed here** — starts via launchd on Mac boot
- **Check mode**: `agentic-up.sh --check` — verifies status without starting anything

---

## Configuration Files Cheatsheet

| File | Controls | When to edit |
|------|----------|-----------|
| `hermes-docker/docker-compose.yml` | Container config, volumes, resource limits, environment variables | When changing the image, workspace path, or resource limits |
| `hermes-docker/hermes-config/config.yaml` | HermesAgent LLM endpoint, storage paths, MCP config | When changing the agent's primary model or data paths |
| `hermes-docker/hermes-config/soul.md` | System prompt (SOUL.md) injected into HermesAgent | When updating SDD orchestration instructions |
| `hermes-docker/hermes-config/mcp_servers.yaml` | MCP server connections for HermesAgent | When adding or removing MCP tools |
| `~/litellm_config.yaml` | Model aliases, API keys, observability callbacks, fallbacks | When adding models, changing ports, adjusting fallbacks, or changing callbacks |
| `~/.config/litellm/env` | LiteLLM API keys + Langfuse credentials (chmod 600) | When rotating Anthropic, Together.ai, or Langfuse keys |
| `~/projects/langfuse-docker/.env` | Langfuse server secrets (NEXTAUTH_SECRET, SALT, POSTGRES_PASSWORD) (chmod 600) | Only if you lose access or need to rotate secrets — requires `docker compose down -v` |
| `~/projects/langfuse-docker/docker-compose.yml` | Langfuse image, port, Postgres | When pinning to a specific Langfuse minor version |
| `schema-service/app/registry.py` | Phase → model alias, token budgets, temperature | When reassigning which model handles each SDD phase |
| `schema-service/app/prompts/*.txt` | System prompts per SDD phase | When tuning model instructions for a phase |
| `.env` (hermes-docker) | `HERMES_IMAGE`, `MINIMAX_API_KEY`, `OPENAI_API_KEY`, `WORKSPACE_PATH` | When rotating API keys, changing the image, or the default workspace |

---

## Troubleshooting

### ❌ LiteLLM not connecting / Schema Service returns 500

**Cause**: LiteLLM is not running, or it started after HermesAgent.

**Fix**:
```bash
# Check if LiteLLM is active
curl -s http://localhost:8002/v1/models

# Start or restart via launchd
launchctl start com.pirito.litellm
# If unresponsive, force restart:
launchctl kickstart -k gui/$(id -u)/com.pirito.litellm

# Logs
tail -f ~/Library/Logs/litellm/stderr.log

# Restart Schema Service after confirming LiteLLM is healthy
```

---

### ❌ Traces not appearing in Langfuse

**Cause**: Langfuse was not running when LiteLLM sent the callback, or the API keys in `~/.config/litellm/env` are incorrect.

**Diagnosis**:
```bash
# Is Langfuse running?
curl -s http://localhost:3000/api/public/health

# Are the keys loaded in LiteLLM?
launchctl list | grep litellm   # should show active PID

# Verify traces exist via API
curl -s http://localhost:3000/api/public/traces?limit=5 \
  -u "pk-lf-...:sk-lf-..."
```

**Fix if Langfuse was down**: bring Langfuse up, restart LiteLLM to reload keys:
```bash
cd ~/projects/langfuse-docker && docker compose up -d
launchctl kickstart -k gui/$(id -u)/com.pirito.litellm
```

---

### ❌ Qwen3 32B :8006 not reachable from Docker

**Cause**: `mlx_lm.server` for :8006 was started without `--host 0.0.0.0`. The default `127.0.0.1` binding is not reachable via `host.docker.internal`.

**Fix**:
```bash
# Kill the current server on :8006
lsof -ti :8006 | xargs kill -9

# Restart with the correct binding
mlx_lm.server --model ~/models/qwen3-32b-mlx --port 8006 --host 0.0.0.0
```

**Verification** (from inside the container):
```bash
docker compose run --rm hermes curl -s http://host.docker.internal:8006/v1/models
```

---

### ❌ MiniMax executing SDD phases itself (not routing to local models)

**Cause**: Schema Service (:8010) or LiteLLM (:8002) is not running when HermesAgent starts. MiniMax falls back to generating content on its own.

**Fix**: Always bring up Schema Service and LiteLLM **before** starting HermesAgent. Verify both:
```bash
curl -s http://localhost:8010/health
curl -s http://localhost:8002/v1/models
```

---

### ❌ hermes-agent container in restart loop

**Cause**: A previous session was started with `docker compose up` instead of `docker compose run`, or with an invalid or outdated CMD. The container has no valid entrypoint when run as a daemon.

**Fix**:
```bash
# Stop and remove the stuck container
docker stop hermes-agent && docker rm hermes-agent

# Always start with run, not up
docker compose run --rm hermes hermes chat
```

**Verify no container is running**:
```bash
docker ps --filter name=hermes-agent
```

---

### ⚠️ SOUL.md lost or not updating

**Cause**: Previously, SOUL.md lived only in the `hermes-data` named volume and could be overwritten on container restart. The fix (Phase 8 quick wins) moved it to the repository as a bind-mount.

**Current state**: `hermes-config/soul.md` is bind-mounted read-only at `/opt/data/SOUL.md` in `docker-compose.yml`. Changes to the host file take effect immediately in the next session — no `docker cp` needed.

**If the container reads a stale SOUL.md**:
```bash
# Confirm the bind-mount is in place
docker inspect hermes-agent | jq '.[].Mounts[] | select(.Destination == "/opt/data/SOUL.md")'

# If missing, recreate with compose run (not docker run)
docker rm -f hermes-agent
docker compose run --rm hermes hermes chat
```

**To recover SOUL.md from the volume** (emergency only, if the repo file has been lost):
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

### ✅ hermes-gentle-ai — gentle-ai orchestration in soul.md (2026-06-03)

- **soul.md rewritten** with 11 sections: gentle-ai orchestration principles adapted to hermes primitives (curl + MCP)
- **Engram migrated REST→MCP**: `curl POST :7437` replaced by `mem_save`/`mem_search`/`mem_get_observation`/`mem_session_summary`
- **LiteLLM model table**: `local-thinking` (propose/design), `local-hermes` (explore/verify/default), `local-coder` (spec/tasks/apply/archive)
- **Full DAG**: `explore → propose → spec/design → tasks → apply → verify → archive` with explicit dependency rules
- **Delegation/cost rules** adapted to curl/bash — no references to Agent/Task/Skill tool
- **Session close protocol** (`mem_session_summary`) now mandatory
- **CLAUDE.md** tagged with 5 sync-tags (`gentle-ai:hermes-portable`) to ease diffing between soul.md and its source

### ✅ Web dashboard + macOS apps (2026-05-31)

- **HermesAgent.app**: launches `hermes dashboard --tui` on :9119 — browser opens automatically with embedded TUI chat
- **HermesStop.app**: cleanly kills hermes-docker container + mcp-proxy
- **mcp-proxy**: new Tier 1b in `agentic-up.sh` — stdio→HTTP/SSE bridge on :7438 for MCP from Docker
- **Engram MCP configured** in hermes-docker: `hermes mcp add engram --url .../mcp`
- **Dynamic project detection**: HermesAgent.app restarts mcp-proxy from the chosen workspace + passes `HERMES_PROJECT` env var to the container
- **docker-compose.yml**: port 9119:9119, `hermes-tui-dist` volume (writable for TUI build)
- **SOUL.md**: uses `$HERMES_PROJECT` to name the project in all Engram MCP calls

### ✅ hermes-native — A/B experiment (archived 2026-05-31)

- Experiment: second container with native capabilities (execute_code + MCP Engram) vs hermes-docker + schema-service
- Result: **STAY** — hermes-docker wins on quality (+15% coherence, +27% specificity)
- hermes-native is faster in workers (-45% latency) but the MiniMax orchestrator consumes ~2M tokens/session (real API cost)
- Archived in Engram: `sdd/hermes-native/archive-report`

### ✅ Phase 9 — hermes-stack-improvements (archived 2026-05-29)

- **Slice 1**: LiteLLM auto-start via launchd — `~/bin/litellm-launch.sh` + plist + `~/.config/litellm/env`
- **Slice 2**: Structured inputs in Schema Service — `ProposeIn`, `SpecIn`, etc. with `context: str` fallback
- **Slice 3**: `_meta` preservation in Engram — `jq` in SOUL.md + `X-SDD-Phase`/`X-SDD-Worker` headers

### ✅ Phase 10a — LLM judge for all phases (archived 2026-05-29)

LLM judge extended from 2 phases (propose, design) to all 6 SDD phases. Adversarial rubrics per phase in `calibration/judge.py`.

### ✅ Phase 10b — Unified startup script (archived 2026-05-29)

`~/bin/agentic-up.sh` — starts all 8 stack components in 4 tiers with parallel health-gating. Idempotent, `--check` mode.

### ✅ Phase 10c — LiteLLM observability via Langfuse (archived 2026-05-29)

Langfuse v2 self-hosted in `~/projects/langfuse-docker/`. Async callbacks in LiteLLM. Traces with model, tokens, latency, and cost. Integrated into `agentic-up.sh` as tier T0.

### ✅ Phase 10d — SDD output schema improvements (archived 2026-05-29)

- **TasksOut**: YAML block at the end of the artifact with `id`, `status` (pending/in_progress/done/skipped), `deps`
- **VerifyReportOut**: Issues section as `| severity | path | description |` table
- **sdd-apply**: YAML-first rule with checklist fallback for older artifacts

---

## Pending / Roadmap

No pending phases. Stack is productive and stable.

Possible future improvements:
- **Open WebUI** — terminal-free chat alternative (mentioned, never decided)
- **HermesStop.app icon** — visually distinguish it from HermesAgent in Spotlight
