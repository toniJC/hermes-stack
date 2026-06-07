#!/usr/bin/env bash
set -euo pipefail

echo "=== hermes-stack install ==="

if [ ! -f .env ]; then
  cp .env.example .env
  echo "[ok] .env created from .env.example — fill in your values."
else
  echo "[skip] .env already exists."
fi

echo ""
echo "Next steps:"
echo "  1. Edit .env with your actual API keys"
echo "  2. Start Langfuse:         cd langfuse-docker && docker compose up -d"
echo "  3. Start LiteLLM:          cd litellm && bash bin/litellm-launch.sh"
echo "  4. Start Hermes:           cd hermes-docker && docker compose up -d"
echo "  5. (Optional) Start MCP:   cd hermes-design-mcp && bash run.sh"
