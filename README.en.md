[🇪🇸 Español](README.md) | 🇬🇧 English

# Hermes Stack

Most people run local AI models in chat mode. This stack runs them as a **complete engineering ecosystem** — from raw idea to verified, artifact-producing code — with each phase routed to the model best suited for that cognitive task, all observable, all persisted to memory across sessions.

This is not a chatbot setup. It's a local AI engineering environment.

---

## The full pipeline

```
Idea
 │
 ▼  BMAD Planning Layer
 ├─ analyze    → business context, constraints, risks
 ├─ prd        → product requirements document
 ├─ ux         → UI/UX design brief (optional, design-focused phases)
 ├─ architect  → technical architecture decisions
 └─ stories    → structured user stories
       │
       ▼  SDD Implementation Layer
       ├─ explore   → codebase investigation, approach comparison
       ├─ propose   → formal change proposal with scope and tradeoffs
       ├─ spec      → requirements and acceptance scenarios
       ├─ design    → architecture decisions and component breakdown
       ├─ tasks     → ordered, dependency-aware implementation checklist
       ├─ apply     → implementation with work-unit commits
       └─ verify    → validation against spec, CRITICAL / WARNING report
             │
             ▼
          Verified, artifact-backed code
          persisted in Engram for future sessions
```

Most tools give you a coding assistant. This gives you the full engineering process — structured, reproducible, model-aware at every step.

---

## What is Hermes?

