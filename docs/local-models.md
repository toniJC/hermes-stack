# Guía de modelos locales

Esta guía cubre cómo configurar el entorno MLX y descargar los modelos locales para ejecutar el stack sin depender de APIs en la nube.

> **Requisito de hardware**: Apple Silicon (M1 Pro o superior). Los modelos de 32B requieren al menos 32 GB de RAM unificada; el de 70B requiere 64 GB o más.

---

## 1. Crear el entorno virtual MLX

El stack asume un virtualenv en `~/projects/mlx-qwen/mlx_env/`. Este entorno contiene `mlx_lm`, `mcp-proxy` y el resto de dependencias locales.

```bash
mkdir -p ~/projects/mlx-qwen
python3.11 -m venv ~/projects/mlx-qwen/mlx_env
source ~/projects/mlx-qwen/mlx_env/bin/activate
```

Instalar dependencias:

```bash
pip install --upgrade pip

# MLX runtime y servidor de modelos
pip install mlx mlx-lm

# MCP proxy (puente stdio→HTTP para Docker)
pip install mcp-proxy

# Dependencias de Schema Service (opcional aquí si prefieres instalar en su propio venv)
pip install fastapi uvicorn instructor openai httpx pydantic

# MCP SDK
pip install mcp
```

Verificar:

```bash
mlx_lm.server --help   # debe mostrar opciones
mcp-proxy --version    # debe mostrar versión
```

---

## 2. Instalar llama.cpp (para Devstral GGUF)

Devstral corre via `llama-server` (llama.cpp), no MLX. Instalar via Homebrew:

```bash
brew install llama.cpp
```

Verificar:
```bash
llama-server --version
```

---

## 3. Descargar los modelos

Crea el directorio de modelos:

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

O descarga directa desde HuggingFace:
```bash
huggingface-cli download mlx-community/Qwen2.5-Coder-32B-Instruct-4bit \
  --local-dir ~/models/qwen2.5-coder-32b-mlx
```

Tamaño aproximado: **18 GB**

---

### DeepSeek R1 Distill 32B (alias: `local-thinking` — propose, design)

```bash
huggingface-cli download mlx-community/DeepSeek-R1-Distill-Qwen-32B-4bit \
  --local-dir ~/models/deepseek-r1-32b-mlx
```

Tamaño aproximado: **18 GB**

---

### Hermes 3 70B (alias: `local-hermes` — explore, verify, bmad-ux)

```bash
huggingface-cli download mlx-community/Hermes-3-Llama-3.1-70B-4bit \
  --local-dir ~/models/hermes3-70b-mlx
```

Tamaño aproximado: **40 GB**

---

### Llama 3.3 70B (alias: `local-architect` — disponible, sin fase asignada aún)

```bash
huggingface-cli download mlx-community/Llama-3.3-70B-Instruct-4bit \
  --local-dir ~/models/llama3.3-70b-mlx
```

Tamaño aproximado: **40 GB**

---

### Devstral Small 24B GGUF (alias: `local-devstral` — fallback, tool calling)

```bash
mkdir -p ~/models/devstral-small-2505-gguf
huggingface-cli download mistralai/Devstral-Small-2505-GGUF \
  --include "Devstral-Small-2505-Q4_K_M.gguf" \
  --local-dir ~/models/devstral-small-2505-gguf
```

Tamaño aproximado: **15 GB**

---

## 4. Verificar la estructura de modelos

Al terminar, `~/models/` debe tener esta estructura:

```
~/models/
├── qwen2.5-coder-32b-mlx/        # Qwen 2.5-Coder 32B (MLX)
├── deepseek-r1-32b-mlx/          # DeepSeek R1 32B (MLX)
├── hermes3-70b-mlx/              # Hermes 3 70B (MLX)
├── llama3.3-70b-mlx/             # Llama 3.3 70B (MLX)
└── devstral-small-2505-gguf/
    └── Devstral-Small-2505-Q4_K_M.gguf
```

Verifica con `agentic-up.sh`:
```bash
bash bin/agentic-up.sh --check
```

Si algún modelo falta, el script reportará el error exacto con la ruta esperada.

---

## 5. Arranque manual de modelos (sin agentic-up.sh)

Si prefieres arrancar los modelos manualmente:

```bash
source ~/projects/mlx-qwen/mlx_env/bin/activate

# Qwen Coder — puerto 8000
mlx_lm.server --model ~/models/qwen2.5-coder-32b-mlx --port 8000 --host 0.0.0.0 &

# DeepSeek R1 — puerto 8001
mlx_lm.server --model ~/models/deepseek-r1-32b-mlx --port 8001 --host 0.0.0.0 &

# Hermes 3 70B — puerto 8006 (debe escuchar en 0.0.0.0 para ser accesible desde Docker)
mlx_lm.server --model ~/models/hermes3-70b-mlx --port 8006 --host 0.0.0.0 &

# Llama 3.3 70B — puerto 8003
mlx_lm.server --model ~/models/llama3.3-70b-mlx --port 8003 --host 0.0.0.0 &

# Devstral GGUF — puerto 8004
llama-server \
  --model ~/models/devstral-small-2505-gguf/Devstral-Small-2505-Q4_K_M.gguf \
  --port 8004 --host 0.0.0.0 \
  --n-gpu-layers 999 &

# Devstral proxy (convierte tool calls al formato OpenAI) — puerto 8005
python ~/bin/devstral-proxy.py &
```

---

## 6. Sin modelos locales (solo API en la nube)

Si no tienes Apple Silicon o prefieres usar solo Anthropic, edita `litellm/litellm_config.yaml` y apunta todos los alias a `claude-sonnet` o `claude-haiku`:

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

El resto del stack (Hermes, Schema Service, Engram, Langfuse) funciona de forma idéntica — solo cambia el modelo que ejecuta cada fase.
