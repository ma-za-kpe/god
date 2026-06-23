#!/usr/bin/env bash
# Restart and verify the full GOD stack on a Vast.ai instance.
# Run this on the instance:
#   bash /workspace/god/scripts/vast-restart-services.sh
#
# This is the single startup entrypoint for the native stack. It brings up:
# PostgreSQL, Redis, NATS, IPFS, Ollama, ComfyUI, fish-speech, the runtime,
# the observer on port 3000, and nginx.

set -euo pipefail

REPO_DIR="/workspace/god"
LOG_DIR="/var/log/god"
mkdir -p "$LOG_DIR"

log() { echo "[vast-start] $*"; }
die() { log "ERROR: $*"; exit 1; }

check_port() {
  local port=$1 name=$2
  if ss -tlnp 2>/dev/null | grep -q ":${port} "; then
    log "Port ${port} (${name}) already bound; releasing it"
    fuser -k "${port}/tcp" 2>/dev/null || true
    sleep 2
  fi
}

cleanup_stale_ports() {
  local port name
  while read -r port name; do
    [ -z "${port:-}" ] && continue
    check_port "$port" "$name"
  done <<'EOF'
5432 PostgreSQL
6379 Redis
4222 NATS
11434 Ollama
8188 ComfyUI
7860 fish-speech
3000 Observer
8888 Runtime
10515 nginx-proxy
10516 nginx-proxy
10517 nginx-proxy
EOF
}

wait_http() {
  local url=$1 name=$2 timeout=${3:-90} delay=${4:-3}
  local elapsed=0
  while [ "$elapsed" -lt "$timeout" ]; do
    if curl -sf "$url" >/dev/null 2>&1; then
      log "${name} OK"
      return 0
    fi
    sleep "$delay"
    elapsed=$((elapsed + delay))
  done
  return 1
}

wait_http_post() {
  local url=$1 name=$2 timeout=${3:-90} delay=${4:-3}
  local elapsed=0
  while [ "$elapsed" -lt "$timeout" ]; do
    if curl -sf -X POST "$url" >/dev/null 2>&1; then
      log "${name} OK"
      return 0
    fi
    sleep "$delay"
    elapsed=$((elapsed + delay))
  done
  return 1
}

