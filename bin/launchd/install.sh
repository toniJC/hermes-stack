#!/usr/bin/env bash
# bin/launchd/install.sh
# Generates launchd plists from templates and installs them into ~/Library/LaunchAgents/.
#
# Usage:
#   bash bin/launchd/install.sh          # install all plists
#   bash bin/launchd/install.sh --unload # unload all managed services
#
# What it does:
#   1. Replaces __HOME__ in each .plist.template with $HOME
#   2. Copies the generated plists to ~/Library/LaunchAgents/
#   3. Loads them with launchctl (or unloads if --unload)
#
# The bin/litellm-launch.sh and bin/engram-mcp-proxy-run.sh scripts must be
# installed at ~/bin/ before running this. Copy them from bin/:
#   mkdir -p ~/bin && cp bin/agentic-up.sh bin/devstral-proxy.py bin/engram-mcp-proxy-run.sh ~/bin/
#   cp litellm/bin/litellm-launch.sh ~/bin/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
TEMPLATES=("$SCRIPT_DIR"/*.plist.template)

green()  { printf "\033[32m%s\033[0m\n" "$*"; }
red()    { printf "\033[31m%s\033[0m\n" "$*"; }
cyan()   { printf "\033[36m%s\033[0m\n" "$*"; }

mkdir -p "$LAUNCH_AGENTS_DIR"
mkdir -p "$HOME/Library/Logs/agentic-stack"

if [[ "${1:-}" == "--unload" ]]; then
  cyan "=== Unloading hermes-stack launchd services ==="
  for template in "${TEMPLATES[@]}"; do
    label=$(basename "$template" .plist.template)
    plist="$LAUNCH_AGENTS_DIR/${label}.plist"
    if [[ -f "$plist" ]]; then
      launchctl unload "$plist" 2>/dev/null && green "[unloaded] $label" || true
    fi
  done
  exit 0
fi

cyan "=== Installing hermes-stack launchd services ==="
cyan "    HOME: $HOME"
echo ""

for template in "${TEMPLATES[@]}"; do
  label=$(basename "$template" .plist.template)
  dest="$LAUNCH_AGENTS_DIR/${label}.plist"

  # Generate plist from template
  sed "s|__HOME__|$HOME|g" "$template" > "$dest"

  # Unload first if already loaded (idempotent)
  launchctl unload "$dest" 2>/dev/null || true

  # Load
  if launchctl load "$dest" 2>/dev/null; then
    green "[ok] $label"
  else
    red "[failed] $label — check: launchctl list | grep hermes-stack"
  fi
done

echo ""
cyan "Done. Verify with: launchctl list | grep hermes-stack"
