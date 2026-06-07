#!/usr/bin/env bash
# agentic-up.sh — cold-start the local agentic stack
#
# Tiers:
#   T0 verify: LiteLLM :8002 (launchd-managed)
#   T1:        Engram :7437
#   T1b:       Engram MCP proxy :7438 (stdio→HTTP/SSE bridge for Docker agents)
#   T2 par:    MLX coder :8000 | MLX thinking :8001 | llama devstral :8004 | MLX hermes :8006 | MLX architect :8003
#   T3:        devstral-proxy :8005
#   T4:        Schema Service :8010
#
# Idempotent: healthy components are skipped. Stale processes (port bound, health failing)
# are reported with kill hint — never auto-killed.
#
# Requires:
#   - engram, mlx_lm.server, uvicorn on PATH
#   - /opt/homebrew/bin/llama-server (brew-managed symlink)
#     Re-link after `brew upgrade llama.cpp`:
#       ln -sf /opt/homebrew/Cellar/llama.cpp/$(ls /opt/homebrew/Cellar/llama.cpp | sort -V | tail -1)/bin/llama-server /Users/pirito/bin/llama-server
#
# Usage:
#   agentic-up.sh          # cold-start the stack
#   agentic-up.sh --check  # health-only report, no starts
#   agentic-up.sh --help

set -uo pipefail

# ───────────────────────────── config ─────────────────────────────
# mlx_lm.server and uvicorn live in the shared MLX venv — prepend to PATH
export PATH="${MLX_VENV_BIN:-$HOME/projects/mlx-qwen/mlx_env/bin}:${PATH}"

LOG_DIR="${HOME}/Library/Logs/agentic-stack"
MODELS_DIR="${MODELS_DIR:-$HOME/models}"
LLAMA_BIN="/opt/homebrew/bin/llama-server"
DEVSTRAL_PROXY="${DEVSTRAL_PROXY:-$HOME/bin/devstral-proxy.py}"
SCHEMA_SERVICE_DIR="${SCHEMA_SERVICE_DIR:-$HOME/projects/schema-service}"

DEVSTRAL_GGUF="${MODELS_DIR}/devstral-small-2505-gguf/Devstral-Small-2505-Q4_K_M.gguf"
MLX_CODER="${MODELS_DIR}/qwen2.5-coder-32b-mlx"
MLX_THINKING="${MODELS_DIR}/deepseek-r1-32b-mlx"
MLX_HERMES="${MODELS_DIR}/hermes3-70b-mlx"
MLX_ARCHITECT="${MODELS_DIR}/llama3.3-70b-mlx"

LANGFUSE_DOCKER_DIR="${LANGFUSE_DOCKER_DIR:-$HOME/projects/langfuse-docker}"
LANGFUSE_TIMEOUT=60

T1_TIMEOUT=30
T1B_TIMEOUT=15
T2_TIMEOUT=120
T3_TIMEOUT=15
T4_TIMEOUT=30

START_TS=$(date +%s)

# ───────────────────────────── helpers ────────────────────────────
red()    { printf "\033[31m%s\033[0m" "$*"; }
green()  { printf "\033[32m%s\033[0m" "$*"; }
yellow() { printf "\033[33m%s\033[0m" "$*"; }
cyan()   { printf "\033[36m%s\033[0m" "$*"; }

status_ok()    { printf "  %s %-18s :%-5s\n"             "$(green '[OK]      ')" "$1" "$2"; }
status_start() { printf "  %s %-18s :%-5s\n"             "$(cyan  '[STARTING]')" "$1" "$2"; }
status_skip()  { printf "  %s %-18s :%-5s (already running)\n" "$(green '[SKIP]    ')" "$1" "$2"; }
status_warn()  { printf "  %s %-18s :%-5s — %s\n"        "$(yellow '[WARN]    ')" "$1" "$2" "$3"; }
status_fail()  { printf "  %s %-18s :%-5s — %s\n"        "$(red    '[FAILED]  ')" "$1" "$2" "$3"; }
status_stale() { printf "  %s %-18s :%-5s — stale (kill: lsof -ti :%s | xargs kill -9)\n" "$(red '[STALE]   ')" "$1" "$2" "$2"; }

die() { echo "FATAL: $*" >&2; exit 1; }

port_in_use() {
  lsof -ti ":$1" -sTCP:LISTEN >/dev/null 2>&1
}

wait_for_health() {
  local url="$1" timeout="$2" elapsed=0
  while (( elapsed < timeout )); do
    if curl -sf -m 2 -o /dev/null "$url"; then
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  return 1
}

