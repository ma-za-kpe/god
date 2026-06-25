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

LOCK_DIR="/var/run/god-vast-restart.lock.d"
acquire_launcher_lock() {
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    printf '%s\n' "$$" >"$LOCK_DIR/pid"
    trap 'rm -f "$LOCK_DIR/pid"; rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT
    return 0
  fi

  if [ -f "$LOCK_DIR/pid" ]; then
    local lock_pid=""
    lock_pid="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
    if [ -n "$lock_pid" ] && kill -0 "$lock_pid" 2>/dev/null; then
      die "another vast-restart-services.sh instance is already running"
    fi
  fi

  rm -rf "$LOCK_DIR" 2>/dev/null || true
  mkdir "$LOCK_DIR" || die "unable to create launcher lock directory"
  printf '%s\n' "$$" >"$LOCK_DIR/pid"
  trap 'rm -f "$LOCK_DIR/pid"; rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT
}

acquire_launcher_lock

check_port() {
  local port=$1 name=$2
  if ss -tlnp 2>/dev/null | grep -q ":${port} "; then
    log "Port ${port} (${name}) already bound; releasing it"
    fuser -k "${port}/tcp" 2>/dev/null || true
    sleep 2
  fi
}

cleanup_stale_ports() {
  local stage="${1:-all}"
  local port name
  case "$stage" in
    core)
      set -- \
        "5432 PostgreSQL" \
        "6379 Redis" \
        "4222 NATS" \
        "5001 IPFS-API" \
        "8080 IPFS-Gateway" \
        "11434 Ollama" \
        "8188 ComfyUI"
      ;;
    voice)
      set -- "7860 fish-speech"
      ;;
    observer)
      set -- "3000 Observer" "10517 nginx-proxy"
      ;;
    streaming)
      set -- "4444 OBS-websocket"
      ;;
    runtime)
      set -- "8888 Runtime" "10515 nginx-proxy" "10516 nginx-proxy"
      ;;
    all|*)
      set -- \
        "5432 PostgreSQL" \
        "6379 Redis" \
        "4222 NATS" \
        "5001 IPFS-API" \
        "8080 IPFS-Gateway" \
        "11434 Ollama" \
        "8188 ComfyUI" \
        "7860 fish-speech" \
        "3000 Observer" \
        "8888 Runtime" \
        "10515 nginx-proxy" \
        "10516 nginx-proxy" \
        "10517 nginx-proxy" \
        "4444 OBS-websocket"
      ;;
  esac

  for entry in "$@"; do
    port="${entry%% *}"
    name="${entry#* }"
    [ -z "${port:-}" ] && continue
    check_port "$port" "$name"
  done
}

obs_websocket_ready() {
  python3 - <<'PY' >/dev/null 2>&1
from pathlib import Path
import base64
import hashlib
import json
from websocket import create_connection

profile_candidates = [
    Path("/home/stream/.config/obs-studio/basic/profiles/Untitled/basic.ini"),
    Path("/root/.config/obs-studio/basic/profiles/Untitled/basic.ini"),
]
profile = next((p for p in profile_candidates if p.is_file()), None)
if profile is None:
    raise SystemExit("missing OBS profile basic.ini")
text = profile.read_text(encoding="utf-8", errors="ignore")
auth_secret = ""
for line in text.splitlines():
    if line.startswith("AuthSecret="):
        auth_secret = line.split("=", 1)[1].strip()
        break

if not auth_secret:
    raise SystemExit("missing OBS websocket AuthSecret")

ws = create_connection("ws://127.0.0.1:4444", timeout=6)

def call(payload: dict[str, object]) -> dict[str, object]:
    ws.send(json.dumps(payload))
    return json.loads(ws.recv())

auth = call({"request-type": "GetAuthRequired", "message-id": "1"})
if auth.get("authRequired"):
    challenge = str(auth["challenge"])
    ws_auth = base64.b64encode(
        hashlib.sha256((auth_secret + challenge).encode("utf-8")).digest()
    ).decode("utf-8")
    result = call({
        "request-type": "Authenticate",
        "message-id": "2",
        "auth": ws_auth,
    })
    if result.get("status") != "ok":
        raise SystemExit("OBS websocket auth failed")

status = call({"request-type": "GetStreamingStatus", "message-id": "3"})
if status.get("status") != "ok":
    raise SystemExit("OBS websocket status failed")

ws.close()
PY
}

