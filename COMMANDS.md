# GOD Project — Command Reference

Commands used during development, debugging, and operations of this project.

---

## Agents & World

```bash
# Check all living agents
curl -s http://localhost:8888/agents

# Check world snapshot (scene, speaker, stats)
curl -s http://localhost:8888/world/snapshot

# Spawn the initial cast (count is a hint; genesis always produces 8 archetypes)
curl -s -X POST http://localhost:8888/creator/genesis \
  -H "Content-Type: application/json" \
  -d '{"count": 6, "confirm": true}'

# Full genesis with portrait + voice (do this AFTER fish-speech goes healthy)
# Step 1: wipe the current world
curl -s -X DELETE http://localhost:8888/world
# Step 2: spawn fresh agents — pipeline will now attempt ComfyUI portrait + Fish Speech voice
curl -s -X POST http://localhost:8888/creator/genesis \
  -H "Content-Type: application/json" \
  -d '{"count": 6, "confirm": true}'

# NeMo director status
curl -s http://localhost:8888/nemo/status

# Current NeMo directive (scene, speaker, guardrail_status)
curl -s http://localhost:8888/nemo/director

# Broadcast surface state (scene, captions, overlay, commands)
curl -s http://localhost:8888/broadcast/state

# Verify showrunner headline shows display names (not soul_ids)
curl -s http://localhost:8888/world/snapshot | python3 -c \
  "import json,sys; s=json.load(sys.stdin)['showrunner']; print('speaker:', s['speaker']); print('headline:', s['headline'])"
```

```powershell
# Same check in PowerShell
$snap = Invoke-RestMethod -Uri "http://localhost:8888/world/snapshot"
Write-Host "headline:" $snap.showrunner.headline
Write-Host "speaker: " $snap.showrunner.speaker
Write-Host "cue[0]:  " $snap.showrunner.cues[0].agent_name
```

---

## Docker

```bash
# Bring up all core services (runtime, db, redis, nats, anvil, ipfs)
docker compose up -d

# Bring up all services INCLUDING the observer (:3000)
docker compose --profile observer up -d

# Bring up fish-speech ALONE for voice cloning (needs ~14 GB RAM — stop other containers first)
# fish-speech is on its own profile; it OOMs Docker when run alongside the full stack on 16 GB RAM
docker compose --profile fish-speech up -d fish-speech

# Stop fish-speech when done to free memory for the rest of the stack
docker compose stop fish-speech

# Pull images for heavy services before starting (avoids timeout on first run)
docker compose pull comfyui

# Build the fish-speech image (bakes CUDA deps in so they don't re-download every boot)
# Run this once; after that 'docker compose up' starts instantly
docker compose build fish-speech

# Check status of all containers (name, health, ports)
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Tail logs for a specific service
docker logs god-fish-speech --tail 40
docker logs god-comfyui --tail 20
docker logs god-runtime --tail 40

# Follow logs live for a service
docker logs -f god-runtime

# Stop all containers
docker compose down

# Stop and wipe volumes (destructive — resets db, redis, ipfs state)
docker compose down -v
```

---

## CI / Pre-commit

```bash
# Run all pre-commit hooks locally before pushing
python3 -m pre_commit run --all-files

# Watch a GitHub Actions run after push
gh run watch

# Security audit before push
bash scripts/security-audit.sh
```

---

## GitHub (gh CLI)

```bash
# List open issues
gh issue list

# Create an issue with a label
gh issue create --title "Title" --body "Body" --label "stub"

# Add a comment to an issue
gh issue comment <number> --body "Comment text"

# View a specific issue
gh issue view <number>

# List recent workflow runs
gh run list --limit 10
```

---

## Runtime (Python / tests)

```bash
# Run all tests inside the runtime container
docker exec god-runtime pytest

# Run tests locally (from runtime/ directory)
cd runtime && pytest

# Run a specific test file
pytest tests/test_broadcast_surface.py -v
```

---

## Health Checks (PowerShell)

```powershell
# Parse world snapshot stats
$snap = Invoke-RestMethod -Uri "http://localhost:8888/world/snapshot"
Write-Host "living:" $snap.stats.living_count
Write-Host "scene:"  $snap.showrunner.scene
Write-Host "speaker:" $snap.showrunner.speaker

# Quick agent count
(Invoke-RestMethod -Uri "http://localhost:8888/agents").count
```

