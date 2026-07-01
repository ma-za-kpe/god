#!/usr/bin/env bash
# Native GOD stack setup for Vast.ai — no Docker required.
# Runs all services directly on the host (Python, PostgreSQL, Redis, NATS, Ollama, IPFS).
#
# Usage (run ON the Vast.ai instance):
#   bash /root/vast-setup-native.sh
#
# Overrides:
#   OLLAMA_MODEL=llama3.2:3b   — smaller model (default: llama3.1:8b)
#   SKIP_FISH=1                — skip fish-speech install
#   SKIP_COMFYUI=1             — skip ComfyUI install
#   SKIP_IPFS=1                — skip IPFS daemon (avatar CID pinning disabled)
#   SKIP_OBS=1                 — skip OBS Studio install/start
#   POSTGRES_PASSWORD=xxx      — custom DB password (default: random)
#   REPO_BRANCH=<branch>       — branch to deploy (default: main)

set -euo pipefail

REPO_URL="https://github.com/ma-za-kpe/god.git"
REPO_DIR="/workspace/god"
REPO_BRANCH="${REPO_BRANCH:-main}"
OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.1:8b}"
SKIP_FISH="${SKIP_FISH:-0}"
SKIP_COMFYUI="${SKIP_COMFYUI:-0}"
SKIP_IPFS="${SKIP_IPFS:-0}"
SKIP_OBS="${SKIP_OBS:-0}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-$(openssl rand -hex 16)}"
CREATOR_GENESIS_TOKEN="${CREATOR_GENESIS_TOKEN:-$(openssl rand -hex 32)}"
BROADCAST_ENABLED_VALUE="false"
if [ "$SKIP_OBS" = "1" ]; then
  BROADCAST_ENABLED_VALUE="false"
fi
LOG_DIR="/var/log/god"

log() { echo "[vast-native] $*"; }
die() { log "ERROR: $*"; exit 1; }
mkdir -p "$LOG_DIR"

# ── 0. GPU + CUDA sanity ──────────────────────────────────────────────────────
# Vast.ai sometimes exports CUDA_VISIBLE_DEVICES="" which hides GPUs from CUDA
# even though nvidia-smi still sees them. Unset before any service starts.
[ -z "${CUDA_VISIBLE_DEVICES:-}" ] && unset CUDA_VISIBLE_DEVICES
log "GPU(s): $(nvidia-smi --list-gpus 2>/dev/null | head -2 || echo 'none — CPU mode')"

# ── Port conflict helper ──────────────────────────────────────────────────────
# Kill anything already bound to a port before starting a new service on it.
check_port() {
  local port=$1 name=$2
  if ss -tlnp 2>/dev/null | grep -q ":${port} "; then
    log "Port ${port} (${name}) already bound — releasing"
    fuser -k "${port}/tcp" 2>/dev/null || true
    sleep 2
  fi
}

export DEBIAN_FRONTEND=noninteractive

# ── 1. System packages ────────────────────────────────────────────────────────
log "Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
  curl git openssl ca-certificates \
  zstd \
  iproute2 psmisc \
  postgresql postgresql-client \
  redis-server \
  python3-pip python3-venv python3-dev \
  build-essential libssl-dev libffi-dev \
  ffmpeg libsndfile1 \
  portaudio19-dev \
  nodejs npm \
  obs-studio xvfb xauth dbus-x11

# ── 2. NATS server ────────────────────────────────────────────────────────────
if ! command -v nats-server &>/dev/null; then
  log "Installing NATS server..."
  NATS_VER="v2.10.22"
  curl -sL "https://github.com/nats-io/nats-server/releases/download/${NATS_VER}/nats-server-${NATS_VER}-linux-amd64.tar.gz" \
    | tar -xz -C /usr/local/bin --strip-components=1 "nats-server-${NATS_VER}-linux-amd64/nats-server"
fi
log "NATS: $(nats-server --version)"

