# hermes-native

Versioned configuration templates for the native (non-Docker) Hermes install, wired to the local hermes-stack.

## What is this?

Native Hermes Desktop (`~/.hermes/`) points to the local AI stack instead of cloud providers:

- **Model**: LiteLLM proxy at `localhost:8002` with alias `hermes-orchestrator`
- **Engram MCP**: SSE server at `localhost:7438`
- **Design MCP**: SSE server at `localhost:8012`

These templates are the single source of truth for the live `~/.hermes/` config. Keep them in sync when you make changes.

## Files

| File | Destination | Notes |
|------|-------------|-------|
| `config.yaml` | `~/.hermes/config.yaml` | Model + MCP wiring |
| `SOUL.md` | `~/.hermes/SOUL.md` | System prompt (host.docker.internal replaced with localhost) |
| `env.example` | `~/.hermes/.env` (append) | Key placeholder — never commit real secrets |

## Install

```bash
# 1. Copy config
cp config.yaml ~/.hermes/config.yaml

# 2. Copy SOUL.md
cp SOUL.md ~/.hermes/SOUL.md

# 3. Append key to .env (append-only — do NOT overwrite existing entries)
echo "OPENAI_API_KEY=hermes-local-dev" >> ~/.hermes/.env
```

## Sync rules

- **config.yaml**: Edit here first, then copy to `~/.hermes/`. Keep the diff empty (`diff config.yaml ~/.hermes/config.yaml`).
- **SOUL.md**: Derived from `/Users/pirito/projects/hermes-docker/hermes-config/soul.md`. After the Docker source changes, re-derive:
  ```bash
  sd 'host\.docker\.internal' 'localhost' \
    < /Users/pirito/projects/hermes-docker/hermes-config/soul.md \
    > SOUL.md
  cp SOUL.md ~/.hermes/SOUL.md
  # Verify: rg host.docker.internal SOUL.md  (must return zero results)
  ```
  `soul-bmad.md` (sibling file in `hermes-native/`) contains the extracted BMAD sections (S12–S17) from the Docker soul.md. When updating the Docker container's `hermes-config/soul.md`, also sync `soul-bmad.md` alongside `SOUL.md` if the BMAD sections changed.
- **env.example**: Placeholder only. Real API keys live in `~/.hermes/.env` and are NEVER committed.

## Constraints

- Do NOT copy or modify files under `hermes-docker/hermes-config/`. That directory is Docker-only and read-only from native's perspective.
- Do NOT symlink `SOUL.md` to the Docker source — the Docker file contains `host.docker.internal` addresses that do not resolve from the host.
- `OPENAI_API_KEY=hermes-local-dev` is the LiteLLM master key. It is not a real cloud credential.

## Rollback

```bash
# Restore a previous working config from git
git checkout HEAD~1 -- config.yaml SOUL.md
cp config.yaml ~/.hermes/config.yaml
cp SOUL.md ~/.hermes/SOUL.md
```
