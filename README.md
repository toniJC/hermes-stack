# Hermes Stack

A fully local AI agent stack. Hermes runs in Docker as an SDD orchestrator, routes all LLM calls through a LiteLLM proxy that automatically injects coding standards, and logs every trace to Langfuse. A companion Design MCP server gives the agent access to a curated UI/UX knowledge base.

This repo is one half of a two-repo setup:
- **hermes-stack** (this repo) — services, config, and scripts
- **[dotfiles](https://github.com/toniJC/dotfiles)** — Claude Code config (`~/.claude/`) as a versioned symlink

---

## Why this exists

Running an AI agent directly against Anthropic's API works, but you lose three things:
- **Skill injection** — there's no layer to automatically prepend coding standards to every request
- **Local model routing** — switching between Anthropic, Together.ai, and local MLX models requires code changes
- **Observability** — no traces, no cost tracking, no way to replay what the agent did

This stack adds all three without changing how the agent is invoked.

---

## Architecture

```
You
 │  macOS launcher (Spotlight → HermesAgent.app)
 ▼
Hermes (Docker) ──────────────────────────────────────────────────
  OpenCode AI agent                    port 9119 (web TUI)
  Reads soul.md on startup (persona + SDD instructions)
  │
  │  All LLM calls go through LiteLLM proxy
  ▼
LiteLLM Proxy  :8002 ─────────────────────────────────────────────
  OpenAI-compatible router
  skill_injector.py fires on every request:
    → scans ~/.claude/skills/ for matching coding standards
    → prepends them to the system message automatically
  Routes to:
    anthropic/claude-*     (Anthropic API)
    openai/MiniMax-M2.7    (Together.ai)
    openai/<model>         (local MLX servers on :8000–:8006)
  │
  ├──► Langfuse  :3000  (traces, costs, evals)
  │
  └──► Local MLX models (optional)
         :8000  Qwen 2.5-Coder 32B   → spec, tasks, apply
         :8001  DeepSeek R1 32B      → propose, design
         :8005  Devstral 24B         → fallback / tool calling
         :8006  Hermes 3 70B         → explore, verify
  │
  ▼
hermes-design-mcp  :8012 ─────────────────────────────────────────
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
- **LiteLLM** — `pip install litellm` (or install via the mlx virtualenv)
- **API keys** — Anthropic (required), Together.ai (optional), local MLX servers (optional)

Local MLX models are optional. If you only have Anthropic API keys, the stack works with `opus`, `sonnet`, and `haiku` aliases out of the box.

---

## Secrets Setup

Secrets are kept out of this repo and loaded at runtime from `~/.config/litellm/env`:

```bash
mkdir -p ~/.config/litellm
cat > ~/.config/litellm/env <<EOF
ANTHROPIC_API_KEY=sk-ant-...
TOGETHER_API_KEY=...           # optional
LITELLM_MASTER_KEY=hermes-local-dev
EOF
```

This file is sourced automatically by `litellm/bin/litellm-launch.sh`. Never commit it.

For Docker Compose variables (Langfuse DB password, etc.) copy `.env.example` to `.env` and fill in the values — `bash install.sh` does this for you.

---

## Quick Start

```bash
# 1. Clone and bootstrap
git clone git@github.com:toniJC/hermes-stack.git
cd hermes-stack
bash install.sh          # creates .env from .env.example

# 2. Set up secrets (see above)

# 3. Start services (order matters)
cd langfuse-docker  && docker compose up -d          # observability first
cd ../litellm       && bash bin/litellm-launch.sh    # LiteLLM proxy
cd ../hermes-docker && docker compose up -d          # Hermes agent

# 4. (Optional) Start Design MCP
cd hermes-design-mcp && bash run.sh
```

Hermes web UI: http://localhost:9119

For health checks, troubleshooting, and update procedures → [hermes-docker/RUNBOOK.md](hermes-docker/RUNBOOK.md)

---

## soul.md

`hermes-docker/hermes-config/soul.md` is the agent's persona and operating instructions — the equivalent of `CLAUDE.md` but for Hermes. It's bind-mounted read-only into the container at startup.

It defines:
- Hermes's role as a thin SDD orchestrator (it coordinates, Schema Service executes)
- How to detect the active project (`$HERMES_PROJECT`)
- Engram MCP protocol (how to persist memory)
- SDD phase routing rules

Edit this file to change how Hermes behaves. Changes take effect on the next `docker compose up`.

---

## skill_injector.py

`litellm/skill_injector.py` is a LiteLLM `CustomLogger` that fires before every LLM request. It scans `~/.claude/skills/` for skill files matching the current request context and prepends the relevant coding standards to the system message — automatically, without any change to how Hermes calls the API.

This means Hermes always has the right standards loaded (React, TypeScript, .NET, etc.) without needing to know which project it's working on.

---

## Companion Repo

Claude Code configuration (CLAUDE.md, SDD agents, slash commands, skills) lives in:
[https://github.com/toniJC/dotfiles](https://github.com/toniJC/dotfiles)

Clone it and run `bash install.sh` to symlink `~/.claude` from the versioned config.