# ── 3. Ollama (GPU-accelerated LLM) ──────────────────────────────────────────
if ! command -v ollama &>/dev/null; then
  log "Installing Ollama..."
  curl -fsSL https://ollama.com/install.sh | sh
fi
log "Ollama: $(ollama --version 2>/dev/null | head -1)"

# ── 4. Clone / update repo ────────────────────────────────────────────────────
if [ -d "$REPO_DIR/.git" ]; then
  log "Repo exists — syncing branch ${REPO_BRANCH}..."
  GIT_TERMINAL_PROMPT=0 git -C "$REPO_DIR" fetch origin || true
  git -C "$REPO_DIR" checkout "$REPO_BRANCH" 2>/dev/null \
    || die "Branch ${REPO_BRANCH} not found on remote"
  GIT_TERMINAL_PROMPT=0 git -C "$REPO_DIR" pull \
    || die "git pull failed — check network or branch state"
else
  log "Cloning ${REPO_URL} (branch: ${REPO_BRANCH})..."
  mkdir -p /workspace
  GIT_TERMINAL_PROMPT=0 git clone --branch "$REPO_BRANCH" --single-branch "$REPO_URL" "$REPO_DIR" \
    || die "git clone failed"
fi
cd "$REPO_DIR"

# ── 5. PostgreSQL ─────────────────────────────────────────────────────────────
log "Configuring PostgreSQL..."
check_port 5432 "PostgreSQL"
service postgresql start 2>/dev/null || pg_ctlcluster 14 main start 2>/dev/null \
  || die "Cannot start PostgreSQL"
# Poll until ready — first boot can take 10+ seconds
for i in $(seq 1 15); do
  pg_isready -U postgres -h localhost &>/dev/null && break
  sleep 2
done
pg_isready -U postgres -h localhost || die "PostgreSQL failed to become ready after 30s"
sudo -u postgres psql -c "CREATE USER god WITH PASSWORD '${POSTGRES_PASSWORD}';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE god OWNER god;" 2>/dev/null || true
sudo -u postgres psql -c "ALTER USER god WITH PASSWORD '${POSTGRES_PASSWORD}';" 2>/dev/null || true
log "PostgreSQL ready"

# ── 6. Redis ──────────────────────────────────────────────────────────────────
log "Starting Redis..."
check_port 6379 "Redis"
service redis-server start || redis-server --daemonize yes \
  || die "Cannot start Redis"
sleep 2
redis-cli ping &>/dev/null && log "Redis ready" || die "Redis not responding after start"

# ── 7. NATS ───────────────────────────────────────────────────────────────────
log "Starting NATS..."
if ! pgrep -x nats-server &>/dev/null; then
  check_port 4222 "NATS"
  nohup nats-server -p 4222 --jetstream > "$LOG_DIR/nats.log" 2>&1 &
  sleep 2
fi
log "NATS ready"

# ── 8. IPFS daemon ────────────────────────────────────────────────────────────
if [ "$SKIP_IPFS" = "0" ]; then
  log "Setting up IPFS..."
  if ! command -v ipfs &>/dev/null; then
    IPFS_VER="v0.28.0"
    curl -sL "https://dist.ipfs.tech/kubo/${IPFS_VER}/kubo_${IPFS_VER}_linux-amd64.tar.gz" \
      | tar -xz -C /tmp kubo
    install -m 755 /tmp/kubo/ipfs /usr/local/bin/ipfs
    rm -rf /tmp/kubo
  fi
  if [ ! -f /root/.ipfs/config ]; then
    ipfs init --profile server
  fi
  if ! pgrep -x ipfs &>/dev/null; then
    check_port 5001 "IPFS API"
    check_port 8080 "IPFS Gateway"
    nohup ipfs daemon --enable-gc > "$LOG_DIR/ipfs.log" 2>&1 &
  fi
  for i in $(seq 1 15); do
    curl -sf http://localhost:5001/api/v0/version &>/dev/null && break
    sleep 2
  done
  curl -sf http://localhost:5001/api/v0/version &>/dev/null \
    && log "IPFS ready" \
    || log "WARNING: IPFS not responding — avatar CID pinning will fail"
