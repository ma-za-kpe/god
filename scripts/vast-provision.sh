#!/usr/bin/env bash
# Provision a Vast.ai GPU instance for the GOD full stack.
# Run this locally (WSL2 or Linux). Outputs the SSH command when ready.
#
# Usage:
#   export VAST_API_KEY=your_key_here
#   bash scripts/vast-provision.sh

set -euo pipefail

: "${VAST_API_KEY:?Set VAST_API_KEY before running}"
# No other API keys needed — Ollama runs on the instance itself.

# ── Config ────────────────────────────────────────────────────────────────────
GPU_NAME="${VAST_GPU:-RTX_4090}"        # 24 GB VRAM — fits fish-speech (6.5 GB) + SDXL (7 GB)
MIN_RAM="${VAST_MIN_RAM:-32}"           # GB — fish-speech needs ~14 GB, rest of stack ~8 GB
MIN_DISK="${VAST_MIN_DISK:-120}"        # GB — models (SDXL 6.5 GB, fish-speech 10.4 GB) + docker layers
MAX_PRICE="${VAST_MAX_PRICE:-0.55}"     # USD/hr — RTX 4090 typically $0.30–0.45
DISK_GB="${VAST_DISK:-120}"

# ── Find pip / python ─────────────────────────────────────────────────────────
if command -v pip3 &>/dev/null; then
  PIP=pip3
elif command -v pip &>/dev/null; then
  PIP=pip
elif command -v python3 &>/dev/null; then
  PIP="python3 -m pip"
elif command -v python &>/dev/null; then
  PIP="python -m pip"
else
  echo "ERROR: Python not found. Install Python 3 first: https://python.org"
  exit 1
fi

# ── Install vastai CLI if missing ─────────────────────────────────────────────
if ! command -v vastai &>/dev/null; then
  echo "Installing vastai CLI..."
  $PIP install --quiet vastai
  # Refresh PATH in case pip installed into a Scripts/ dir not yet on PATH
  export PATH="$PATH:$(python3 -c 'import sysconfig; print(sysconfig.get_path("scripts"))' 2>/dev/null || true)"
fi

vastai set api-key "$VAST_API_KEY"

# ── Find cheapest matching offer ──────────────────────────────────────────────
echo "Searching for ${GPU_NAME} with >=${MIN_RAM}GB RAM, >=${MIN_DISK}GB disk, <\$${MAX_PRICE}/hr..."

OFFER_JSON=$(vastai search offers \
  "gpu_name=${GPU_NAME} num_gpus=1 cpu_ram>=${MIN_RAM} disk_space>=${MIN_DISK} dph_total<${MAX_PRICE} inet_up>100" \
  --raw -o dph_total 2>/dev/null | head -1)

if [ -z "$OFFER_JSON" ]; then
  echo "No offers found for ${GPU_NAME}. Trying RTX_4080..."
  GPU_NAME="RTX_4080"
  OFFER_JSON=$(vastai search offers \
    "gpu_name=${GPU_NAME} num_gpus=1 cpu_ram>=${MIN_RAM} disk_space>=${MIN_DISK} dph_total<${MAX_PRICE} inet_up>100" \
    --raw -o dph_total 2>/dev/null | head -1)
fi

if [ -z "$OFFER_JSON" ]; then
  echo "ERROR: No suitable GPU offers found. Check https://cloud.vast.ai/ manually."
  exit 1
fi

OFFER_ID=$(echo "$OFFER_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
VRAM=$(echo "$OFFER_JSON" | python3 -c "import sys,json; o=json.load(sys.stdin); print(int(o.get('gpu_totalram',0)//1024))")
PRICE=$(echo "$OFFER_JSON" | python3 -c "import sys,json; print(f\"\${json.load(sys.stdin)['dph_total']:.3f}\")")
echo "Best offer: id=${OFFER_ID}  VRAM=${VRAM}GB  price=${PRICE}/hr"

# ── Launch instance ───────────────────────────────────────────────────────────
# Use Ubuntu 22.04 with CUDA pre-installed. Docker will be installed via vast-setup.sh.
echo "Launching instance..."
INSTANCE_JSON=$(vastai create instance "$OFFER_ID" \
  --image "nvidia/cuda:12.4.1-runtime-ubuntu22.04" \
  --disk "$DISK_GB" \
  --ssh \
  --direct \
  --env '-e CUDA_VISIBLE_DEVICES=0' \
  --raw 2>/dev/null)

INSTANCE_ID=$(echo "$INSTANCE_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['new_contract'])")
echo "Instance ${INSTANCE_ID} created. Waiting for SSH to be ready..."

# ── Poll until running ────────────────────────────────────────────────────────
for i in $(seq 1 40); do
  STATUS_JSON=$(vastai show instance "$INSTANCE_ID" --raw 2>/dev/null)
  STATUS=$(echo "$STATUS_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('actual_status',''))" 2>/dev/null || echo "")
  if [ "$STATUS" = "running" ]; then
    SSH_HOST=$(echo "$STATUS_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['ssh_host'])")
    SSH_PORT=$(echo "$STATUS_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['ssh_port'])")
    echo ""
    echo "✓ Instance ${INSTANCE_ID} is running"
    echo ""
    echo "SSH command:"
    echo "  ssh -p ${SSH_PORT} root@${SSH_HOST} -o StrictHostKeyChecking=no"
    echo ""
    echo "Next — copy setup script and run it on the instance:"
    echo "  scp -P ${SSH_PORT} scripts/vast-setup.sh root@${SSH_HOST}:/root/"
    echo "  ssh -p ${SSH_PORT} root@${SSH_HOST} 'bash /root/vast-setup.sh'"
    echo ""
    echo "To stop the instance when done:"
    echo "  vastai destroy instance ${INSTANCE_ID}"
    exit 0
  fi
  echo "  [${i}/40] status=${STATUS:-unknown}, waiting 15s..."
  sleep 15
done

echo "ERROR: Instance did not reach 'running' state after 10 minutes."
vastai show instance "$INSTANCE_ID"
exit 1