wait_for_x_display() {
  local attempts=${1:-30}
  local delay=${2:-2}
  for _ in $(seq 1 "$attempts"); do
    if env DISPLAY=:99 xset q >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay"
  done
  return 1
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

wait_ready_json() {
  local url=$1 name=$2 timeout=${3:-90} delay=${4:-3}
  local elapsed=0 body=""
  while [ "$elapsed" -lt "$timeout" ]; do
    body="$(curl -sS "$url" 2>/dev/null || true)"
    if echo "$body" | grep -q '"ok"[[:space:]]*:[[:space:]]*true'; then
      log "${name} OK"
      return 0
    fi
    sleep "$delay"
    elapsed=$((elapsed + delay))
  done
  log "${name} not ready; last response: ${body:-<empty>}"
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

  if [ -z "${CREATOR_GENESIS_TOKEN:-}" ] && [ -n "${CREATOR_TOKEN:-}" ]; then
    export CREATOR_GENESIS_TOKEN="$CREATOR_TOKEN"
    log "Using legacy CREATOR_TOKEN as CREATOR_GENESIS_TOKEN"
  fi

  REPO_BRANCH="${REPO_BRANCH:-feat/twitch-ne-mo-showrunner}"
  current_branch="$(git -C "$REPO_DIR" branch --show-current 2>/dev/null || true)"
  current_sha="$(git -C "$REPO_DIR" rev-parse --short HEAD 2>/dev/null || true)"
  if [ -z "$current_branch" ]; then
    die "unable to determine current repo branch"
  fi
  if [ "$current_branch" != "$REPO_BRANCH" ]; then
    die "repo on ${current_branch}, expected ${REPO_BRANCH}; run a deploy step first"
  fi
  log "Repo ready on ${current_branch} @ ${current_sha}"
}

configure_streaming_mode() {
  # Browser source is always /stage — hardcoded, no override.
  export OBS_BROWSER_SOURCE=god-browser
  export OBS_BROWSER_URL=http://localhost:10517/stage

  if [ -z "${OBS_STREAM_SERVER:-}" ]; then
    export OBS_STREAM_SERVER=rtmp://a.rtmp.youtube.com/live2
  fi
  if [ -z "${OBS_WEBSOCKET_URL:-}" ]; then
    export OBS_WEBSOCKET_URL=ws://localhost:4444
  fi
  if [ -z "${OBS_CAPTURE_MODE:-}" ]; then
    export OBS_CAPTURE_MODE=window
  fi
  if [ -z "${OBS_CAPTURE_SOURCE_KIND:-}" ]; then
    export OBS_CAPTURE_SOURCE_KIND=xshm_input
  fi
  if [ -z "${OBS_CAPTURE_WINDOW_CLASS:-}" ]; then
    export OBS_CAPTURE_WINDOW_CLASS=Firefox
  fi
  if [ -z "${OBS_CAPTURE_WINDOW_NAME:-}" ]; then
    export OBS_CAPTURE_WINDOW_NAME=Firefox
  fi

  # Always stream to YouTube when the stream key is present — no flag required.
  if [ -n "${OBS_STREAM_KEY:-}" ]; then
    export YOUTUBE_ENABLED=true
    export YOUTUBE_DRY_RUN=false
    export BROADCAST_ENABLED=true
    export BROADCAST_DRY_RUN=false
    log "Stream key present: YouTube + OBS live streaming enabled (streaming /stage)"
    return 0
  fi

  export YOUTUBE_ENABLED=false
  export YOUTUBE_DRY_RUN=true
  export BROADCAST_ENABLED=false
  export BROADCAST_DRY_RUN=true
  log "No OBS_STREAM_KEY — streaming in dry-run mode"
}

streaming_launch_requested() {
  # Launch OBS and start stream whenever the stream key is available.
  if [ -n "${OBS_STREAM_KEY:-}" ] && [ -n "${OBS_WEBSOCKET_URL:-}" ]; then
    return 0
  fi
  return 1
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
    # Keep Ollama off the GPU on single-card hosts so fish-speech can stay healthy.
    CUDA_VISIBLE_DEVICES="" OLLAMA_KEEP_ALIVE=0 nohup ollama serve >"$LOG_DIR/ollama.log" 2>&1 &
  fi
  wait_http "http://localhost:11434/api/tags" "Ollama" 90 3 || die "Ollama not responding"
}

fish_tts_ready() {
  local endpoint="${VOICE_HEALTH_URL:-${TTS_ENDPOINT:-http://localhost:7860}}"
  local seed_audio="$REPO_DIR/runtime/seed_utterances/philosopher.wav"
  local tmp_body http_code audio_b64 payload

  [ -f "$seed_audio" ] || return 1

  audio_b64="$(base64 -w0 "$seed_audio" 2>/dev/null || base64 "$seed_audio" | tr -d '\n')"
  payload="$(printf '{"text":"voice health check","references":[{"audio":"%s","text":""}],"format":"wav","streaming":false}' "$audio_b64")"
  tmp_body="$(mktemp)"
  http_code="$(curl -sS -o "$tmp_body" -w '%{http_code}' -X POST "${endpoint%/}/v1/tts" -H 'Content-Type: application/json' --data "$payload" 2>/dev/null || true)"
  if [ "${http_code:-000}" -ge 200 ] && [ "${http_code:-000}" -lt 300 ] && [ -s "$tmp_body" ]; then
    rm -f "$tmp_body"
    return 0
  fi

  log "fish-speech synthesis probe failed: HTTP ${http_code:-000}; body=$(tr '\n' ' ' < "$tmp_body" 2>/dev/null | cut -c1-200)"
  rm -f "$tmp_body"
  return 1
}

fish_process_is_cuda() {
  ps -ef | grep -F "tools/api_server.py" | grep -v grep | grep -q -- "--device cuda"
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
  local min_free_vram_mb="${FISH_MIN_FREE_VRAM_MB:-3072}"
  local fish_device="${FISH_DEVICE:-cuda}"
  local fish_half_flag="${FISH_HALF_MODE:---half}"
  if [ "$fish_device" != "cuda" ]; then
    die "fish-speech must run on GPU; set FISH_DEVICE=cuda"
  fi
  if [ -n "${FISH_DEVICE:-}" ]; then
    log "FISH_DEVICE=${FISH_DEVICE} forced by environment"
  fi
  if command -v nvidia-smi >/dev/null 2>&1; then
    local free_vram_mb
    free_vram_mb="$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits 2>/dev/null | awk 'NR==1 {gsub(/[^0-9]/,""); print $1}' || true)"
    if [ -n "${free_vram_mb:-}" ] && [ "${free_vram_mb:-0}" -lt "$min_free_vram_mb" ]; then
      log "GPU headroom for fish-speech is low (${free_vram_mb} MiB free); starting on CUDA with ${fish_half_flag:-no} half-precision"
    fi
  fi
  if fish_process_is_cuda && fish_tts_ready; then
    log "fish-speech already healthy on CUDA"
    return 0
  fi
  if pgrep -f "tools/api_server.py" >/dev/null 2>&1; then
    log "Killing existing fish-speech processes"
    pkill -9 -f "tools/api_server.py" 2>/dev/null || true
    sleep 3
  fi
  if pgrep -f "/opt/fish-speech/.venv/bin/python.*api_server.py" >/dev/null 2>&1; then
    pkill -9 -f "/opt/fish-speech/.venv/bin/python.*api_server.py" 2>/dev/null || true
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
  UV="${UV:-$(command -v uv 2>/dev/null || true)}"
  local fish_launcher="/tmp/god-fish-speech-launch.sh"
  cat >"$fish_launcher" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd /opt/fish-speech
exec >>"$LOG_DIR/fish-speech.log" 2>&1
echo "[$(date -Is)] fish-speech launcher starting"
$(if [ -n "${UV:-}" ]; then
    printf 'exec "%s" run python tools/api_server.py --llama-checkpoint-path /opt/fish-speech/checkpoints/s2-pro --decoder-checkpoint-path /opt/fish-speech/checkpoints/s2-pro/codec.pth --decoder-config-name modded_dac_vq --device %s %s --listen 0.0.0.0:7860\n' "$UV" "$fish_device" "${fish_half_flag:-}"
  else
    printf 'source /opt/god-venv/bin/activate\nexec python3 tools/api_server.py --llama-checkpoint-path /opt/fish-speech/checkpoints/s2-pro --decoder-checkpoint-path /opt/fish-speech/checkpoints/s2-pro/codec.pth --decoder-config-name modded_dac_vq --device %s %s --listen 0.0.0.0:7860\n' "$fish_device" "${fish_half_flag:-}"
  fi)
EOF
  chmod +x "$fish_launcher"

  if command -v tmux >/dev/null 2>&1; then
    tmux kill-session -t god-fish-speech 2>/dev/null || true
    tmux new-session -d -s god-fish-speech /bin/bash "$fish_launcher" >/dev/null 2>&1 || die "failed to start fish-speech via tmux"
  else
    cd /opt/fish-speech
    nohup /bin/bash "$fish_launcher" >"$LOG_DIR/fish-speech.log" 2>&1 &
    cd "$REPO_DIR"
  fi
  local fish_ready_attempts=60
  for _ in $(seq 1 "$fish_ready_attempts"); do
    if fish_tts_ready; then
      log "fish-speech synthesis probe OK"
      return 0
    fi
    sleep 5
  done
  die "fish-speech synthesis probe did not succeed"
}

start_observer() {
  if [ ! -d "$REPO_DIR/observer" ]; then
    die "$REPO_DIR/observer missing"
  fi

  log "Starting observer static server on :3000..."
  if pgrep -f 'observer/serve.py' >/dev/null 2>&1; then
    log "Killing existing observer serve.py process"
    pkill -9 -f 'observer/serve.py' 2>/dev/null || true
    sleep 2
  fi
  check_port 3000 "observer"
  cd "$REPO_DIR/observer"
  nohup python3 serve.py >"$LOG_DIR/observer.log" 2>&1 &
  cd "$REPO_DIR"
  wait_http "http://localhost:3000/stage" "observer /stage" 120 3 || die "Observer not responding on /stage"
}

ensure_browser_user() {
  if ! id stream >/dev/null 2>&1; then
    log "Creating browser user 'stream'..."
    useradd -m -s /bin/bash stream
  fi
  install -d -o stream -g stream /tmp/firefox-profile
  install -d -o stream -g stream /tmp/runtime-stream
}

ensure_xvfb_display() {
  local attempt
  for attempt in 1 2; do
    if pgrep -x Xvfb >/dev/null 2>&1; then
      if wait_for_x_display 5 1; then
        return 0
      fi
      log "Xvfb is present but display :99 is not responding; restarting Xvfb"
      pkill -9 -x Xvfb 2>/dev/null || true
      rm -f /tmp/.X99-lock /tmp/.X11-unix/X99 2>/dev/null || true
      sleep 2
    fi

    nohup Xvfb :99 -screen 0 1920x1080x24 -ac >"$LOG_DIR/xvfb.log" 2>&1 &
    sleep 3
    if wait_for_x_display 20 2; then
      return 0
    fi
  done
  return 1
}

start_firefox() {
  if [ ! -x /opt/firefox/firefox ]; then
    log "Firefox tarball not present; installing..."
    curl -fsSL -L -o /tmp/firefox-latest.tar.xz "https://download.mozilla.org/?product=firefox-latest-ssl&os=linux64&lang=en-US"
    rm -rf /opt/firefox
    tar -xJf /tmp/firefox-latest.tar.xz -C /opt
  fi

  ensure_browser_user

  log "Starting Firefox on Xvfb..."
  local browser_url="${OBS_BROWSER_URL:-http://localhost:10517/stage}"
  local launch_firefox
  launch_firefox() {
    nohup runuser -u stream -- env \
      DISPLAY=:99 \
      XDG_RUNTIME_DIR=/tmp/runtime-stream \
      MOZ_DISABLE_CONTENT_SANDBOX=1 \
      MOZ_WEBRENDER=0 \
      /opt/firefox/firefox --new-instance --profile /tmp/firefox-profile --kiosk "$browser_url" \
      >"$LOG_DIR/firefox.log" 2>&1 &
  }

  if ! ensure_xvfb_display; then
    die "Xvfb display :99 not ready"
  fi

  if ! pgrep -u stream -f '/opt/firefox/firefox --new-instance --profile /tmp/firefox-profile --kiosk' >/dev/null 2>&1; then
    launch_firefox
  else
    log "Firefox already running"
  fi

  local window_id=""
  local tried_restart=0
  for _ in $(seq 1 30); do
    window_id="$(timeout 3s env DISPLAY=:99 xdotool search --all --class Firefox 2>/dev/null | head -1 || true)"
    if [ -n "${window_id:-}" ]; then
      break
    fi
    if [ "$tried_restart" -eq 0 ]; then
      tried_restart=1
      log "Firefox window not found; relaunching browser once"
      pkill -9 -u stream -f '/opt/firefox/firefox --new-instance --profile /tmp/firefox-profile --kiosk' 2>/dev/null || true
      sleep 2
      launch_firefox
    fi
    sleep 2
  done
  if [ -z "${window_id:-}" ]; then
    die "Firefox window not found on DISPLAY=:99"
  fi

  export OBS_CAPTURE_WINDOW_ID="$window_id"
  log "Firefox window id: ${OBS_CAPTURE_WINDOW_ID}"

  python3 - <<'PY'
from pathlib import Path
import json
import os

scene_path = Path("/root/.config/obs-studio/basic/scenes/Untitled.json")
data = json.loads(scene_path.read_text(encoding="utf-8"))
window_id = os.environ["OBS_CAPTURE_WINDOW_ID"]
for source in data.get("sources", []):
    if source.get("name") == os.getenv("OBS_CAPTURE_SOURCE_NAME", "god-browser"):
        source["id"] = os.getenv("OBS_CAPTURE_SOURCE_KIND", "xshm_input")
        source["versioned_id"] = os.getenv("OBS_CAPTURE_SOURCE_KIND", "xshm_input")
        source["settings"] = {
            "capture_window": window_id,
            "CaptureCursor": 0,
            "include_border": 0,
            "exclude_alpha": 0,
            "lock_x": 0,
            "swap_redblue": 0,
            "AdvancedSettings": 0,
            "CropTop": 0,
            "CropLeft": 0,
            "CropRight": 0,
            "CropBottom": 0,
        }
        break
else:
    raise SystemExit("god-browser source not found")
scene_path.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
PY
}

start_nginx() {
  if command -v nginx >/dev/null 2>&1 || [ -d /etc/nginx ]; then
    log "Starting nginx..."
    if [ -d /etc/nginx ]; then
      cat >/etc/nginx/conf.d/god.conf <<'EOF'
server {
  listen 127.0.0.1:10515;
  server_name _;
  location / {
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_pass http://127.0.0.1:8888;
  }
}

server {
  listen 127.0.0.1:10516;
  server_name _;
  location / {
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_pass http://127.0.0.1:8188;
  }
}

server {
  listen 0.0.0.0:10517;
  server_name _;
  location / {
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_pass http://127.0.0.1:3000;
  }
}
EOF
    fi
    nginx -t >/dev/null 2>&1 || die "nginx configuration test failed"
    service nginx start 2>/dev/null || true
    wait_http "http://127.0.0.1:10517/stage" "nginx observer proxy" 60 2 || die "nginx observer proxy not responding"
  fi
}

start_obs() {
  if ! streaming_launch_requested; then
    log "Streaming launch not requested; skipping OBS startup"
    return 0
  fi

  if [ "${SKIP_OBS:-0}" = "1" ]; then
    log "OBS install/start skipped (SKIP_OBS=1)"
    return 0
  fi

  if ! command -v obs >/dev/null 2>&1; then
    die "OBS Studio not installed; cannot start streaming"
  fi

  log "Starting OBS Studio..."
  if ! ensure_xvfb_display; then
    die "Xvfb display :99 not ready"
  fi

  mkdir -p /tmp/xdg-runtime-root
  chmod 700 /tmp/xdg-runtime-root 2>/dev/null || true

  force_obs_keyframes() {
    local profile_dir profile_file
    while IFS= read -r profile_file; do
      [ -f "$profile_file" ] || continue
      python3 - "$profile_file" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8", errors="ignore")

def ensure_section(data: str, section: str, key_values: dict[str, str]) -> str:
    marker = f"[{section}]"
    if marker not in data:
        block = "\n".join([marker, *[f"{k}={v}" for k, v in key_values.items()], ""])
        return data.rstrip() + "\n\n" + block

    lines = data.splitlines()
    out = []
    in_section = False
    seen = set()
    inserted = False
    current_section = None

    for line in lines:
      if line.startswith("[") and line.endswith("]"):
        if in_section and not inserted:
          for k, v in key_values.items():
            if k not in seen:
              out.append(f"{k}={v}")
          inserted = True
        current_section = line[1:-1]
        in_section = current_section == section
        seen = set()
        out.append(line)
        continue

      if in_section:
        if "=" in line and not line.lstrip().startswith(";"):
          key = line.split("=", 1)[0].strip()
          if key in key_values:
            out.append(f"{key}={key_values[key]}")
            seen.add(key)
            continue
      out.append(line)

    if in_section and not inserted:
      for k, v in key_values.items():
        if k not in seen:
          out.append(f"{k}={v}")

    result = "\n".join(out)
    if not result.endswith("\n"):
      result += "\n"
    return result

simple_keys = {
    "keyint_sec": "2",
}
adv_keys = {
    "keyint_sec": "2",
}
updated = ensure_section(text, "SimpleOutput", simple_keys)
updated = ensure_section(updated, "AdvOut", adv_keys)
if updated != text:
    path.write_text(updated, encoding="utf-8")
PY
    done < <(find /root/.config/obs-studio/basic/profiles -name basic.ini -type f 2>/dev/null)
  }

  force_obs_keyframes

  if pgrep -x obs >/dev/null 2>&1; then
    if obs_websocket_ready; then
      log "OBS already running and websocket responsive"
      return 0
    fi
    log "OBS process present but websocket not ready yet; waiting before restart"
    for _ in $(seq 1 30); do
      if obs_websocket_ready; then
        log "OBS websocket became responsive"
        return 0
      fi
      sleep 2
    done
    log "OBS websocket still not responsive; restarting OBS"
    pkill -9 -x obs 2>/dev/null || true
    fuser -k 4444/tcp 2>/dev/null || true
    sleep 5
  fi

  # OBS runs headless under Xvfb. A profile/scene collection still needs to be
  # configured once, but the app itself is now part of the startup stack.
  nohup runuser -u stream -- env DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/runtime-stream QT_QPA_PLATFORM=xcb obs \
    >"$LOG_DIR/obs.log" 2>&1 &
  for _ in $(seq 1 60); do
    if obs_websocket_ready; then
      log "OBS websocket ready"
      return 0
    fi
    sleep 2
  done
  die "OBS failed to expose websocket after startup; see $LOG_DIR/obs.log"
}

start_obs_stream() {
  if ! streaming_launch_requested; then
    log "Streaming launch not requested; skipping OBS stream start"
    return 0
  fi

  if [ "${SKIP_OBS:-0}" = "1" ]; then
    return 0
  fi

  if ! pgrep -x obs >/dev/null 2>&1; then
    die "OBS is not running; cannot start stream"
  fi

  if ! obs_websocket_ready; then
    die "OBS websocket is not responsive; cannot start stream"
  fi

  if ! python3 - <<'PY' >/dev/null 2>&1
from pathlib import Path
import base64
import hashlib
import json
import os
import time

from websocket import create_connection

profile_candidates = [
    Path("/home/stream/.config/obs-studio/basic/profiles/Untitled/basic.ini"),
    Path("/root/.config/obs-studio/basic/profiles/Untitled/basic.ini"),
]
profile = next((p for p in profile_candidates if p.is_file()), None)
if profile is None:
    raise SystemExit("missing OBS profile basic.ini")
text = profile.read_text(encoding="utf-8", errors="ignore")
auth_secret = ""
for line in text.splitlines():
    if line.startswith("AuthSecret="):
        auth_secret = line.split("=", 1)[1].strip()
        break

if not auth_secret:
    raise SystemExit("missing OBS websocket AuthSecret")

ws = create_connection("ws://127.0.0.1:4444", timeout=10)

def call(payload: dict[str, object]) -> dict[str, object]:
    ws.send(json.dumps(payload))
    return json.loads(ws.recv())

auth = call({"request-type": "GetAuthRequired", "message-id": "1"})
if auth.get("authRequired"):
    challenge = str(auth["challenge"])
    ws_auth = base64.b64encode(
        hashlib.sha256((auth_secret + challenge).encode("utf-8")).digest()
    ).decode("utf-8")
    result = call({
        "request-type": "Authenticate",
        "message-id": "2",
        "auth": ws_auth,
    })
    if result.get("status") != "ok":
        raise SystemExit("OBS websocket auth failed")

status = call({"request-type": "GetStreamingStatus", "message-id": "3"})
if status.get("streaming"):
    print("OBS already streaming; restarting stream to clear stale ingest state")
    call({"request-type": "StopStreaming", "message-id": "3b"})
    time.sleep(3)

stream_server = os.getenv("OBS_STREAM_SERVER", "")
stream_key = os.getenv("OBS_STREAM_KEY", "")
if stream_server and stream_key:
    result = call({
        "request-type": "SetStreamSettings",
        "message-id": "4",
        "streamType": "rtmp_custom",
        "settings": {
            "server": stream_server,
            "key": stream_key,
        },
        "save": True,
    })
    if result.get("status") != "ok":
        raise SystemExit("OBS stream settings update failed")

result = call({"request-type": "StartStreaming", "message-id": "5"})
if result.get("status") != "ok":
    raise SystemExit("OBS start streaming failed")

for _ in range(10):
    time.sleep(1)
    status = call({"request-type": "GetStreamingStatus", "message-id": "6"})
    if status.get("streaming"):
        print("OBS streaming started")
        break
else:
    raise SystemExit("OBS streaming did not report true")

ws.close()
PY
  then
    log "OBS stream start completed"
  else
    die "OBS stream start failed"
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
  wait_ready_json "http://localhost:8888/ready" "runtime /ready" 180 3 || die "Runtime not ready"
}

run_core_stage() {
  start_postgres
  start_redis
  start_nats
  start_ipfs
  start_comfyui
  start_ollama
}

run_voice_stage() {
  start_fish
}

run_observer_stage() {
  start_observer
  start_nginx
}

run_streaming_stage() {
  if streaming_launch_requested; then
    log "Preparing streaming capture stack..."
    start_firefox
    start_obs
  else
    log "Streaming launch not requested; skipping Firefox/OBS/browser capture stage"
  fi
}

run_runtime_stage() {
  start_runtime
  start_obs_stream
}

main() {
  local stage="${1:-${BOOT_STAGE:-all}}"
  [ -z "${CUDA_VISIBLE_DEVICES:-}" ] && unset CUDA_VISIBLE_DEVICES
  log "GPU(s): $(nvidia-smi --list-gpus 2>/dev/null | head -2 || echo 'none - CPU mode')"

  ensure_repo
  configure_streaming_mode
  cleanup_stale_ports "$stage"
  case "$stage" in
    core)
      run_core_stage
      return 0
      ;;
    voice)
      run_voice_stage
      return 0
      ;;
    observer)
      run_observer_stage
      return 0
      ;;
    streaming)
      run_streaming_stage
      return 0
      ;;
    runtime)
      run_runtime_stage
      return 0
      ;;
    all)
      log "Running stage: core"
      run_core_stage
      log "Running stage: voice"
      run_voice_stage
      log "Running stage: observer"
      run_observer_stage
      log "Running stage: streaming-prep"
      run_streaming_stage
      log "Running stage: runtime"
      run_runtime_stage
      ;;
    *)
      die "unknown stage '${stage}'; expected all, core, voice, observer, streaming, or runtime"
      ;;
  esac

  PUBLIC_IP=$(curl -sf --max-time 5 ifconfig.me 2>/dev/null || echo "<instance-ip>")
  log ""
  log "All required services are up."
  log "  Commit    $(git -C "$REPO_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)"
  log "  Runtime   http://${PUBLIC_IP}:8888"
  log "  ComfyUI   http://${PUBLIC_IP}:8188"
  log "  Ollama    http://${PUBLIC_IP}:11434"
  log "  fish TTS  http://${PUBLIC_IP}:7860"
  log "  Observer  http://${PUBLIC_IP}:10517/stage"
  log ""
  log "Genesis can run only after the stack is healthy:"
  if [ -n "${CREATOR_GENESIS_TOKEN:-}" ]; then
    log "  curl -s -X POST http://localhost:8888/creator/genesis -H 'Content-Type: application/json' -H \"X-Creator-Token: ${CREATOR_GENESIS_TOKEN}\" -d '{\"confirm\": true}'"
  else
    log "  curl -s -X POST http://localhost:8888/creator/genesis -H 'Content-Type: application/json' -d '{\"confirm\": true}'"
  fi

  python3 - <<PY