# Like wait_for_health but for SSE endpoints (streaming — curl -sf always fails).
# Checks that the response starts with "event:" within the timeout.
wait_for_sse() {
  local url="$1" timeout="$2" elapsed=0
  sleep 1  # give the process time to bind before first check
  while (( elapsed < timeout )); do
    local status
    status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "$url" 2>/dev/null || true)
    if [[ "$status" == "200" ]]; then
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 3))
  done
  return 1
}

tail_log() {
  local log="$1"
  echo "    ── last 20 lines of ${log} ──" >&2
  tail -n 20 "$log" >&2 2>/dev/null || echo "    (no log)" >&2
}

# start_if_dead NAME PORT HEALTH_URL LOG_FILE -- CMD...
#   Returns: 0 started (or skipped healthy), 2 stale, 3 launch error
start_if_dead() {
  local name="$1" port="$2" health="$3" log="$4"
  shift 4
  [[ "$1" == "--" ]] && shift

  if port_in_use "$port"; then
    if curl -sf -m 2 -o /dev/null "$health"; then
      status_skip "$name" "$port"
      return 0
    else
      status_stale "$name" "$port"
      return 2
    fi
  fi

  status_start "$name" "$port"
  echo "===== $(date) — starting $name =====" >> "$log"
  nohup "$@" >> "$log" 2>&1 &
  disown
  return 0
}

# ───────────────────────────── preflight ──────────────────────────
preflight() {
  mkdir -p "$LOG_DIR"

  command -v engram        >/dev/null || die "engram not on PATH"
  command -v mlx_lm.server >/dev/null || die "mlx_lm.server not on PATH"
  command -v uvicorn       >/dev/null || die "uvicorn not on PATH"
  command -v curl          >/dev/null || die "curl not on PATH"
  command -v lsof          >/dev/null || die "lsof not on PATH"

  [[ -x "$LLAMA_BIN" ]]    || die "llama-server not found at $LLAMA_BIN"
  [[ -f "$DEVSTRAL_GGUF" ]] || die "devstral GGUF missing: $DEVSTRAL_GGUF"
  [[ -f "$DEVSTRAL_PROXY" ]] || die "devstral-proxy.py missing: $DEVSTRAL_PROXY"
  [[ -d "$MLX_CODER"    ]]  || die "MLX coder model missing: $MLX_CODER"
  [[ -d "$MLX_THINKING" ]]  || die "MLX thinking model missing: $MLX_THINKING"
  [[ -d "$MLX_HERMES"   ]]  || die "MLX hermes model missing: $MLX_HERMES"
  [[ -d "$MLX_ARCHITECT" ]] || die "MLX architect model missing: $MLX_ARCHITECT"
  [[ -d "$SCHEMA_SERVICE_DIR" ]] || die "Schema Service repo missing: $SCHEMA_SERVICE_DIR"
}

# ───────────────────────────── tier 0-pre: langfuse ───────────────
t0_langfuse() {
  echo
  echo "── Tier 0-pre: Langfuse (observability — non-blocking) ──"

  if ! docker info >/dev/null 2>&1; then
    status_start "docker" ""
    open -a Docker
    local i=0
    while ! docker info >/dev/null 2>&1; do
      sleep 2; i=$(( i + 2 ))
      if (( i >= 60 )); then
        status_warn "langfuse" 3000 "Docker did not start in 60s — observability disabled"
        return 0
      fi
    done
    status_ok "docker" ""
  fi

  if curl -sf -m 2 -o /dev/null "http://127.0.0.1:3000/api/public/health"; then
    status_skip "langfuse" 3000
    return 0
  fi

  status_start "langfuse" 3000
  (
    cd "$LANGFUSE_DOCKER_DIR" 2>/dev/null || {
      status_warn "langfuse" 3000 "compose dir missing — skipping"
      exit 0
    }
    docker compose up -d >> "$LOG_DIR/langfuse.log" 2>&1
  )

  if wait_for_health "http://127.0.0.1:3000/api/public/health" "$LANGFUSE_TIMEOUT"; then
    status_ok "langfuse" 3000
  else
    status_warn "langfuse" 3000 "did not become healthy in ${LANGFUSE_TIMEOUT}s — continuing without traces"
    tail_log "$LOG_DIR/langfuse.log"
  fi
}

verify_litellm() {
  local elapsed=0
  while (( elapsed < 15 )); do
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" -m 2 \
      -H "Authorization: Bearer ${LITELLM_MASTER_KEY:-hermes-local-dev}" \
      "http://127.0.0.1:8002/health" 2>/dev/null)
    if [[ "$code" == "200" ]]; then
      status_ok "litellm" "8002"
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  status_fail "litellm" "8002" "not responding — try: launchctl start com.pirito.litellm"
  return 1
}

