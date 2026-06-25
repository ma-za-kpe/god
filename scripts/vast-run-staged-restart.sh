#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/workspace/god"
START_SCRIPT="$REPO_DIR/scripts/vast-restart-services.sh"

: "${FISH_DEVICE:=cuda}"
: "${FISH_HALF_MODE:=--half}"
export FISH_DEVICE FISH_HALF_MODE

log() { echo "[vast-stage-runner] $*"; }

log "Starting one-stop startup: core -> voice -> observer -> streaming-prep -> runtime -> go-live"
exec bash "$START_SCRIPT" all
