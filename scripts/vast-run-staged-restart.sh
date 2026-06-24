#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/workspace/god"
STAGE_DIR="$REPO_DIR/scripts"

: "${FISH_DEVICE:=cuda}"
: "${FISH_HALF_MODE:=--half}"
export FISH_DEVICE FISH_HALF_MODE

log() { echo "[vast-stage-runner] $*"; }

run_stage() {
  local name="$1"
  local script="$2"
  log "Starting stage ${name}..."
  bash "$script"
  log "Stage ${name} complete"
}

run_stage "core" "$STAGE_DIR/vast-stage-01-core.sh"
run_stage "voice" "$STAGE_DIR/vast-stage-02-voice.sh"
run_stage "observer" "$STAGE_DIR/vast-stage-03-observer.sh"

if [ "${STREAMING_MODE:-auto}" = "true" ] || [ "${STREAMING_MODE:-auto}" = "1" ]; then
  run_stage "streaming" "$STAGE_DIR/vast-stage-04-streaming.sh"
else
  log "Streaming stage skipped (STREAMING_MODE=${STREAMING_MODE:-auto})"
fi

run_stage "runtime" "$STAGE_DIR/vast-stage-05-runtime.sh"
log "All requested stages complete"
