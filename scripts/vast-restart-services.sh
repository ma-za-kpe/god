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
  if ! pgrep -x ipfs >/dev/null 2>&1; then
    check_port 5001 "IPFS API"
    check_port 8080 "IPFS Gateway"
    nohup ipfs daemon --enable-gc >"$LOG_DIR/ipfs.log" 2>&1 &
  fi
  wait_http "http://localhost:5001/api/v0/version" "IPFS" 90 2 || die "IPFS not responding"
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
  if ! pgrep -f "tools/api_server.py" >/dev/null 2>&1; then
    check_port 7860 "fish-speech"
    UV=$(find /opt/god-venv/bin /root/.local/bin -name uv -type f 2>/dev/null | head -1)
    UV="${UV:-$(command -v uv)}"
    cd /opt/fish-speech
    nohup "$UV" run python tools/api_server.py \
      --llama-checkpoint-path /opt/fish-speech/checkpoints/s2-pro \
      --decoder-checkpoint-path /opt/fish-speech/checkpoints/s2-pro/codec.pth \
      --decoder-config-name modded_dac_vq \
      --device cuda \
      --listen 0.0.0.0:7860 \
      >"$LOG_DIR/fish-speech.log" 2>&1 &
    cd "$REPO_DIR"
  fi
  wait_http "http://localhost:7860/" "fish-speech" 150 5 || die "fish-speech not responding"
}

start_observer() {
  if [ ! -d "$REPO_DIR/observer" ]; then
    die "$REPO_DIR/observer missing"
  fi

  log "Starting observer on :3000..."
  if ! pgrep -f "observer/serve.py" >/dev/null 2>&1 && ! pgrep -f "vite" >/dev/null 2>&1; then
    check_port 3000 "observer"
    cd "$REPO_DIR/observer"
    if [ ! -d node_modules ]; then
      npm ci
    fi
    nohup npm run dev -- --host 0.0.0.0 --port 3000 >"$LOG_DIR/observer.log" 2>&1 &
    cd "$REPO_DIR"
  fi
  wait_http "http://localhost:3000/one" "observer /one" 120 3 || die "Observer not responding on /one"
}

start_nginx() {
  if command -v nginx >/dev/null 2>&1 || [ -d /etc/nginx ]; then
    log "Starting nginx..."
    service nginx start 2>/dev/null || true
  fi
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
  start_postgres
  start_redis
  start_nats
  start_ipfs
  start_ollama
  start_comfyui
  start_fish
  start_observer
  start_nginx
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
