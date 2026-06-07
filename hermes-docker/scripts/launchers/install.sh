#!/usr/bin/env bash
# install.sh — Compile, icon, de-quarantine, codesign, and Spotlight-index
# AgenticStart.app, AgenticStop.app, HermesAgent.app.
# Idempotent: safe to re-run after editing the .applescript sources.

set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST_DIR="${HOME}/Applications"
ICONS_DIR="${SRC_DIR}/icons"

mkdir -p "${DEST_DIR}"

apps=(
  "AgenticStart:AgenticStart.applescript"
  "AgenticStop:AgenticStop.applescript"
  "HermesAgent:HermesAgent.applescript"
)

for entry in "${apps[@]}"; do
  name="${entry%%:*}"
  src="${entry##*:}"
  target="${DEST_DIR}/${name}.app"
  source_path="${SRC_DIR}/${src}"

  if [[ ! -f "${source_path}" ]]; then
    echo "ERROR: missing source file ${source_path}" >&2
    exit 1
  fi

  echo "==> Building ${name}.app"

  if [[ -e "${target}" ]]; then
    rm -rf "${target}"
  fi

  osacompile -o "${target}" "${source_path}"
  xattr -cr "${target}"
  codesign --force --deep --sign - "${target}"

  # Install custom icon if PNG source and magick are available
  icon_src="${ICONS_DIR}/${name}.png"
  if [[ -f "${icon_src}" ]] && command -v magick &>/dev/null; then
    iconset="/tmp/${name}.iconset"
    rm -rf "${iconset}" && mkdir "${iconset}"
    for s in 16 32 64 128 256 512; do
      magick "${icon_src}" -resize ${s}x${s}     "${iconset}/icon_${s}x${s}.png"
      magick "${icon_src}" -resize $((s*2))x$((s*2)) "${iconset}/icon_${s}x${s}@2x.png"
    done
    iconutil -c icns "${iconset}" -o "/tmp/${name}.icns"
    cp "/tmp/${name}.icns" "${target}/Contents/Resources/droplet.icns"
    rm -rf "${iconset}"
    echo "    icon:  ${icon_src}"
  fi

  echo "    built: ${target}"
done

mdutil -i on "${DEST_DIR}" >/dev/null 2>&1 || true
for entry in "${apps[@]}"; do
  name="${entry%%:*}"
  touch "${DEST_DIR}/${name}.app"
  mdimport "${DEST_DIR}/${name}.app" >/dev/null 2>&1 || true
done

cat <<'EOF'

Done.

Try it now:
  Cmd+Space  ->  "AgenticStart"  ->  Return
  Cmd+Space  ->  "AgenticStop"   ->  Return
  Cmd+Space  ->  "HermesAgent"   ->  Return

If Spotlight does not see them within ~10 seconds, run:
  mdutil -E ~/Applications
EOF