ensure_repo() {
  if [ -f "$REPO_DIR/.env.local" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$REPO_DIR/.env.local"
    set +a
  else
    die "$REPO_DIR/.env.local not found; run vast-setup-native.sh first"
  fi

  REPO_BRANCH="${REPO_BRANCH:-feat/twitch-ne-mo-showrunner}"
  log "Syncing repo on branch ${REPO_BRANCH}..."
  GIT_TERMINAL_PROMPT=0 git -C "$REPO_DIR" fetch origin || true
  git -C "$REPO_DIR" checkout "$REPO_BRANCH" 2>/dev/null || die "Branch ${REPO_BRANCH} not found"
  GIT_TERMINAL_PROMPT=0 git -C "$REPO_DIR" pull || die "git pull failed"
}

configure_streaming_mode() {
  local streaming_mode="${STREAMING_MODE:-auto}"

  # If the operator has already enabled streaming, preserve it.
  # Otherwise, auto-enable only when the required credentials are present.
  if [ "${streaming_mode}" = "true" ] || [ "${streaming_mode}" = "1" ]; then
    export YOUTUBE_ENABLED=true
    export YOUTUBE_DRY_RUN=false
    export BROADCAST_ENABLED=true
    export BROADCAST_DRY_RUN=false
    log "STREAMING_MODE forced on: runtime will connect YouTube + OBS live"
    return 0
  fi

  if [ -n "${YOUTUBE_CHANNEL_ID:-}" ] && [ -n "${YOUTUBE_ACCESS_TOKEN:-}" ] && [ -n "${YOUTUBE_CLIENT_ID:-}" ] && [ -n "${YOUTUBE_CLIENT_SECRET:-}" ]; then
    export YOUTUBE_ENABLED=true
    export YOUTUBE_DRY_RUN=false
    log "YouTube credentials detected: enabling live chat poller"
  fi

  if [ -n "${OBS_WEBSOCKET_URL:-}" ]; then
    export BROADCAST_ENABLED=true
    export BROADCAST_DRY_RUN=false
    log "OBS websocket detected: enabling live broadcast control"
  fi

  if [ -z "${OBS_BROWSER_SOURCE:-}" ]; then
    export OBS_BROWSER_SOURCE=god-browser
  fi
  if [ -z "${OBS_BROWSER_URL:-}" ]; then
    export OBS_BROWSER_URL=http://localhost:10517/one
  fi
  if [ -z "${OBS_STREAM_SERVER:-}" ]; then
    export OBS_STREAM_SERVER=rtmp://a.rtmp.youtube.com/live2
  fi
}

start_postgres() {
  log "Starting PostgreSQL..."
  service postgresql start 2>/dev/null || pg_ctlcluster 14 main start 2>/dev/null || die "Cannot start PostgreSQL"
  for _ in $(seq 1 15); do
    pg_isready -U god -h localhost >/dev/null 2>&1 && return 0
    sleep 2
  done
  die "PostgreSQL not ready after 30s"
}

start_redis() {
  log "Starting Redis..."
  check_port 6379 "Redis"
  service redis-server start 2>/dev/null || redis-server --daemonize yes || die "Cannot start Redis"
  wait_http "http://localhost:6379" "Redis" 2 1 || true
  redis-cli ping >/dev/null 2>&1 || die "Redis not responding"
  log "Redis OK"
}

start_nats() {
  log "Starting NATS..."
  if ! pgrep -x nats-server >/dev/null 2>&1; then
    check_port 4222 "NATS"
    nohup nats-server -p 4222 --jetstream >"$LOG_DIR/nats.log" 2>&1 &
  fi
  for _ in $(seq 1 20); do
    if ss -tlnp 2>/dev/null | grep -q ":4222 "; then
      log "NATS OK"
      return 0
    fi
    sleep 2
  done
  die "NATS not listening on :4222"
}

start_ipfs() {
  if ! command -v ipfs >/dev/null 2>&1; then
    die "ipfs binary missing; install IPFS before running the stack"
  fi

  log "Starting IPFS..."
  if curl -sf -X POST http://localhost:5001/api/v0/version >/dev/null 2>&1; then
    log "IPFS OK"
    return 0
  fi
  if ! pgrep -x ipfs >/dev/null 2>&1; then
    check_port 5001 "IPFS API"
    check_port 8080 "IPFS Gateway"
    nohup ipfs daemon --enable-gc >"$LOG_DIR/ipfs.log" 2>&1 &
  fi
  wait_http_post "http://localhost:5001/api/v0/version" "IPFS" 180 3 || die "IPFS not responding"
}

start_ollama() {
  log "Starting Ollama..."
  if ! pgrep -x ollama >/dev/null 2>&1; then
    check_port 11434 "Ollama"
    OLLAMA_KEEP_ALIVE=0 nohup ollama serve >"$LOG_DIR/ollama.log" 2>&1 &
  fi
  wait_http "http://localhost:11434/api/tags" "Ollama" 90 3 || die "Ollama not responding"
}

start_comfyui() {
  if [ ! -d /opt/ComfyUI ]; then
    die "/opt/ComfyUI missing; install ComfyUI before running the stack"
  fi

  log "Starting ComfyUI..."
  if ! pgrep -f "ComfyUI/main.py" >/dev/null 2>&1; then
    check_port 8188 "ComfyUI"
    cd /opt/ComfyUI
    source /opt/god-venv/bin/activate
    nohup python3 main.py --listen 0.0.0.0 --port 8188 --disable-auto-launch >"$LOG_DIR/comfyui.log" 2>&1 &
    cd "$REPO_DIR"
  fi
  wait_http "http://localhost:8188/" "ComfyUI" 120 5 || die "ComfyUI not responding"
}

start_fish() {
  if [ ! -d /opt/fish-speech ]; then
    die "/opt/fish-speech missing; install fish-speech before running the stack"
  fi

  log "Starting fish-speech..."
  if pgrep -f "tools/api_server.py" >/dev/null 2>&1; then
    log "Killing existing fish-speech processes"
    pkill -9 -f "tools/api_server.py" 2>/dev/null || true
    sleep 3
  fi
  check_port 7860 "fish-speech"
  UV=""
  for uv_dir in /opt/god-venv/bin /root/.local/bin; do
    if [ -d "$uv_dir" ]; then
      UV=$(find "$uv_dir" -name uv -type f 2>/dev/null | head -1 || true)
      if [ -n "$UV" ]; then
        break
      fi
    fi
  done
  UV="${UV:-$(command -v uv)}"
  cd /opt/fish-speech
  if [ -n "${UV:-}" ]; then
    nohup "$UV" run python tools/api_server.py \
      --llama-checkpoint-path /opt/fish-speech/checkpoints/s2-pro \
      --decoder-checkpoint-path /opt/fish-speech/checkpoints/s2-pro/codec.pth \
      --decoder-config-name modded_dac_vq \
      --device cuda \
      --listen 0.0.0.0:7860 \
      >"$LOG_DIR/fish-speech.log" 2>&1 &
  else
    source /opt/god-venv/bin/activate
    nohup python3 tools/api_server.py \
      --llama-checkpoint-path /opt/fish-speech/checkpoints/s2-pro \
      --decoder-checkpoint-path /opt/fish-speech/checkpoints/s2-pro/codec.pth \
      --decoder-config-name modded_dac_vq \
      --device cuda \
      --listen 0.0.0.0:7860 \
      >"$LOG_DIR/fish-speech.log" 2>&1 &
  fi
  cd "$REPO_DIR"
  wait_http "http://localhost:7860/" "fish-speech" 150 5 || die "fish-speech not responding"
}

start_observer() {
  if [ ! -d "$REPO_DIR/observer" ]; then
    die "$REPO_DIR/observer missing"
  fi

  log "Starting observer on :3000..."
  if pgrep -f 'observer/serve.py' >/dev/null 2>&1; then
    log "Killing existing observer serve.py process"
    pkill -9 -f 'observer/serve.py' 2>/dev/null || true
    sleep 2
  fi
  if pgrep -f 'vite' >/dev/null 2>&1; then
    log "Killing existing Vite process"
    pkill -9 -f 'vite' 2>/dev/null || true
    sleep 2
  fi
  check_port 3000 "observer"
  cd "$REPO_DIR/observer"
  if [ ! -d node_modules ]; then
    if [ -f package-lock.json ]; then
      npm ci
    else
      npm install
    fi
  fi
  nohup npm run dev -- --host 0.0.0.0 --port 3000 >"$LOG_DIR/observer.log" 2>&1 &
  cd "$REPO_DIR"
  wait_http "http://localhost:3000/one" "observer /one" 120 3 || die "Observer not responding on /one"
}

start_nginx() {
  if command -v nginx >/dev/null 2>&1 || [ -d /etc/nginx ]; then
    log "Starting nginx..."
    service nginx start 2>/dev/null || true
  fi
}

start_obs() {
  if [ "${SKIP_OBS:-0}" = "1" ]; then
    log "OBS install/start skipped (SKIP_OBS=1)"
    return 0
  fi

  if ! command -v obs >/dev/null 2>&1; then
    log "OBS Studio not installed; skipping OBS start"
    return 0
  fi

  log "Starting OBS Studio..."
  if ! pgrep -x Xvfb >/dev/null 2>&1; then
    nohup Xvfb :99 -screen 0 1920x1080x24 -ac >"$LOG_DIR/xvfb.log" 2>&1 &
    sleep 2
  fi

  mkdir -p /tmp/xdg-runtime-root
  chmod 700 /tmp/xdg-runtime-root 2>/dev/null || true

  if pgrep -x obs >/dev/null 2>&1; then
    log "OBS already running"
    return 0
  fi

  # OBS runs headless under Xvfb. A profile/scene collection still needs to be
  # configured once, but the app itself is now part of the startup stack.
  nohup env DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/xdg-runtime-root obs \
    >"$LOG_DIR/obs.log" 2>&1 &
}

start_runtime() {
  log "Starting runtime..."
  UVICORN_PIDS=$(pgrep -f "uvicorn src.main" 2>/dev/null || true)
  if [ -n "$UVICORN_PIDS" ]; then
    log "Killing existing uvicorn PIDs: $UVICORN_PIDS"
    kill -9 $UVICORN_PIDS 2>/dev/null || true
    sleep 2
  fi

  fuser -k 8888/tcp 2>/dev/null || true
  sleep 3
  cd "$REPO_DIR/runtime"
  source /opt/god-venv/bin/activate
  set -a
  # shellcheck disable=SC1090
  source "$REPO_DIR/.env.local"
  set +a
  nohup python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8888 >"$LOG_DIR/runtime.log" 2>&1 &
  cd "$REPO_DIR"
  wait_http "http://localhost:8888/health" "runtime /health" 120 3 || die "Runtime not responding"
}

main() {
  [ -z "${CUDA_VISIBLE_DEVICES:-}" ] && unset CUDA_VISIBLE_DEVICES
  log "GPU(s): $(nvidia-smi --list-gpus 2>/dev/null | head -2 || echo 'none - CPU mode')"

  ensure_repo
  configure_streaming_mode
  cleanup_stale_ports
  start_postgres
  start_redis
  start_nats
  start_ipfs
  start_ollama
  start_comfyui
  start_fish
  start_observer
  start_nginx
  start_obs
  start_runtime

  PUBLIC_IP=$(curl -sf --max-time 5 ifconfig.me 2>/dev/null || echo "<instance-ip>")
  log ""
  log "All required services are up."
  log "  Runtime   http://${PUBLIC_IP}:8888"
  log "  ComfyUI   http://${PUBLIC_IP}:8188"
  log "  Ollama    http://${PUBLIC_IP}:11434"
  log "  fish TTS  http://${PUBLIC_IP}:7860"
  log "  Observer  http://${PUBLIC_IP}:10517/one"
  log ""
  log "Genesis can run only after the stack is healthy:"
  log "  curl -s -X POST http://localhost:8888/creator/genesis -H 'Content-Type: application/json' -d '{\"confirm\": true}'"
}

main "$@"
