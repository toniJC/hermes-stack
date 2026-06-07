#!/bin/bash
# engram-mcp-proxy-run.sh
# Reads the current workspace from ~/.hermes-current-workspace and starts
# mcp-proxy from that directory so that Engram's mem_current_project detects
# the correct project (engram mcp inherits this cwd via mcp-proxy).
#
# Managed by launchd (com.pirito.engram-mcp-proxy). Do not run directly.

WORKSPACE=$(cat "$HOME/.hermes-current-workspace" 2>/dev/null || echo "$HOME")

if [[ -d "$WORKSPACE" ]]; then
  cd "$WORKSPACE"
fi

exec "${MLX_VENV_BIN:-$HOME/projects/mlx-qwen/mlx_env/bin}/mcp-proxy" \
  --port 7438 \
  --host 0.0.0.0 \
  --allow-origin '*' \
  -- /opt/homebrew/bin/engram mcp --tools=agent
