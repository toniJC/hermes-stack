# Hermes Stack

Most people run local AI models in chat mode. This stack runs them **agentically** — the same way Claude Code orchestrates Claude, but with your own local models, each one assigned to the cognitive task it's best at.

Hermes is an SDD orchestrator that executes structured development workflows (explore → propose → spec → design → tasks → apply → verify). Every phase is routed through LiteLLM to the model that fits the job: a reasoning model for architecture decisions, a coding model for implementation, a general model for exploration. You decide the mapping. The agent just calls an alias.

```
propose / design   →  DeepSeek R1 32B      (reasoning — needs to think through tradeoffs)
spec / tasks       →  Qwen 2.5-Coder 32B   (structured output — fast and precise)
apply              →  Qwen 2.5-Coder 32B   (code generation)
explore / verify   →  Hermes 3 70B         (broad context, qualitative judgment)
```

No cloud required. No per-token cost for local phases. No chat window — structured, reproducible, artifact-producing workflows that persist to memory (Engram) and are observable in Langfuse.

This repo is one half of a two-repo setup:
- **hermes-stack** (this repo) — services, config, and scripts
- **[dotfiles](https://github.com/toniJC/dotfiles)** — Claude Code config (`~/.claude/`) as a versioned symlink

---

## How model routing works

LiteLLM acts as an OpenAI-compatible proxy. Each model is registered under an alias:

```yaml
# litellm/litellm_config.yaml (simplified)
models:
  - model_name: local-thinking    # alias Hermes calls
    litellm_params:
      model: openai/deepseek-r1   # actual model on :8001
      api_base: http://localhost:8001/v1

  - model_name: local-coder
    litellm_params:
      model: openai/qwen-coder
      api_base: http://localhost:8000/v1
```

Hermes calls `local-thinking` or `local-coder` — it never knows (or cares) what model is behind the alias. Swap a model, change a port, point an alias to Anthropic instead — zero changes to the agent.

---

## Automatic skill injection

Before every LLM request, `skill_injector.py` (a LiteLLM `CustomLogger`) scans `~/.claude/skills/` and prepends the relevant coding standards to the system message — automatically. Hermes gets React patterns when working on a React project, .NET patterns for a .NET project, without any explicit instruction.

This is the same mechanism that makes Claude Code context-aware, replicated at the proxy layer so every model benefits from it.

---

## Architecture

```
You
 │  macOS launcher (Spotlight → HermesAgent.app)
 ▼
Hermes (Docker)  ─────────────────────────────────────────────────
  OpenCode AI agent                    port 9119 (web TUI)
  Reads soul.md on startup (persona + SDD orchestration rules)
  │
  │  All LLM calls → LiteLLM proxy
  ▼
LiteLLM Proxy  :8002 ─────────────────────────────────────────────
  skill_injector.py → injects coding standards per request
  Routes by alias:
    local-thinking  → DeepSeek R1 32B   :8001
    local-coder     → Qwen 2.5-Coder    :8000
    local-hermes    → Hermes 3 70B      :8006
    local-devstral  → Devstral 24B      :8005
    claude-sonnet   → Anthropic API     (cloud fallback)
    minimax-text    → Together.ai API   (cloud fallback)
  │
  ├──► Langfuse  :3000  (traces, costs, evals — every request logged)
  │
  └──► hermes-design-mcp  :8012
         FastMCP SSE server
         BM25 search over 14 UI/UX CSV datasets
         Tools: search_design, search_stack, generate_design_system
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

Local models run via `mlx_lm.server` on Apple Silicon. If you only have Anthropic keys, the stack works with `claude-sonnet` and `claude-haiku` aliases — just skip the MLX servers.

---

## Secrets Setup

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

Hermes web UI: http://localhost:9119

For health checks, troubleshooting, and update procedures → [hermes-docker/RUNBOOK.md](hermes-docker/RUNBOOK.md)

---

## soul.md

`hermes-docker/hermes-config/soul.md` is the agent's persona and operating instructions — equivalent to `CLAUDE.md` in Claude Code, but for Hermes. It's bind-mounted read-only into the container at startup.

It defines Hermes's role as a thin SDD orchestrator: it coordinates, Schema Service executes, Engram persists. Edit this file to change how the agent behaves. Changes take effect on the next `docker compose up`.

---

## Companion Repo

Claude Code configuration (CLAUDE.md, SDD agents, slash commands, 40+ skills) lives in:
[https://github.com/toniJC/dotfiles](https://github.com/toniJC/dotfiles)

Clone it and run `bash install.sh` to symlink `~/.claude` from the versioned config.