---

## Observer / Stage

```
# Stage broadcast UI
http://localhost:3000/stage

# Maku operator panel
http://localhost:3000/maku

# ComfyUI image generation UI
http://localhost:8188

# Fish Speech TTS UI
http://localhost:8090

# Runtime OpenAPI / Swagger
http://localhost:8888/docs
```

---

## Vast.ai Deployment

> **How the CLI works**: `scripts\vastai.cmd` is a thin Docker wrapper around the
> `vastai` script in the repo root. It builds `god-vastai-cli:latest` once
> (see `scripts/vastai-cli.Dockerfile`) and reuses it on every call — no local Python
> or pip install needed. API key is persisted in `%USERPROFILE%\.config\vastai\vast_api_key`.

### One-time setup

```bash
# 1. Download the Vast.ai CLI script into the repo root.
curl -sL https://raw.githubusercontent.com/vast-ai/vast-cli/master/vast.py -o vastai

# 2. Build the helper image (bakes `requests` in; skipped automatically after first build).
docker build -t god-vastai-cli:latest -f scripts/vastai-cli.Dockerfile .

# 3. Persist your API key — get it from https://cloud.vast.ai/ → Account → API Key.
#    After this, every vastai.cmd call picks it up automatically.
scripts\vastai.cmd set api-key YOUR_KEY

# 4. Register your SSH public key with your Vast account.
#    The wrapper mounts %USERPROFILE%\.ssh into /root/.ssh, so use the container path.
scripts\vastai.cmd create ssh-key /root/.ssh/id_ed25519.pub -y

# 5. Confirm the key is registered.
scripts\vastai.cmd show ssh-keys
```

### Search for available GPU instances

```bash
# List cheapest RTX 4090 offers sorted by price (dph_total = dollars per hour).
# Filters: 1 GPU, ≥32 GB RAM, ≥120 GB disk, <$0.55/hr, ≥100 Mbit/s upload.
scripts\vastai.cmd search offers \
  "gpu_name=RTX_4090 num_gpus=1 cpu_ram>=32 disk_space>=120 dph_total<0.55 inet_up>100" \
  -o dph_total

# Fall back to RTX 4080 if no 4090 is within budget:
scripts\vastai.cmd search offers \
  "gpu_name=RTX_4080 num_gpus=1 cpu_ram>=32 disk_space>=120 dph_total<0.45 inet_up>100" \
  -o dph_total
```

### Launch an instance

```bash
# Create an on-demand instance from an offer ID returned by the search above.
# --image  : Ubuntu 22.04 + CUDA 12.4 pre-installed; Docker added by vast-setup.sh.
# --disk   : 120 GB min — SDXL (6.5 GB) + fish-speech (10.4 GB) + docker layers.
# --ssh    : enables SSH access.
# --direct : direct connection, no relay hop.
scripts\vastai.cmd create instance OFFER_ID \
  --image 'nvidia/cuda:12.4.1-runtime-ubuntu22.04' \
  --disk 120 \
  --ssh \
  --direct \
  --env '-e CUDA_VISIBLE_DEVICES=0'
# Returns JSON with `new_contract` — that is your INSTANCE_ID.
```

### Check and manage instances

```bash
# List all your instances (status, SSH host:port, price).
scripts\vastai.cmd show instances

# Check a specific instance — wait for status to change from loading → running.
scripts\vastai.cmd show instance INSTANCE_ID

# Get the SSH URL in one shot (host:port formatted for direct use).
scripts\vastai.cmd ssh-url INSTANCE_ID

# Attach your SSH key to a running instance if it was registered after launch.
# IMPORTANT: pass the key *content* as a string — the vastai CLI interprets
# the argument as a literal string, NOT a file path to read.
PUB=$(cat ~/.ssh/id_ed25519.pub)
docker run --rm \
  -v "$(pwd)/vastai:/vastai" \
  -v "$HOME/.config/vastai:/root/.config/vastai" \
  god-vastai-cli:latest \
  python /vastai attach ssh INSTANCE_ID "$PUB"

# Destroy an instance when done — billing stops immediately.
scripts\vastai.cmd destroy instance INSTANCE_ID
```