fi

# ── 9. Runtime Python environment ─────────────────────────────────────────────
log "Installing runtime Python dependencies..."
cd "$REPO_DIR/runtime"
python3 -m venv /opt/god-venv
source /opt/god-venv/bin/activate

pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt 2>/dev/null || \
  pip install --quiet \
    fastapi uvicorn httpx asyncpg psycopg2-binary redis nats-py \
    aiofiles python-multipart ipfshttpclient \
    web3 eth-account 2>/dev/null || true

cd "$REPO_DIR"

# ── 10. .env.local ────────────────────────────────────────────────────────────
log "Writing .env.local..."
cat > .env.local <<EOF
# Generated by vast-setup-native.sh — $(date -u +%Y-%m-%dT%H:%M:%SZ)

POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
DATABASE_URL=postgresql://god:${POSTGRES_PASSWORD}@localhost:5432/god
LOCAL_DEV_MODE=false

# LLM — Ollama on localhost
LLM_PROVIDER=ollama
LLM_MODEL=${OLLAMA_MODEL}
OLLAMA_BASE_URL=http://localhost:11434

# All services on localhost (native, no Docker)
NATS_URL=nats://localhost:4222
REDIS_URL=redis://localhost:6379
IPFS_API=http://localhost:5001
# Vast native live-test profile runs one local Kubo API. This is not Law-2
# durable replication; Compose remains the three-node profile.
IPFS_API_ENDPOINTS=http://localhost:5001
MIN_IPFS_PINS=1

# Avatar genesis — SDXL
COMFYUI_PORTRAIT_TEMPLATE=sdxl_portrait.json
COMFYUI_EXPRESSION_TEMPLATE=sdxl_expression.json
AVATAR_GENESIS_ENABLED=true
AVATAR_ENABLED=true
COMFYUI_ENDPOINT=http://localhost:8188
AVATAR_HEALTH_URL=http://localhost:8188

# Voice — fish-speech
VOICE_ENABLED=true
TTS_ENDPOINT=http://localhost:7860
VOICE_HEALTH_URL=http://localhost:7860
VOICE_PROVIDER=fish
TTS_PROVIDER=fish
VOICE_MODEL=fish-speech-s2-pro
TTS_MODEL=fish-speech-s2-pro
VOICE_NAME=agent-reference
VOICE_HEALTH_FAILURE_GRACE_SECONDS=180
FISH_DEVICE=cuda
FISH_HALF_MODE=--half
STREAMING_MODE=auto
YOUTUBE_ENABLED=false
YOUTUBE_DRY_RUN=true
YOUTUBE_AUTO_GO_LIVE=false
YOUTUBE_BROADCAST_ID=
YOUTUBE_GO_LIVE_TIMEOUT_S=90
YOUTUBE_GO_LIVE_POLL_S=5
# Empty lets vast-restart-services.sh disable LTX/Wan/offline GPU jobs when
# live streaming, and allow them during dry-run/offline validation.
GPU_BACKGROUND_JOBS_ALLOWED=
OBS_WEBSOCKET_URL=
OBS_WEBSOCKET_PASSWORD=
CREATOR_GENESIS_TOKEN=${CREATOR_GENESIS_TOKEN}
CREATOR_TOKEN=${CREATOR_GENESIS_TOKEN}
ALLOW_TOKENLESS_CREATOR=false
ALLOW_INSECURE_LOCAL_ENDPOINTS=false
BROADCAST_ENABLED=${BROADCAST_ENABLED_VALUE}
BROADCAST_DRY_RUN=true
OBS_BROWSER_SOURCE=god-browser
OBS_BROWSER_URL=http://localhost:10517/one
OBS_BROWSER_WIDTH=1920
OBS_BROWSER_HEIGHT=1080
OBS_AUTO_START_STREAM=false
OBS_STREAM_SERVER=rtmp://a.rtmp.youtube.com/live2
OBS_STREAM_KEY=
EOF
log ".env.local written"

