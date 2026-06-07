# Hermes Stack

Most people run local AI models in chat mode. This stack runs them **agentically** — structured, multi-phase development workflows where each phase is routed to the model best suited for that cognitive task, all observable, all persisted to memory across sessions.

This is not a chatbot setup. It's a local AI engineering environment.

---

## What is Hermes?

Hermes is an [OpenCode](https://github.com/opencode-ai/opencode) agent configured as an SDD (Spec-Driven Development) orchestrator. OpenCode is an open-source terminal AI coding assistant — think Claude Code, but self-hostable and model-agnostic.

Out of the box, OpenCode is a capable coding agent. Hermes layers on top of it:

- A **soul** (`soul.md`) that defines its role: thin orchestrator, never implements inline, always delegates to Schema Service and persists to Engram
- A **LiteLLM proxy** that routes each SDD phase to the optimal local or cloud model
- A **dual memory system** that gives it both session context and cross-session persistence
- A **skill injector** that automatically loads the right coding standards for every request
- A **Design MCP** that gives it access to a curated UI/UX knowledge base

The result: an agent that behaves like Claude Code — structured, context-aware, artifact-producing — but runs your own models on your own hardware.

---

## Model-per-phase routing

Every SDD phase has a different cognitive profile. A reasoning model excels at architectural tradeoffs; a coding model is faster and more precise at generating structured output. LiteLLM lets you assign the right model to each phase via simple aliases — the agent never knows what's behind them.

```
explore / verify   →  Hermes 3 70B        (broad context, qualitative judgment)
propose / design   →  DeepSeek R1 32B     (deep reasoning — needs to think through tradeoffs)
spec / tasks       →  Qwen 2.5-Coder 32B  (structured output — fast and precise)
apply              →  Qwen 2.5-Coder 32B  (code generation)
```

Swap a model, change a port, or point an alias to Anthropic — zero changes to the agent.

```yaml
# litellm/litellm_config.yaml (simplified)
models:
  - model_name: local-thinking     # alias Hermes calls
    litellm_params:
      model: openai/deepseek-r1    # actual model on :8001
      api_base: http://localhost:8001/v1

  - model_name: local-coder
    litellm_params:
      model: openai/qwen-coder
      api_base: http://localhost:8000/v1
```

---

## Dual memory system

This is one of the most underappreciated parts of the stack. Hermes has two memory layers that work together:

### 1. Session memory (OpenCode native)
Within a session, Hermes maintains full conversation context — tool calls, file reads, decisions made. Standard for any AI coding agent.

### 2. Cross-session memory (Engram)
Engram is a persistent memory MCP server running on `:7437`. Hermes writes to it via MCP tools (`mem_save`, `mem_search`, `mem_get_observation`) and reads from it at the start of every session.

What gets persisted:
- **SDD artifacts** — every phase output (proposal, spec, design, tasks, apply-progress, verify report) stored by topic key
- **Decisions** — architecture choices, tradeoffs considered, direction taken
- **Bug fixes** — root cause + fix, so the agent never repeats the same mistake
- **Discoveries** — non-obvious findings about the codebase, gotchas, edge cases
- **Session summaries** — at the end of every session, a structured summary is saved so the next session starts with full context

The practical effect: Hermes remembers what it built last week, why it made that architecture call, and what bugs it already solved — across restarts, across projects.

This is what separates agentic workflows from chat. Chat forgets. Hermes doesn't.

---

## Automatic skill injection

Before every LLM request, `skill_injector.py` (a LiteLLM `CustomLogger`) scans `~/.claude/skills/` and prepends the relevant coding standards to the system message — automatically, without any instruction from the agent.

Hermes gets React patterns when working on a React project, .NET patterns for a .NET project. Every model that sits behind LiteLLM benefits from this, including local ones.

---

## Architecture

```
You
 │  macOS launcher (Spotlight → HermesAgent.app)
 ▼
Hermes (Docker)  ─────────────────────────────────────────────────
  OpenCode agent (SDD orchestrator)       port 9119 (web TUI)
  soul.md defines persona + routing rules (bind-mounted :ro)
  │
  │  All LLM calls → LiteLLM proxy
  ▼
LiteLLM Proxy  :8002 ─────────────────────────────────────────────
  skill_injector.py → injects coding standards per request
  Routes by alias:
    local-hermes    → Hermes 3 70B        :8006  (explore, verify)
    local-thinking  → DeepSeek R1 32B     :8001  (propose, design)
    local-coder     → Qwen 2.5-Coder 32B  :8000  (spec, tasks, apply)
    local-devstral  → Devstral 24B        :8005  (fallback)
    claude-sonnet   → Anthropic API             (cloud fallback)
  │
  ├──► Langfuse  :3000  (traces, costs, evals — every request logged)
  │
  └──► Engram  :7437  (cross-session memory — MCP via proxy :7438)
  │
  └──► hermes-design-mcp  :8012
         FastMCP SSE server
         BM25 search over 14 UI/UX CSV datasets
         Tools: design_search, design_search_stack, design_system
```

---

## Components

| Directory | Role |
|-----------|------|
| `hermes-docker/` | OpenCode agent in Docker — config, soul.md, launchers, RUNBOOK |
| `hermes-design-mcp/` | MCP server for UI/UX design knowledge base |
| `langfuse-docker/` | Observability dashboard (traces, costs, evals) |
| `litellm/` | LiteLLM proxy config + skill injector + launch script |

---

## Prerequisites

- **Docker Desktop** — for Hermes and Langfuse
- **Python 3.11+** — for LiteLLM proxy and Design MCP server
- **LiteLLM** — `pip install litellm`
- **API keys** — Anthropic (required for cloud fallback), local MLX models (optional)

Local models run via `mlx_lm.server` on Apple Silicon. If you only have Anthropic keys, point the aliases to `claude-sonnet` and `claude-haiku` in `litellm_config.yaml` — the rest of the stack works identically.

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

`litellm/bin/litellm-launch.sh` sources this file before starting the proxy. Never commit it.

For Docker Compose variables (Langfuse DB password, etc.) copy `.env.example` → `.env`. `bash install.sh` does this automatically.

---

## Quick Start

```bash
# 1. Clone and bootstrap
git clone git@github.com:toniJC/hermes-stack.git
cd hermes-stack
bash install.sh

# 2. Set up secrets (see above)

# 3. Start services (order matters)
cd langfuse-docker  && docker compose up -d          # observability first
cd ../litellm       && bash bin/litellm-launch.sh    # LiteLLM proxy + skill injector
cd ../hermes-docker && docker compose up -d          # Hermes agent

# 4. (Optional) Start Design MCP
cd hermes-design-mcp && bash run.sh
```

Hermes web UI → http://localhost:9119

For health checks, troubleshooting, and update procedures → [hermes-docker/RUNBOOK.md](hermes-docker/RUNBOOK.md)

---

## soul.md

`hermes-docker/hermes-config/soul.md` is Hermes's persona and operating instructions — the equivalent of `CLAUDE.md` in Claude Code, but for this agent. It's bind-mounted read-only into the container at startup.

It defines the orchestration contract: Hermes coordinates, Schema Service executes phases, Engram persists everything. Edit it to change how the agent reasons, what it prioritizes, or how it routes work.

---

## Companion repo

Claude Code configuration (CLAUDE.md, SDD agents, slash commands, 40+ skills) lives in:
[https://github.com/toniJC/dotfiles](https://github.com/toniJC/dotfiles)

Clone it and run `bash install.sh` to symlink `~/.claude` from the versioned config.