# ───────────────────────────── --check mode ───────────────────────
check_all() {
  echo "Health check (no starts):"
  local rc=0
  local checks=(
    "langfuse         3000 http://127.0.0.1:3000/api/public/health"
    "litellm          8002 http://127.0.0.1:8002/v1/models"
    "engram           7437 http://127.0.0.1:7437/health"
    "engram-mcp-proxy 7438 http://127.0.0.1:7438/sse"
    "mlx-coder        8000 http://127.0.0.1:8000/v1/models"
    "mlx-thinking     8001 http://127.0.0.1:8001/v1/models"
    "mlx-architect    8003 http://127.0.0.1:8003/v1/models"
    "llama-devstral   8004 http://127.0.0.1:8004/health"
    "devstral-proxy   8005 http://127.0.0.1:8005/v1/models"
    "mlx-hermes       8006 http://127.0.0.1:8006/v1/models"
    "schema-service   8010 http://127.0.0.1:8010/healthz"
  )
  for line in "${checks[@]}"; do
    read -r name port url <<< "$line"
    local healthy=0
    if [[ "$url" == *"/sse" ]]; then
      [[ "$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "$url" 2>/dev/null)" == "200" ]] && healthy=1
    elif [[ "$name" == "litellm" ]]; then
      [[ "$(curl -s -o /dev/null -w "%{http_code}" -m 2 -H "Authorization: Bearer ${LITELLM_MASTER_KEY:-hermes-local-dev}" "$url" 2>/dev/null)" == "200" ]] && healthy=1
    else
      curl -sf -m 2 -o /dev/null "$url" && healthy=1
    fi
    if [[ "$healthy" -eq 1 ]]; then
      status_ok "$name" "$port"
    else
      status_fail "$name" "$port" "down"
      [[ "$name" == "schema-service" ]] && rc=1
    fi
  done
  return $rc
}

# ───────────────────────────── tier 1: engram ─────────────────────
t1_engram() {
  echo
  echo "── Tier 1: Engram ──"
  start_if_dead "engram" 7437 "http://127.0.0.1:7437/health" \
    "$LOG_DIR/engram.log" -- engram serve
  local rc=$?
  [[ $rc -eq 2 ]] && die "engram :7437 stale; manual intervention required"
  if port_in_use 7437 && curl -sf -m 2 -o /dev/null "http://127.0.0.1:7437/health"; then
    return 0
  fi
  if wait_for_health "http://127.0.0.1:7437/health" "$T1_TIMEOUT"; then
    status_ok "engram" 7437
  else
    status_fail "engram" 7437 "no health within ${T1_TIMEOUT}s"
    tail_log "$LOG_DIR/engram.log"
    die "tier 1 failed"
  fi
}

# ───────────────────────────── tier 1b: engram mcp proxy ─────────
LAUNCHD_LABEL="com.pirito.engram-mcp-proxy"
LAUNCHD_PLIST="$HOME/Library/LaunchAgents/${LAUNCHD_LABEL}.plist"
LAUNCHD_TARGET="gui/$(id -u)/${LAUNCHD_LABEL}"