# ── 11. Ollama daemon + model ─────────────────────────────────────────────────
log "Starting Ollama daemon..."
if ! pgrep -x ollama &>/dev/null; then
  check_port 11434 "Ollama"
  # OLLAMA_KEEP_ALIVE=0 unloads the model from VRAM after each request,
  # freeing GPU memory for ComfyUI and fish-speech between LLM calls.
  OLLAMA_KEEP_ALIVE=0 nohup ollama serve > "$LOG_DIR/ollama.log" 2>&1 &
fi
log "Waiting for Ollama API..."
for i in $(seq 1 30); do
  curl -sf http://localhost:11434/api/tags &>/dev/null && break
  sleep 3
done
curl -sf http://localhost:11434/api/tags &>/dev/null || die "Ollama API not responding after 90s"
log "Pulling ${OLLAMA_MODEL}..."
ollama pull "$OLLAMA_MODEL" || die "Failed to pull model ${OLLAMA_MODEL} — check disk space and network"
log "Ollama ready"

# ── 12. ComfyUI (optional) ────────────────────────────────────────────────────
if [ "$SKIP_COMFYUI" = "0" ]; then
  log "Installing ComfyUI..."
  if [ ! -d /opt/ComfyUI ]; then
    git clone --depth 1 https://github.com/comfyanonymous/ComfyUI /opt/ComfyUI
  fi
  cd /opt/ComfyUI
  source /opt/god-venv/bin/activate
  pip install --quiet -r requirements.txt

  log "Downloading SDXL base 1.0 (~6.5 GB)..."
  mkdir -p models/checkpoints
  python3 -c "
from huggingface_hub import hf_hub_download
import signal
signal.alarm(600)  # 10-minute hard timeout
hf_hub_download(
    repo_id='stabilityai/stable-diffusion-xl-base-1.0',
    filename='sd_xl_base_1.0.safetensors',
    local_dir='models/checkpoints',
)
print('SDXL ready')
" || log "WARNING: SDXL download failed — avatar portrait generation will be skipped"

  log "Starting ComfyUI on :8188..."
  check_port 8188 "ComfyUI"
  nohup python3 main.py --listen 0.0.0.0 --port 8188 --disable-auto-launch \
    > "$LOG_DIR/comfyui.log" 2>&1 &
  cd "$REPO_DIR"
fi

# ── 13. fish-speech (optional) ────────────────────────────────────────────────
if [ "$SKIP_FISH" = "0" ]; then
  log "Installing fish-speech..."
  if ! command -v uv &>/dev/null; then
    pip install --quiet uv
  fi
  if [ ! -d /opt/fish-speech ]; then
    git clone --depth 1 https://github.com/fishaudio/fish-speech /opt/fish-speech
  fi
  cd /opt/fish-speech
  UV=$(find /opt/god-venv/bin /root/.local/bin -name uv -type f -print -quit 2>/dev/null || true)
  UV="${UV:-$(command -v uv)}"
  "$UV" sync --no-dev --quiet

  log "Downloading Fish Audio S2-Pro models (~11 GB)..."
  pip install --quiet "huggingface_hub[hf_xet]"
  python3 -c "