import json
import os
import pathlib
import subprocess

def sh(cmd: str) -> str:
    try:
        return subprocess.check_output(cmd, shell=True, text=True).strip()
    except Exception:
        return ""

report = {
    "commit": sh("git -C /workspace/god rev-parse HEAD"),
    "branch": sh("git -C /workspace/god branch --show-current"),
    "env": {
        "STREAMING_MODE": os.getenv("STREAMING_MODE", ""),
        "BROADCAST_ENABLED": os.getenv("BROADCAST_ENABLED", ""),
        "YOUTUBE_ENABLED": os.getenv("YOUTUBE_ENABLED", ""),
        "LOCAL_DEV_MODE": os.getenv("LOCAL_DEV_MODE", ""),
    },
    "pids": {
        "postgres": sh("pgrep -x postgres"),
        "redis": sh("pgrep -x redis-server"),
        "nats": sh("pgrep -x nats-server"),
        "ipfs": sh("pgrep -x ipfs"),
        "ollama": sh("pgrep -x ollama"),
        "comfyui": sh("pgrep -f 'ComfyUI/main.py'"),
        "fish": sh("pgrep -f 'tools/api_server.py'"),
        "observer": sh("pgrep -f 'observer/serve.py'"),
        "runtime": sh("pgrep -f 'uvicorn src.main:app'"),
        "firefox": sh("pgrep -f '/opt/firefox/firefox --new-instance'"),
        "obs": sh("pgrep -x obs"),
    },
    "urls": {
        "runtime": "http://localhost:8888",
        "ready": "http://localhost:8888/ready",
        "comfyui": "http://localhost:8188",
        "ollama": "http://localhost:11434",
        "fish": "http://localhost:7860",
        "observer": "http://localhost:10517/stage",
        "obs_websocket": "ws://127.0.0.1:4444",
    },
    "logs": {
        "dir": "/var/log/god",
        "runtime": "/var/log/god/runtime.log",
        "observer": "/var/log/god/observer.log",
        "obs": "/var/log/god/obs.log",
        "fish": "/var/log/god/fish-speech.log",
    },
}
pathlib.Path("/var/log/god/startup-report.json").write_text(
    json.dumps(report, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY
}

main "$@"