Hermes is an [OpenCode](https://github.com/opencode-ai/opencode) agent configured as an SDD orchestrator. OpenCode is an open-source terminal AI coding assistant — think Claude Code, but self-hostable and model-agnostic.

Out of the box, OpenCode is a capable coding agent. Hermes layers on top of it:

- A **soul** (`soul.md`) that defines its role: thin orchestrator, coordinates phases, never implements inline
- A **LiteLLM proxy** that routes each phase to the optimal local or cloud model
- A **dual memory system** for both session context and cross-session persistence
- A **skill injector** that automatically loads coding standards per request
- A **Design MCP** for UI/UX knowledge without external calls
- A **full BMAD + SDD workflow** implemented in Schema Service

---

## Model-per-phase routing

Every phase has a different cognitive profile. Reasoning models excel at tradeoffs and architecture; coding models are faster and more precise at structured output and implementation; broad-context models handle exploration and qualitative judgment.

```
BMAD analyze / prd / architect   →  DeepSeek R1 32B      (deep reasoning)
BMAD ux                          →  Hermes 3 70B          (design + broad context)
BMAD stories                     →  Qwen 2.5-Coder 32B   (structured output)

SDD explore / verify             →  Hermes 3 70B          (qualitative judgment)
SDD propose / design             →  DeepSeek R1 32B       (architectural decisions)
SDD spec / tasks / apply         →  Qwen 2.5-Coder 32B   (precision + code gen)
```

All routing is configured via aliases in `litellm/litellm_config.yaml`. Swap a model, change a port, or point an alias to Anthropic — zero changes to the agent.

---

## Dual memory system

Hermes has two memory layers that work together:

### Session memory (OpenCode native)
Within a session, full conversation context — tool calls, file reads, decisions made. Standard for any AI coding agent.

### Cross-session memory (Engram)
Engram is a persistent memory MCP server on `:7437`. Hermes writes to it via MCP tools and reads from it at the start of every session. What gets persisted:

- **SDD + BMAD artifacts** — every phase output stored by topic key, retrievable in future sessions
- **Decisions** — architecture choices, tradeoffs considered, direction taken
- **Bug fixes** — root cause + fix, so the agent never repeats the same mistake
- **Discoveries** — non-obvious findings about the codebase, gotchas, edge cases
- **Session summaries** — structured end-of-session saves so the next session starts informed

This is what separates agentic workflows from chat. Chat forgets. Hermes doesn't.

---

## Automatic skill injection

Before every LLM request, `skill_injector.py` (a LiteLLM `CustomLogger`) scans `~/.claude/skills/` and prepends the relevant coding standards to the system message — automatically, without any instruction from the agent.

The skills library currently covers:

| Domain | Skills |
|--------|--------|
| **Frontend** | React 19, React Enterprise SPA, Next.js 15, Angular (architecture, core, forms, performance), Tailwind 4, Zustand 5, Zod 4, AI SDK 5 |
| **UI/UX** | frontend-design, web-designer-expert |
| **Backend** | Django DRF, .NET backend, .NET MCP server, Go testing, pytest |
| **Language** | TypeScript, Playwright |
| **Dev workflow** | SDD (9 phases), branch-pr, chained-pr, github-pr, work-unit-commits, Jira (epic, task), issue-creation |
| **Code quality** | comment-writer, cognitive-doc-design, project-review, lessons-learnt, judgment-day |

Every model that sits behind LiteLLM — local or cloud — benefits from this injection automatically.

---

## UI/UX knowledge base

`hermes-design-mcp` is a FastMCP SSE server backed by a BM25 search engine over 14 curated CSV datasets covering design systems, color palettes, typography, icons, UX guidelines, component patterns, and framework-specific guidance.

Hermes calls it before answering any design question or generating UI. Three tools:

- `design_search(query, domain?)` — targeted lookup (color, typography, icons, UX, landing, charts...)
- `design_search_stack(query, stack)` — framework-specific guidance (React, Next.js, Tailwind, shadcn, SwiftUI...)
- `design_system(query, project_name?)` — generate a full design system for a new project

No external calls. No design tokens invented from training data.

---

## Architecture

```
You
 │  macOS launcher (Spotlight → HermesAgent.app)
 ▼
Hermes (Docker)  ─────────────────────────────────────────────────
  OpenCode agent (BMAD + SDD orchestrator)    port 9119 (web TUI)
  soul.md → persona + orchestration rules (bind-mounted :ro)
  │
  ├──► Schema Service  :8010  (FastAPI — executes BMAD + SDD phases)
  │      /v1/bmad/*  — analyze, prd, ux, architect, stories
  │      /v1/sdd/*   — explore, propose, spec, design, tasks, apply, verify
  │
  │  All LLM calls → LiteLLM proxy
  ▼
LiteLLM Proxy  :8002 ─────────────────────────────────────────────
  skill_injector.py → injects coding standards per request
  Routes by alias:
    local-hermes    → Hermes 3 70B        :8006  (explore, verify, bmad-ux)
    local-thinking  → DeepSeek R1 32B     :8001  (propose, design, bmad-analyze/prd/architect)
    local-coder     → Qwen 2.5-Coder 32B  :8000  (spec, tasks, apply, bmad-stories)
    local-devstral  → Devstral 24B        :8005  (fallback / tool calling)
    claude-sonnet   → Anthropic API             (cloud fallback)
  │
  ├──► Langfuse  :3000  (traces, costs, evals — every request logged)
  │
  ├──► Engram  :7437  (cross-session memory — MCP via proxy :7438)
  │
  └──► hermes-design-mcp  :8012  (UI/UX knowledge base — 14 datasets)
```

---

## Components

| Directory | Role |
|-----------|------|
| `hermes-docker/` | OpenCode agent in Docker — config, soul.md, launchers, RUNBOOK |
| `schema-service/` | FastAPI that executes all BMAD and SDD phases via structured LLM |
| `hermes-design-mcp/` | MCP server for UI/UX design knowledge base |
| `langfuse-docker/` | Observability dashboard (traces, costs, evals) |
| `litellm/` | LiteLLM proxy config + skill injector + launch script |
| `bin/` | Stack management scripts (startup, proxies, Engram) |

---

## Schema Service

`schema-service/` is the execution layer of the stack. Hermes orchestrates, but never generates SDD or BMAD content itself — it always delegates to Schema Service via `curl`.

It is a FastAPI + [Instructor](https://github.com/jxnl/instructor) + Pydantic v2 API. Instructor forces local models to return structured, schema-validated JSON — no format hallucinations, no fragile parsing.

```
schema-service/
├── app/
│   ├── routes/
│   │   ├── sdd.py       # /v1/sdd/* endpoints (explore, propose, spec, design, tasks, apply, verify)
│   │   └── bmad.py      # /v1/bmad/* endpoints (analyze, prd, ux, architect, stories)
│   ├── schemas/         # Pydantic input/output models per phase
│   ├── prompts/         # system prompts per phase (.txt)
│   └── registry.py      # model→alias→endpoint table (authoritative routing source)
└── calibration/         # phase quality evaluation harness
```

Start:
```bash
cd schema-service
pip install -e .
uvicorn app.main:app --host 0.0.0.0 --port 8010
```

Or via `bin/agentic-up.sh`, which starts it automatically in the correct order.

---

## Engram — persistent memory

Engram is the stack's memory server, developed by [Gentleman Programming](https://github.com/Gentleman-Programming/engram). It provides cross-session persistence via MCP tools — Hermes uses it to store SDD/BMAD artifacts, decisions, resolved bugs, and session summaries.

**Install:**
```bash
brew install engram
```

**Access architecture:**

Hermes runs in Docker and cannot call a stdio process directly. The stack uses `mcp-proxy` as a bridge:

```
Hermes (Docker)
  │  MCP HTTP/SSE  →  :7438
  ▼
mcp-proxy (:7438)     ← bin/engram-mcp-proxy-run.sh (managed by launchd)
  │  stdio
  ▼
engram mcp --tools=agent
  │  REST
  ▼
Engram (:7437)        ← main Engram process
```

`bin/engram-mcp-proxy-run.sh` reads the active workspace from `~/.hermes-current-workspace` and starts `mcp-proxy` from that directory — so Engram automatically detects the correct project.

**launchd** manages this automatically on macOS. The `com.pirito.litellm` and `com.pirito.engram-mcp-proxy` plists start these services at login.

---

## Prerequisites

- **Docker Desktop** — for Hermes and Langfuse
- **Python 3.11+** — for LiteLLM proxy and Design MCP server
- **LiteLLM** — `pip install litellm`
- **API keys** — Anthropic (required for cloud fallback), local MLX models (optional)

Local models run via `mlx_lm.server` on Apple Silicon. If you only have Anthropic keys, point the aliases to `claude-sonnet` / `claude-haiku` in `litellm_config.yaml` — the rest of the stack works identically.

---

## Secrets setup

Secrets live outside the repo in `~/.config/litellm/env`, sourced at runtime:

```bash
mkdir -p ~/.config/litellm
cat > ~/.config/litellm/env <<EOF
ANTHROPIC_API_KEY=sk-ant-...
TOGETHER_API_KEY=...           # optional
LITELLM_MASTER_KEY=hermes-local-dev
EOF
```

`litellm/bin/litellm-launch.sh` sources this file automatically. Never commit it.

For Docker Compose variables copy `.env.example` → `.env`. `bash install.sh` does this for you.

---

## Quick start

> **Local models**: if you want to run MLX models locally instead of cloud APIs, read first → [docs/local-models.md](docs/local-models.md)

```bash
# 1. Clone and bootstrap
git clone git@github.com:toniJC/hermes-stack.git
cd hermes-stack
bash install.sh

# 2. Set up secrets (see above)

# 3. Install Engram
brew install engram

# 4. Install launchd services (auto-start at login)
mkdir -p ~/bin
cp bin/agentic-up.sh bin/devstral-proxy.py bin/engram-mcp-proxy-run.sh ~/bin/
cp litellm/bin/litellm-launch.sh ~/bin/
bash bin/launchd/install.sh

# 5. Start the full stack
bash bin/agentic-up.sh
```

`agentic-up.sh` starts services in order with health-gating between tiers:

```
T0  LiteLLM proxy     :8002   (launchd — starts automatically at login)
T1  Engram            :7437
T1b Engram MCP proxy  :7438
T2  MLX models        :8000 :8001 :8006  (in parallel)
    Devstral llama    :8004
T3  Devstral proxy    :8005
T4  Schema Service    :8010
```

Idempotent — already-running services are skipped. Diagnostic mode: `bash bin/agentic-up.sh --check`

Then start Hermes:
```bash
cd hermes-docker && docker compose up -d
```

Optional — Design MCP:
```bash
cd hermes-design-mcp && bash run.sh
```

Hermes web UI → http://localhost:9119

For health checks, troubleshooting, and update procedures → [hermes-docker/RUNBOOK.md](hermes-docker/RUNBOOK.md)

---

## soul.md

`hermes-docker/hermes-config/soul.md` is Hermes's persona and operating instructions — the equivalent of `CLAUDE.md` in Claude Code, but for this agent. Bind-mounted read-only into the container at startup. Changes take effect on the next `docker compose up`.

20 sections, each defining an explicit contract. The most important ones:

### The core principle: thin client

Hermes **coordinates**, never implements. All execution logic lives in Schema Service. All persistence lives in Engram. Hermes is the conductor — it never plays an instrument.

```
NEVER generate SDD content yourself.
ALWAYS call Schema Service via curl.
NEVER use curl to reach Engram — MCP only.
```

### First action: project detection

The first thing Hermes does on startup:

```bash
echo $HERMES_PROJECT
```

This value is passed explicitly in **every** MCP call to Engram. Without it, memory doesn't know which project the artifact belongs to.

### Engram protocol (memory)

Proactive saves are mandatory — without being asked — after any of these:
- Phase result received and validated
- Architecture decision made
- Bug or error resolved
- Non-obvious codebase discovery
- Session end (`mem_session_summary`)

Retrieval is always a two-step process — search results are truncated previews of 300 chars and **must never** be used as source material:

```
1. mem_search(query: "sdd/{change}/{phase}", project: "$HERMES_PROJECT") → get ID
2. mem_get_observation(id: <ID>) → full content
```

### Phase discipline

Local models tend to bleed responsibilities across phases. soul.md prevents this with a simple rule: **one phase per turn, named explicitly at the start**.

| Phase | Your job this turn | You will NOT |
|-------|-------------------|--------------|
| explore | Read files, map structure | Modify or propose solutions |
| propose | Problem, scope, approach | Write spec, design, or code |
| spec | WHAT (requirements, criteria) | Decide HOW or pick architecture |
| design | HOW (architecture, tradeoffs) | Write task lists or implement |
| tasks | Ordered breakdown of design | Implement them |
| apply | Implement current batch | Redesign or expand scope |
| verify | Compare implementation to spec | Fix code inline |
| archive | Close and persist final state | Reopen decisions |

### BMAD → SDD handoff

When BMAD completes `stories`, Hermes retrieves the three key artifacts from Engram (`prd`, `architect`, `stories`), assembles them with `jq`, and calls `POST /v1/sdd/propose` — starting the SDD cycle with full business context already embedded.

### Session close

Before ending any session, `mem_session_summary` is **mandatory**. Skip it, and the next session starts blind.

---

## Companion repo

Claude Code configuration (CLAUDE.md, SDD agents, slash commands, 40+ skills) lives in:
[https://github.com/toniJC/dotfiles](https://github.com/toniJC/dotfiles)

Clone it and run `bash install.sh` to symlink `~/.claude` from the versioned config.