from huggingface_hub import snapshot_download
import signal
signal.alarm(900)  # 15-minute hard timeout
snapshot_download(
    repo_id='fishaudio/s2-pro',
    local_dir='checkpoints/s2-pro',
    ignore_patterns=['*.gguf','*.onnx','*.txt','*.md','README*'],
)
print('Fish Audio S2-Pro models ready')
" || log "WARNING: fish-speech model download failed — voice synthesis will be skipped"

  log "Starting fish-speech on :7860..."
  check_port 7860 "fish-speech"
  nohup "$UV" run python tools/api_server.py \
    --llama-checkpoint-path /opt/fish-speech/checkpoints/s2-pro \
    --decoder-checkpoint-path /opt/fish-speech/checkpoints/s2-pro/codec.pth \
    --decoder-config-name modded_dac_vq \
    --device cuda \
    --listen 0.0.0.0:7860 \
    > "$LOG_DIR/fish-speech.log" 2>&1 &
  cd "$REPO_DIR"
fi

# ── 14. Database schema init ──────────────────────────────────────────────────
log "Initialising database schema..."
PGPASSWORD="${POSTGRES_PASSWORD}" psql -U god -d god -h localhost \
  -f "$REPO_DIR/scripts/init-db.sql" 2>&1 | tee -a "$LOG_DIR/schema.log"
# Verify agents table exists — non-zero exit is expected when tables already exist
PGPASSWORD="${POSTGRES_PASSWORD}" psql -U god -d god -h localhost \
  -c "SELECT count(*) FROM agents;" &>/dev/null \
  || die "Schema init failed and agents table is missing — see $LOG_DIR/schema.log"
log "Schema ready"

# ── 15. Alembic migrations ────────────────────────────────────────────────────
log "Running alembic migrations..."
cd "$REPO_DIR/runtime"
source /opt/god-venv/bin/activate
# Export DATABASE_URL before running alembic so it picks up the right DB
export DATABASE_URL="postgresql://god:${POSTGRES_PASSWORD}@localhost:5432/god"
if ! python3 -m alembic upgrade head 2>&1 | tee -a "$LOG_DIR/alembic.log"; then
  log "WARNING: alembic migration failed — see $LOG_DIR/alembic.log"
fi

# ── 16. Start the runtime ─────────────────────────────────────────────────────
log "Starting GOD runtime on :8888..."
cd "$REPO_DIR/runtime"
source /opt/god-venv/bin/activate
set -a; source "$REPO_DIR/.env.local"; set +a
check_port 8888 "Runtime"
nohup python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8888 \
  > "$LOG_DIR/runtime.log" 2>&1 &

# ── Done ──────────────────────────────────────────────────────────────────────
PUBLIC_IP=$(curl -sf --max-time 5 ifconfig.me 2>/dev/null || echo "<instance-ip>")

log ""
log "=================================================="
log " GOD stack is live (native, no Docker)"
log ""
log "   Runtime   http://${PUBLIC_IP}:8888"
log "   ComfyUI   http://${PUBLIC_IP}:8188"
log "   Ollama    http://${PUBLIC_IP}:11434"
log "   Fish TTS  http://${PUBLIC_IP}:7860"
log ""
log " Logs: ${LOG_DIR}/"
log "=================================================="

log "Waiting for runtime to become healthy (up to 90s)..."
RUNTIME_UP=0
for i in $(seq 1 30); do
  if curl -sf http://localhost:8888/ready &>/dev/null; then
    RUNTIME_UP=1; break
  fi
  sleep 3
done

if [ "$RUNTIME_UP" = "1" ]; then
  log "Runtime readiness: OK"
else
  log "WARNING: Runtime not responding after 90s — check $LOG_DIR/runtime.log"
fi
curl -sf http://localhost:11434/api/tags &>/dev/null && log "Ollama health: OK" || log "Ollama: not responding"

log ""
log "Genesis (run after all services are green):"
log "  curl -s -X POST http://localhost:8888/creator/genesis \\"
log "    -H 'Content-Type: application/json' \\"
log "    -H \"X-Creator-Token: ${CREATOR_GENESIS_TOKEN}\" \\"
log "    -d '{\"confirm\": true}' | python3 -m json.tool"