### Deploy the GOD stack

> **Note**: Standard Vast.ai container instances lack `CAP_SYS_ADMIN`, making
> Docker-in-Docker impossible (overlayfs mounts blocked, user-namespace creation blocked).
> Use `vast-setup-native.sh` which runs all services directly on the host — no Docker needed.

```bash
# 1. Copy the native setup script to the instance.
#    SSH_HOST and SSH_PORT come from `show instances` (e.g. ssh8.vast.ai 35402).
scp -P SSH_PORT -i ~/.ssh/id_ed25519 scripts/vast-setup-native.sh root@SSH_HOST:/root/

# 2. Launch in the background — survives disconnects.
#    Installs Postgres/Redis/NATS/Ollama/ComfyUI/fish-speech natively (~30 min total).
ssh -p SSH_PORT -i ~/.ssh/id_ed25519 root@SSH_HOST \
  'nohup bash /root/vast-setup-native.sh > /root/setup-native.log 2>&1 & echo "PID=$!"'

# 3. Follow the setup log in real time (Ctrl-C to detach without killing setup).
ssh -p SSH_PORT -i ~/.ssh/id_ed25519 root@SSH_HOST 'tail -f /root/setup-native.log'

# 4. Run genesis once runtime is healthy.
#    INSTANCE_IP is the public IP printed at the end of setup-native.log.
curl -s -X POST http://INSTANCE_IP:8888/creator/genesis \
  -H 'Content-Type: application/json' \
  -d '{"confirm": true}' | python3 -m json.tool
```

#### Setup overrides (env vars)

```bash
# Skip ComfyUI + fish-speech for a fast LLM-only deploy (~5 min):
ssh -p SSH_PORT -i ~/.ssh/id_ed25519 root@SSH_HOST \
  'SKIP_FISH=1 SKIP_COMFYUI=1 nohup bash /root/vast-setup-native.sh > /root/setup-native.log 2>&1 &'

# Use a smaller model to save VRAM:
ssh -p SSH_PORT -i ~/.ssh/id_ed25519 root@SSH_HOST \
  'OLLAMA_MODEL=llama3.2:3b nohup bash /root/vast-setup-native.sh > /root/setup-native.log 2>&1 &'

# Check service health after setup:
ssh -p SSH_PORT -i ~/.ssh/id_ed25519 root@SSH_HOST 'bash -s' << 'EOF'
curl -sf http://localhost:8888/health && echo "runtime OK"
curl -sf http://localhost:11434/api/tags && echo "ollama OK"
curl -sf http://localhost:8188/ && echo "comfyui OK"
curl -sf http://localhost:7860/ && echo "fish-speech OK"
redis-cli ping
EOF
```

### Automated provisioning scripts

```bash
# Bash (WSL2 / Linux): searches for the cheapest offer, launches, and polls until SSH is ready.
export VAST_API_KEY="YOUR_KEY"
bash scripts/vast-provision.sh
```

```powershell
# PowerShell (Windows): same flow using Invoke-RestMethod — no Python or Docker needed.
$env:VAST_API_KEY = "YOUR_KEY"
.\scripts\vast-provision.ps1
```

### Vast.ai URLs

```
Console / billing:   https://cloud.vast.ai/
Instances:           https://cloud.vast.ai/instances/
API key:             https://cloud.vast.ai/account/
```

---

## Notes

- **Observer** requires `--profile observer` — it is not started by `docker compose up -d` alone.
- **Fish Speech** needs `/app/checkpoints` mounted with the `fish-speech-1.5` model weights, and downloads ~1.4 GB of CUDA packages on first boot.
- **Fish Speech API mode** is lighter than the WebUI path. Use the API server
  entrypoint when you need voice synthesis without the Gradio/browser overhead.
- **ComfyUI** uses a Syncthing sidecar to sync model weights; it shows `(healthy)` once the HTTP port is up, but image generation requires weights + GPU.
- **Genesis**: `POST /creator/genesis {"confirm": true}` always spawns the full 8-archetype cast regardless of the `count` hint.
- **x402 payments** are mocked by default (`MOCK_X402_PAYMENTS=true` in `.env.local`).
- See [GOTCHAS.md](./GOTCHAS.md) for the common startup and readiness traps.
