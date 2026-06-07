# Hermes Stack

Local AI agent stack combining Hermes (OpenCode agent), LiteLLM proxy, Langfuse observability, and a Design MCP server — all running on your machine with no cloud dependency beyond API keys.

This repo is one half of a two-repo setup:
- **hermes-stack** (this repo) — services, config, and scripts
- **dotfiles** — Claude Code config (`~/.claude/`) as a versioned symlink

---

## Architecture

| Component | Directory | Role |
|-----------|-----------|------|
| Hermes Docker | `hermes-docker/` | OpenCode AI agent running in Docker |
| Hermes Native | `hermes-native/` | Native (non-Docker) agent variant |
| Hermes Native Baseline | `hermes-native-baseline/` | Baseline config for hermes-native |
| Design MCP | `hermes-design-mcp/` | MCP server providing design context to agents |
| Langfuse | `langfuse-docker/` | Observability dashboard (traces, costs, eval) |
| LiteLLM | `litellm/` | OpenAI-compatible proxy routing to Anthropic + local models |

---

## Secrets Setup

Secrets are kept out of this repo and loaded at runtime:

1. Create `~/.config/litellm/env` with your API keys:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   TOGETHER_API_KEY=...
   LITELLM_MASTER_KEY=hermes-local-dev
   ```
2. This file is sourced by `litellm/bin/litellm-launch.sh` before starting the proxy.
3. Never commit this file — it is not inside this repo.

See `.env.example` at the root for all variables used by Docker Compose services.

---

## Quick Start

```bash
# 1. Clone and bootstrap
git clone <this-repo-url> hermes-stack
cd hermes-stack
bash install.sh          # creates .env from .env.example

# 2. Fill in your secrets
#    - Edit .env for Docker Compose variables
#    - Edit ~/.config/litellm/env for LiteLLM API keys

# 3. Start services (order matters)
cd langfuse-docker && docker compose up -d    # Observability first
cd ../litellm && bash bin/litellm-launch.sh   # LiteLLM proxy
cd ../hermes-docker && docker compose up -d   # Hermes agent

# 4. (Optional) Start Design MCP
cd hermes-design-mcp && bash run.sh
```

For full operational docs including health checks, troubleshooting, and update procedures, see [hermes-docker/RUNBOOK.md](hermes-docker/RUNBOOK.md).

---

## Companion Repo

Claude Code configuration (CLAUDE.md, SDD agents, slash commands, skills) lives in the dotfiles repo:
[https://github.com/placeholder/dotfiles](https://github.com/placeholder/dotfiles)

Clone it and run its `install.sh` to symlink `~/.claude` from the versioned config.
