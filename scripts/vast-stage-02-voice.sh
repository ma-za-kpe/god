#!/usr/bin/env bash
set -euo pipefail

: "${FISH_DEVICE:=cuda}"
: "${FISH_HALF_MODE:=--half}"
export FISH_DEVICE FISH_HALF_MODE

exec bash /workspace/god/scripts/vast-restart-services.sh voice
