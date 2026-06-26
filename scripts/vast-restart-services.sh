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
import json
from websocket import create_connection

ws = create_connection("ws://127.0.0.1:4444", timeout=6)

def call(t, mid):
    ws.send(json.dumps({"request-type": t, "message-id": str(mid)}))
    for _ in range(20):
        try:
            r = json.loads(ws.recv())
            if r.get("message-id") == str(mid):
                return r
        except Exception:
            break
    return {}

auth = call("GetAuthRequired", 1)
if auth.get("authRequired"):
    raise SystemExit("OBS websocket auth required but no secret configured")

status = call("GetStreamingStatus", 2)
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
    export OBS_CAPTURE_SOURCE_KIND=xcomposite_input
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
  # Unload Ollama models before fish-speech to free VRAM
  if curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
    log "Unloading Ollama models to free VRAM for fish-speech..."
    for model in $(curl -sf http://localhost:11434/api/tags | python3 -c "import sys,json; [print(m['name']) for m in json.load(sys.stdin).get('models',[])]" 2>/dev/null || true); do
      curl -sf -X POST http://localhost:11434/api/generate \
        -H 'Content-Type: application/json' \
        -d "{\"model\":\"$model\",\"keep_alive\":0}" >/dev/null 2>&1 || true
    done
    sleep 2
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

  # Suppress Firefox first-run welcome page and update nags.
  prepare_firefox_profile() {
    if [ "${1:-}" = "clean" ]; then
      rm -rf /tmp/firefox-profile
    fi
    install -d /opt/firefox/distribution 2>/dev/null || true
    cat >/opt/firefox/distribution/policies.json <<'JSON'
{
  "policies": {
    "DisableFirefoxStudies": true,
    "DisableTelemetry": true,
    "DontCheckDefaultBrowser": true,
    "NoDefaultBookmarks": true,
    "OverrideFirstRunPage": "",
    "OverridePostUpdatePage": "",
    "UserMessaging": {
      "ExtensionRecommendations": false,
      "FeatureRecommendations": false,
      "MoreFromMozilla": false,
      "SkipOnboarding": true,
      "UrlbarInterventions": false,
      "WhatsNew": false
    }
  }
}
JSON
    install -d -o stream -g stream /tmp/firefox-profile 2>/dev/null || true
    cat >/tmp/firefox-profile/user.js <<'JS'
user_pref("browser.startup.homepage_override.mstone", "ignore");
user_pref("browser.startup.homepage_override.buildID", "ignore");
user_pref("startup.homepage_welcome_url", "");
user_pref("startup.homepage_welcome_url.additional", "");
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("datareporting.policy.firstRunURL", "");
user_pref("app.update.auto", false);
user_pref("trailhead.firstrun.branches", "nofirstrun");
user_pref("trailhead.firstrun.didSeeAboutWelcome", true);
user_pref("browser.terms.accepted", true);
user_pref("browser.aboutwelcome.enabled", false);
user_pref("browser.newtabpage.enabled", false);
user_pref("toolkit.telemetry.reportingpolicy.firstRun", false);
user_pref("datareporting.healthreport.uploadEnabled", false);
user_pref("datareporting.policy.dataSubmissionEnabled", false);
user_pref("datareporting.policy.dataSubmissionPolicyBypassNotification", true);
user_pref("datareporting.policy.dataSubmissionPolicyAcceptedVersion", 2);
user_pref("browser.uitour.enabled", false);
user_pref("browser.rights.3.shown", true);
user_pref("browser.rights.override", true);
JS
    chown stream:stream /tmp/firefox-profile/user.js 2>/dev/null || true
  }

  log "Starting Firefox on Xvfb..."
  local browser_url="${OBS_BROWSER_URL:-http://localhost:10517/stage}"
  local launch_firefox
  launch_firefox() {
    nohup runuser -u stream -- env \
      DISPLAY=:99 \
      XDG_RUNTIME_DIR=/tmp/runtime-stream \
      MOZ_DISABLE_CONTENT_SANDBOX=1 \
      MOZ_WEBRENDER=0 \
      /opt/firefox/firefox --new-instance --no-remote --profile /tmp/firefox-profile --width 1920 --height 1080 "$browser_url" \
      >"$LOG_DIR/firefox.log" 2>&1 &
  }

  select_firefox_window() {
    timeout 5s env DISPLAY=:99 python3 - <<'PY'
import subprocess

def run(args):
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""

best_id = ""
best_area = 0
ids = run(["xdotool", "search", "--class", "Firefox"]).split()
for window_id in ids:
    name = run(["xdotool", "getwindowname", window_id])
    if name.lower().startswith("close firefox"):
        continue
    geom = run(["xdotool", "getwindowgeometry", "--shell", window_id])
    values = {}
    for line in geom.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    try:
        width = int(values.get("WIDTH", "0"))
        height = int(values.get("HEIGHT", "0"))
    except ValueError:
        continue
    area = width * height
    if width < 640 or height < 360:
        continue
    if area > best_area:
        best_id = window_id
        best_area = area

print(best_id)
PY
  }

  if ! ensure_xvfb_display; then
    die "Xvfb display :99 not ready"
  fi

  if ! pgrep -u stream -f '/opt/firefox/firefox' >/dev/null 2>&1; then
    prepare_firefox_profile clean
    launch_firefox
  else
    log "Firefox already running"
  fi

  local window_id=""
  local tried_restart=0
  for _ in $(seq 1 30); do
    window_id="$(select_firefox_window || true)"
    if [ -n "${window_id:-}" ]; then
      break
    fi
    if [ "$tried_restart" -eq 0 ]; then
      tried_restart=1
      log "Firefox content window not found; relaunching browser once"
      pkill -9 -u stream -f '/opt/firefox/firefox' 2>/dev/null || true
      sleep 2
      prepare_firefox_profile clean
      launch_firefox
    fi
    sleep 2
  done
  if [ -z "${window_id:-}" ]; then
    die "Firefox window not found on DISPLAY=:99"
  fi

  export OBS_CAPTURE_WINDOW_ID="$window_id"
  log "Firefox window id: ${OBS_CAPTURE_WINDOW_ID}"
  timeout 5s env DISPLAY=:99 xdotool windowfocus "$window_id" key Return 2>/dev/null || true

  python3 - <<'PY'
from pathlib import Path
import json
import os

SOURCE_NAME = os.getenv("OBS_CAPTURE_SOURCE_NAME", "god-browser")
SOURCE_KIND = os.getenv("OBS_CAPTURE_SOURCE_KIND", "xshm_input")
window_id = os.environ["OBS_CAPTURE_WINDOW_ID"]

capture_settings = {
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

scene_path = Path("/home/stream/.config/obs-studio/basic/scenes/Untitled.json")
scene_path.parent.mkdir(parents=True, exist_ok=True)

if scene_path.exists():
    data = json.loads(scene_path.read_text(encoding="utf-8"))
    for source in data.get("sources", []):
        if source.get("name") == SOURCE_NAME:
            source["id"] = SOURCE_KIND
            source["versioned_id"] = SOURCE_KIND
            source["settings"] = capture_settings
            break
    else:
        data.setdefault("sources", []).append({
            "id": SOURCE_KIND, "versioned_id": SOURCE_KIND,
            "name": SOURCE_NAME, "settings": capture_settings,
            "mixers": 0, "sync": 0, "flags": 0,
            "volume": 1.0, "enabled": True, "muted": False,
        })
else:
    data = {
        "name": "Untitled",
        "current_scene": "Scene",
        "current_program_scene": "Scene",
        "scene_order": [{"name": "Scene"}],
        "transitions": [],
        "sources": [{
            "id": SOURCE_KIND, "versioned_id": SOURCE_KIND,
            "name": SOURCE_NAME, "settings": capture_settings,
            "mixers": 0, "sync": 0, "flags": 0,
            "volume": 1.0, "enabled": True, "muted": False,
        }],
        "scenes": [{
            "name": "Scene", "id": "scene",
            "settings": {"items": [{
                "name": SOURCE_NAME, "visible": True, "locked": False,
                "pos": {"x": 0.0, "y": 0.0},
                "bounds": {"x": 1920.0, "y": 1080.0},
                "id": 0, "group_id": 0, "bounds_align": 0,
                "crop_top": 0, "crop_right": 0, "crop_left": 0, "crop_bottom": 0,
                "scale_filter": "OBS_SCALE_DISABLE",
                "blend_type": "OBS_BLEND_NORMAL",
                "bounds_type": "OBS_BOUNDS_SCALE_INNER",
                "rot": 0.0,
            }]},
        }],
    }

scene_path.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
print(f"OBS scene written: {SOURCE_NAME} -> window {window_id}")

# If OBS is already running, update the live source via websocket
try:
    import websocket as ws_mod
    import time
    ws2 = ws_mod.create_connection("ws://127.0.0.1:4444", timeout=4)
    _mid = 0
    def _call(t, **kw):
        global _mid; _mid += 1
        p = {"request-type": t, "message-id": str(_mid)}
        p.update(kw)
        ws2.send(json.dumps(p))
        for _ in range(20):
            try:
                r = json.loads(ws2.recv())
                if r.get("message-id") == str(_mid): return r
            except Exception: break
        return {}
    current = _call("GetSourceSettings", sourceName=SOURCE_NAME)
    current_type = current.get("sourceType") or current.get("type") or ""
    if current_type and current_type != SOURCE_KIND:
        Path("/tmp/god-obs-restart-required").write_text(
            f"{SOURCE_NAME}: {current_type} -> {SOURCE_KIND}\n",
            encoding="utf-8",
        )
        print(f"OBS source type mismatch: {current_type} -> {SOURCE_KIND}; restart required")
    else:
        r = _call("SetSourceSettings", sourceName=SOURCE_NAME,
            sourceSettings={"capture_window": window_id, "CaptureCursor": 0})
        print(f"OBS live source update: {r.get('status')}")
    ws2.close()
except Exception as e:
    print(f"OBS websocket not ready yet (will pick up scene file on start): {e}")
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
    done < <(find /home/stream/.config/obs-studio/basic/profiles -name basic.ini -type f 2>/dev/null)
  }

  force_obs_keyframes

  if pgrep -x obs >/dev/null 2>&1; then
    if [ -f /tmp/god-obs-restart-required ]; then
      log "OBS source type changed; restarting OBS"
      rm -f /tmp/god-obs-restart-required
      pkill -9 -x obs 2>/dev/null || true
      fuser -k 4444/tcp 2>/dev/null || true
      sleep 5
    elif obs_websocket_ready; then
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

  if ! python3 - <<'PY'
import json
import os
import time
from websocket import create_connection

ws = create_connection("ws://127.0.0.1:4444", timeout=10)
_mid = 0

def call(t, **kw):
    global _mid
    _mid += 1
    payload = {"request-type": t, "message-id": str(_mid)}
    payload.update(kw)
    ws.send(json.dumps(payload))
    for _ in range(30):
        try:
            r = json.loads(ws.recv())
            if r.get("message-id") == str(_mid):
                return r
        except Exception:
            break
    return {}

auth = call("GetAuthRequired")
if auth.get("authRequired"):
    raise SystemExit("OBS websocket auth required but no secret configured")

status = call("GetStreamingStatus")
if status.get("streaming"):
    print("OBS already streaming; restarting stream to clear stale ingest state")
    call("StopStreaming")
    for _ in range(30):
        time.sleep(1)
        status = call("GetStreamingStatus")
        if not status.get("streaming"):
            break
    else:
        print("OBS remained streaming after stop request; treating active stream as healthy")
        ws.close()
        raise SystemExit(0)

stream_server = os.getenv("OBS_STREAM_SERVER", "")
stream_key = os.getenv("OBS_STREAM_KEY", "")
if not stream_server or not stream_key:
    raise SystemExit("OBS_STREAM_SERVER or OBS_STREAM_KEY not set")

result = call("SetStreamSettings",
    streamType="rtmp_common",
    settings={"server": stream_server, "key": stream_key, "use_auth": False},
    save=True)
if result.get("status") != "ok":
    raise SystemExit("OBS stream settings update failed")

result = call("StartStreaming")
if result.get("status") != "ok":
    status = call("GetStreamingStatus")
    if status.get("streaming"):
        print("OBS is streaming despite StartStreaming response")
        ws.close()
        raise SystemExit(0)
    raise SystemExit(f"OBS start streaming failed: {result}")

for _ in range(30):
    time.sleep(1)
    status = call("GetStreamingStatus")
    if status.get("streaming"):
        print("OBS streaming started")
        break
else:
    raise SystemExit("OBS streaming did not report true after 12s")

ws.close()
PY
  then
    log "OBS stream start completed"
  else
    die "OBS stream start failed"
  fi
}

youtube_go_live() {
  if ! streaming_launch_requested; then
    return 0
  fi

  case "${YOUTUBE_AUTO_GO_LIVE:-false}" in
    1|true|TRUE|yes|YES|on|ON) ;;
    *)
      log "YouTube auto go-live disabled; OBS is streaming RTMP but YouTube may still need manual Go Live/Auto-start"
      return 0
      ;;
  esac

  if [ -z "${YOUTUBE_BROADCAST_ID:-}" ]; then
    die "YOUTUBE_AUTO_GO_LIVE=true but YOUTUBE_BROADCAST_ID is not set"
  fi

  cd "$REPO_DIR/runtime"
  source /opt/god-venv/bin/activate
  local result=""
  if result="$(python3 - <<'PY'
import asyncio
import json

from src.youtube.api import ensure_broadcast_live


async def main() -> int:
    result = await ensure_broadcast_live()
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("ok") else 1


raise SystemExit(asyncio.run(main()))
PY
  )"; then
    log "YouTube go-live transition completed: ${result}"
  else
    die "YouTube go-live transition failed: ${result:-<no details>}"
  fi
  cd "$REPO_DIR"
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
  youtube_go_live
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
