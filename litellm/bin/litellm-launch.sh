#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${HOME}/.config/litellm/env"
CONFIG="${HOME}/litellm_config.yaml"
PORT=8002
LITELLM_BIN="${LITELLM_BIN:-$(which litellm)}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "FATAL: ${ENV_FILE} not found — cannot start LiteLLM without API keys" >&2
  exit 78  # EX_CONFIG
fi

# Idempotency: if :8002 already responds, exit 0 (launchd won't restart on SuccessfulExit=false)
if curl -sf -m 2 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "LiteLLM already running on :${PORT}, exiting cleanly"
  exit 0
fi

# Export all vars from env file into the environment
set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

exec "${LITELLM_BIN}" --config "${CONFIG}" --port "${PORT}"