t1b_engram_mcp_proxy() {
  echo
  echo "── Tier 1b: engram-mcp-proxy ──"

  # Already healthy — nothing to do
  if [[ "$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "http://127.0.0.1:7438/sse" 2>/dev/null)" == "200" ]]; then
    status_skip "engram-mcp-proxy" 7438
    return 0
  fi

  status_start "engram-mcp-proxy" 7438

  # Bootstrap the launchd service if not yet loaded
  if ! launchctl list "$LAUNCHD_LABEL" &>/dev/null; then
    launchctl bootstrap "gui/$(id -u)" "$LAUNCHD_PLIST" 2>/dev/null || true
  fi

  # Kick the service (start or restart)
  launchctl kickstart -k "$LAUNCHD_TARGET" &>/dev/null || true

  if wait_for_sse "http://127.0.0.1:7438/sse" "$T1B_TIMEOUT"; then
    status_ok "engram-mcp-proxy" 7438
  else
    status_fail "engram-mcp-proxy" 7438 "no SSE response within ${T1B_TIMEOUT}s"
    tail_log "$LOG_DIR/engram-mcp-proxy.log"
    die "tier 1b failed"
  fi
}

# ───────────────────────────── tier 2: parallel models ────────────
# bash 3.2 compatible (no associative arrays) — status tracked via temp files.
_T2_TMPDIR=""

_t2_set_status() { echo "$2" > "${_T2_TMPDIR}/$1"; }
_t2_get_status() { cat "${_T2_TMPDIR}/$1" 2>/dev/null || echo "unknown"; }

t2_launch_one() {
  local name="$1" port="$2" health="$3" log="$4"; shift 4
  start_if_dead "$name" "$port" "$health" "$log" -- "$@"
  local rc=$?
  if [[ $rc -eq 2 ]]; then
    _t2_set_status "$name" "stale"
    return
  fi
  _t2_set_status "$name" "pending|${health}|${log}|${port}"
}

t2_wait_all() {
  local names=(mlx-coder mlx-thinking llama-devstral mlx-hermes mlx-architect)
  local pids=()
  for name in "${names[@]}"; do
    local v; v=$(_t2_get_status "$name")
    [[ "$v" != pending\|* ]] && continue
    IFS='|' read -r _ url log port <<< "$v"
    (
      wait_for_health "$url" "$T2_TIMEOUT" && echo ok || echo fail
    ) > "${_T2_TMPDIR}/${name}.result" &
    pids+=($!)
  done
  for p in "${pids[@]}"; do wait "$p"; done

  # Evaluate results serially (subshells can't write to parent vars)
  for name in "${names[@]}"; do
    local v; v=$(_t2_get_status "$name")
    [[ "$v" != pending\|* ]] && continue
    IFS='|' read -r _ url log port <<< "$v"
    local result; result=$(cat "${_T2_TMPDIR}/${name}.result" 2>/dev/null || echo fail)
    if [[ "$result" == "ok" ]]; then
      status_ok "$name" "$port"
      _t2_set_status "$name" "ok"
    else
      status_fail "$name" "$port" "no health within ${T2_TIMEOUT}s"
      tail_log "$log"
      _t2_set_status "$name" "fail"
    fi
  done
}

t2_parallel_models() {
  echo
  echo "── Tier 2: models (parallel, ${T2_TIMEOUT}s timeout each) ──"
  _T2_TMPDIR=$(mktemp -d)
  trap 'rm -rf "$_T2_TMPDIR"' EXIT

  t2_launch_one "mlx-coder"      8000 "http://127.0.0.1:8000/v1/models" "$LOG_DIR/mlx-coder.log" \
    mlx_lm.server --model "$MLX_CODER" --port 8000 --host 0.0.0.0
  t2_launch_one "mlx-thinking"   8001 "http://127.0.0.1:8001/v1/models" "$LOG_DIR/mlx-thinking.log" \
    mlx_lm.server --model "$MLX_THINKING" --port 8001 --host 0.0.0.0
  t2_launch_one "llama-devstral" 8004 "http://127.0.0.1:8004/health"    "$LOG_DIR/llama-devstral.log" \
    "$LLAMA_BIN" -m "$DEVSTRAL_GGUF" --port 8004 --host 0.0.0.0 -ngl 99
  t2_launch_one "mlx-hermes"     8006 "http://127.0.0.1:8006/v1/models" "$LOG_DIR/mlx-hermes.log" \
    mlx_lm.server --model "$MLX_HERMES" --port 8006 --host 0.0.0.0
  t2_launch_one "mlx-architect"  8003 "http://127.0.0.1:8003/v1/models" "$LOG_DIR/mlx-architect.log" \
    mlx_lm.server --model "$MLX_ARCHITECT" --port 8003 --host 0.0.0.0

  for name in mlx-coder mlx-thinking llama-devstral mlx-hermes mlx-architect; do
    [[ "$(_t2_get_status "$name")" == "stale" ]] && die "stale process on $name; resolve manually"
  done

  t2_wait_all

  local critical_fail=0
  for n in mlx-coder mlx-thinking llama-devstral; do
    [[ "$(_t2_get_status "$n")" == "fail" ]] && critical_fail=1
  done
  if [[ "$(_t2_get_status "mlx-hermes")" == "fail" ]]; then
    status_warn "mlx-hermes" 8006 "Schema Service will work; HermesAgent will not"
  fi
  if [[ "$(_t2_get_status "mlx-architect")" == "fail" ]]; then
    status_warn "mlx-architect" 8003 "local-architect alias unavailable"
  fi
  [[ $critical_fail -eq 1 ]] && die "tier 2 critical model(s) failed — aborting"
}

# ───────────────────────────── tier 3: devstral-proxy ─────────────
t3_devstral_proxy() {
  echo
  echo "── Tier 3: devstral-proxy ──"
  start_if_dead "devstral-proxy" 8005 "http://127.0.0.1:8005/v1/models" \
    "$LOG_DIR/devstral-proxy.log" -- python3 "$DEVSTRAL_PROXY"
  local rc=$?
  [[ $rc -eq 2 ]] && die "devstral-proxy :8005 stale"
  if wait_for_health "http://127.0.0.1:8005/v1/models" "$T3_TIMEOUT"; then
    status_ok "devstral-proxy" 8005
  else
    status_fail "devstral-proxy" 8005 "no health within ${T3_TIMEOUT}s"
    tail_log "$LOG_DIR/devstral-proxy.log"
    die "tier 3 failed"
  fi
}

# ───────────────────────────── tier 4: schema service ─────────────
t4_schema_service() {
  echo
  echo "── Tier 4: schema-service ──"
  (
    cd "$SCHEMA_SERVICE_DIR" || die "cannot cd $SCHEMA_SERVICE_DIR"
    LITELLM_API_KEY="${LITELLM_MASTER_KEY:-hermes-local-dev}" \
    start_if_dead "schema-service" 8010 "http://127.0.0.1:8010/healthz" \
      "$LOG_DIR/schema-service.log" -- uvicorn app.main:app --host 0.0.0.0 --port 8010
  )
  local rc=$?
  [[ $rc -eq 2 ]] && die "schema-service :8010 stale"
  if wait_for_health "http://127.0.0.1:8010/healthz" "$T4_TIMEOUT"; then
    status_ok "schema-service" 8010
  else
    status_fail "schema-service" 8010 "no health within ${T4_TIMEOUT}s"
    tail_log "$LOG_DIR/schema-service.log"
    die "tier 4 failed"
  fi
}

# ───────────────────────────── summary ────────────────────────────
print_summary() {
  local elapsed=$(( $(date +%s) - START_TS ))
  echo
  echo "── Final status ──"
  local checks=(
    "langfuse         3000 http://127.0.0.1:3000/api/public/health"
    "litellm          8002 http://127.0.0.1:8002/v1/models"
    "engram           7437 http://127.0.0.1:7437/health"
    "engram-mcp-proxy 7438 http://127.0.0.1:7438/sse"
    "mlx-coder        8000 http://127.0.0.1:8000/v1/models"
    "mlx-thinking     8001 http://127.0.0.1:8001/v1/models"
    "mlx-architect    8003 http://127.0.0.1:8003/v1/models"
    "llama-devstral   8004 http://127.0.0.1:8004/health"
    "devstral-proxy   8005 http://127.0.0.1:8005/v1/models"
    "mlx-hermes       8006 http://127.0.0.1:8006/v1/models"
    "schema-service   8010 http://127.0.0.1:8010/healthz"
  )
  for line in "${checks[@]}"; do
    read -r name port url <<< "$line"
    local http_code
    if [[ "$name" == "litellm" ]]; then
      http_code=$(curl -s -o /dev/null -w "%{http_code}" -m 2 \
        -H "Authorization: Bearer ${LITELLM_MASTER_KEY:-hermes-local-dev}" \
        "$url" 2>/dev/null || true)
    elif [[ "$url" == *"/sse" ]]; then
      http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "$url" 2>/dev/null || true)
    else
      http_code=$(curl -s -o /dev/null -w "%{http_code}" -m 2 "$url" 2>/dev/null || true)
    fi
    if [[ "$http_code" == "200" ]]; then
      status_ok "$name" "$port"
    else
      status_fail "$name" "$port" "down"
    fi
  done
  echo
  echo "Stack ready in ${elapsed}s — logs: $LOG_DIR"
  echo "Next: docker compose run --rm hermes hermes chat  (from hermes-docker/)"
}

# ───────────────────────────── main ───────────────────────────────
usage() {
  cat <<EOF
Usage: agentic-up.sh [--check|--help]

  (no args)   Cold-start the agentic stack with idempotent re-runs
  --check     Probe all health endpoints, no starts. Exit 0 if Schema Service healthy.
  --help      This message
EOF
}

main() {
  case "${1:-}" in
    --help|-h) usage; exit 0 ;;
    --check)   preflight; check_all; exit $? ;;
    "")        ;;
    *)         usage; exit 2 ;;
  esac

  preflight
  t0_langfuse                              # non-blocking observability
  echo "── Tier 0: LiteLLM (verify only) ──"
  verify_litellm || die "LiteLLM is required by Schema Service"

  t1_engram
  t1b_engram_mcp_proxy
  t2_parallel_models
  t3_devstral_proxy
  t4_schema_service
  print_summary
}

main "$@"
