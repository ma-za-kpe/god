#!/usr/bin/env bash
# Restart all GOD services after a Vast.ai instance reboot.
# Run this ON the instance: bash /workspace/god/scripts/vast-restart-services.sh
#
# The setup script (vast-setup-native.sh) installs everything once.
# This script just restarts the running services — no re-downloading.

set -euo pipefail

REPO_DIR="/workspace/god"
LOG_DIR="/var/log/god"
mkdir -p "$LOG_DIR"

log() { echo "[vast-restart] $*"; }

# ── Load saved env ────────────────────────────────────────────────────────────
if [ -f "$REPO_DIR/.env.local" ]; then
  set -a; source "$REPO_DIR/.env.local"; set +a
else
  log "ERROR: $REPO_DIR/.env.local not found — run vast-setup-native.sh first"
  exit 1
fi

# Pull latest code on the correct branch
REPO_BRANCH="${REPO_BRANCH:-feat/twitch-ne-mo-showrunner}"
log "Syncing repo to branch ${REPO_BRANCH}..."
GIT_TERMINAL_PROMPT=0 git -C "$REPO_DIR" fetch origin || true
git -C "$REPO_DIR" checkout "$REPO_BRANCH" 2>/dev/null || true
GIT_TERMINAL_PROMPT=0 git -C "$REPO_DIR" pull || log "WARNING: git pull failed"

# ── Unset empty CUDA_VISIBLE_DEVICES ─────────────────────────────────────────
# Vast.ai containers sometimes export CUDA_VISIBLE_DEVICES="" which hides the
# GPU from all CUDA programs even though nvidia-smi still sees it.
[ -z "${CUDA_VISIBLE_DEVICES:-}" ] && unset CUDA_VISIBLE_DEVICES
log "GPU visible: $(nvidia-smi --list-gpus 2>/dev/null | head -2 || echo 'none')"

# ── PostgreSQL ────────────────────────────────────────────────────────────────
log "Starting PostgreSQL..."
service postgresql start 2>/dev/null || pg_ctlcluster 14 main start 2>/dev/null || true
sleep 2

# ── Redis ─────────────────────────────────────────────────────────────────────
log "Starting Redis..."
service redis-server start 2>/dev/null || redis-server --daemonize yes || true
sleep 1
redis-cli ping &>/dev/null && log "Redis OK" || log "WARNING: Redis not responding"

# ── NATS ──────────────────────────────────────────────────────────────────────
log "Starting NATS..."
if ! pgrep -x nats-server &>/dev/null; then
  nohup nats-server -p 4222 --jetstream > "$LOG_DIR/nats.log" 2>&1 &
fi
sleep 2

# ── Ollama ────────────────────────────────────────────────────────────────────
log "Starting Ollama..."
if ! pgrep -x ollama &>/dev/null; then
  # OLLAMA_KEEP_ALIVE=0 releases VRAM immediately after each request so
  # ComfyUI and fish-speech can use the GPU between LLM calls.
  OLLAMA_KEEP_ALIVE=0 nohup ollama serve > "$LOG_DIR/ollama.log" 2>&1 &
fi
for i in $(seq 1 20); do
  curl -sf http://localhost:11434/api/tags &>/dev/null && break
  sleep 3
done
log "Ollama OK"

# ── ComfyUI ───────────────────────────────────────────────────────────────────
if [ -d /opt/ComfyUI ] && [ "${SKIP_COMFYUI:-0}" = "0" ]; then
  log "Starting ComfyUI..."
  if ! pgrep -f "ComfyUI/main.py" &>/dev/null; then
    cd /opt/ComfyUI
    source /opt/god-venv/bin/activate
    nohup python3 main.py --listen 0.0.0.0 --port 8188 --disable-auto-launch \
      > "$LOG_DIR/comfyui.log" 2>&1 &
  fi
  sleep 10
  curl -sf http://localhost:8188/ &>/dev/null && log "ComfyUI OK" || log "ComfyUI still loading..."
fi

# ── fish-speech ───────────────────────────────────────────────────────────────
if [ -d /opt/fish-speech ] && [ "${SKIP_FISH:-0}" = "0" ]; then
  log "Starting fish-speech..."
  if ! pgrep -f "fish_speech" &>/dev/null; then
    UV=$(find /opt/god-venv/bin /root/.local/bin -name uv -type f 2>/dev/null | head -1)
    UV="${UV:-$(command -v uv)}"
    cd /opt/fish-speech
    nohup "$UV" run tools/api_server.py \
      --llama-checkpoint-path checkpoints \
      --decoder-checkpoint-path checkpoints/codec.pth \
      --decoder-config-name modded_dac_vq \
      --device cuda \
      --listen 0.0.0.0:7860 \
      > "$LOG_DIR/fish-speech.log" 2>&1 &
  fi
  sleep 5
  curl -sf http://localhost:7860/ &>/dev/null && log "fish-speech OK" || log "fish-speech still loading..."
fi

# ── GOD runtime ───────────────────────────────────────────────────────────────
log "Starting GOD runtime..."
# Force-kill any stale uvicorn process (prevents stuck-18:04-style ghost)
UVICORN_PIDS=$(pgrep -f "uvicorn src.main" 2>/dev/null || true)
if [ -n "$UVICORN_PIDS" ]; then
  log "Killing existing uvicorn PIDs: $UVICORN_PIDS"
  kill -9 $UVICORN_PIDS 2>/dev/null || true
  sleep 2
fi
fuser -k 8888/tcp 2>/dev/null || true
sleep 1
cd "$REPO_DIR/runtime"
source /opt/god-venv/bin/activate
set -a; source "$REPO_DIR/.env.local"; set +a
nohup python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8888 \
  > "$LOG_DIR/runtime.log" 2>&1 &
sleep 8
curl -sf http://localhost:8888/health &>/dev/null && log "Runtime OK" || log "WARNING: runtime not responding"

# ── Summary ───────────────────────────────────────────────────────────────────
PUBLIC_IP=$(curl -sf --max-time 5 ifconfig.me 2>/dev/null || echo "<instance-ip>")
log ""
log "Services restarted. Check health:"
log "  curl http://${PUBLIC_IP}:8888/health"
log "  curl http://${PUBLIC_IP}:11434/api/tags"
log "  curl http://${PUBLIC_IP}:8188/"
log "  curl http://${PUBLIC_IP}:7860/"
log ""
log "Genesis (after all services are green):"
log "  curl -s -X POST http://localhost:8888/creator/genesis \\"
log "    -H 'Content-Type: application/json' \\"
log "    -d '{\"confirm\": true}' | python3 -m json.tool"
