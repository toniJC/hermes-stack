[🇪🇸 Español](local-models.md) | 🇬🇧 English

# Local models guide

This guide covers how to set up the MLX environment and download the local models to run the stack without relying on cloud APIs.

> **Hardware requirement**: Apple Silicon (M1 Pro or higher). The 32B models require at least 32 GB of unified RAM; the 70B model requires 64 GB or more.

---

## 1. Create the MLX virtual environment

The stack assumes a virtualenv at `~/projects/mlx-qwen/mlx_env/`. This environment contains `mlx_lm`, `mcp-proxy`, and the rest of the local dependencies.

```bash
mkdir -p ~/projects/mlx-qwen
python3.11 -m venv ~/projects/mlx-qwen/mlx_env
source ~/projects/mlx-qwen/mlx_env/bin/activate
```

Install dependencies:

```bash
pip install --upgrade pip

# MLX runtime and model server
pip install mlx mlx-lm

# MCP proxy (stdio→HTTP bridge for Docker)
pip install mcp-proxy

# Schema Service dependencies (optional here if you prefer to install in its own venv)
pip install fastapi uvicorn instructor openai httpx pydantic

# MCP SDK
pip install mcp
```

Verify:

```bash
mlx_lm.server --help   # should display options
mcp-proxy --version    # should display version
```

---

## 2. Download the models

Create the models directory:

```bash
mkdir -p ~/models
```

### Qwen 2.5-Coder 32B (alias: `local-coder` — spec, tasks, apply)

```bash
source ~/projects/mlx-qwen/mlx_env/bin/activate
mlx_lm.convert \
  --hf-path mlx-community/Qwen2.5-Coder-32B-Instruct-4bit \
  --mlx-path ~/models/qwen2.5-coder-32b-mlx \
  --upload-repo ""
```

Or direct download from HuggingFace:
```bash
huggingface-cli download mlx-community/Qwen2.5-Coder-32B-Instruct-4bit \
  --local-dir ~/models/qwen2.5-coder-32b-mlx
```

Approximate size: **18 GB**

---

### DeepSeek R1 Distill 32B (alias: `local-thinking` — propose, design)

```bash
huggingface-cli download mlx-community/DeepSeek-R1-Distill-Qwen-32B-4bit \
  --local-dir ~/models/deepseek-r1-32b-mlx
```

Approximate size: **18 GB**

---

### Qwen3 32B (alias: `local-hermes` / `hermes-orchestrator` — explore, verify, bmad-ux)

```bash
huggingface-cli download mlx-community/Qwen3-32B-4bit \
  --local-dir ~/models/qwen3-32b-mlx
```

Approximate size: **18 GB**

---

## 3. Verify the model structure

When finished, `~/models/` should have this structure:

```
~/models/
├── qwen2.5-coder-32b-mlx/        # Qwen 2.5-Coder 32B (MLX)
├── deepseek-r1-32b-mlx/          # DeepSeek R1 32B (MLX)
└── qwen3-32b-mlx/                # Qwen3 32B (MLX)
```

Verify with `agentic-up.sh`:
```bash
bash bin/agentic-up.sh --check
```

If any model is missing, the script will report the exact error with the expected path.

---

## 4. Manual model startup (without agentic-up.sh)

If you prefer to start the models manually:

```bash
source ~/projects/mlx-qwen/mlx_env/bin/activate

# Qwen Coder — port 8000
mlx_lm.server --model ~/models/qwen2.5-coder-32b-mlx --port 8000 --host 0.0.0.0 &

# DeepSeek R1 — port 8001
mlx_lm.server --model ~/models/deepseek-r1-32b-mlx --port 8001 --host 0.0.0.0 &

# Qwen3 32B — port 8006 (must listen on 0.0.0.0 to be accessible from Docker)
mlx_lm.server --model ~/models/qwen3-32b-mlx --port 8006 --host 0.0.0.0 &
```

---

## 5. Without local models (cloud API only)

If you don't have Apple Silicon or prefer to use only Anthropic, edit `litellm/litellm_config.yaml` and point all aliases to `claude-sonnet` or `claude-haiku`:

```yaml
models:
  - model_name: local-thinking
    litellm_params:
      model: claude-sonnet-4-5
      api_key: os.environ/ANTHROPIC_API_KEY

  - model_name: local-coder
    litellm_params:
      model: claude-haiku-4-5
      api_key: os.environ/ANTHROPIC_API_KEY

  - model_name: local-hermes
    litellm_params:
      model: claude-sonnet-4-5
      api_key: os.environ/ANTHROPIC_API_KEY
```

The rest of the stack (Hermes, Schema Service, Engram, Langfuse) works identically — only the model executing each phase changes.
