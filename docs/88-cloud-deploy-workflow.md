# Cloud Deploy Workflow — Vast.ai Instance

How code changes move from local edits to the live cloud runtime.

## Instance Info

| Item | Value |
|------|-------|
| SSH | `ssh -p 10784 root@ssh7.vast.ai` |
| Runtime port (internal) | `8888` |
| nginx proxy (external) | `10515 → 8888` |
| Observer static proxy | `10517 → 3000` |
| Cloudflare tunnel | `https://folks-forming-bizrate-begins.trycloudflare.com` → port `8888` |
| SSH tunnel (local) | `ssh -L 18888:localhost:8888 -N -f -p 10784 root@ssh7.vast.ai` → `http://localhost:18888` |
| Git branch | `feat/twitch-ne-mo-showrunner` |
| Env file | `/workspace/god/.env.local` |
| Runtime log | `/tmp/runtime.log` |

## Dev Loop (standard change)

```
1. Edit files locally  (Windows, this repo at C:\Users\nampa\Documents\god)
2. Run pre-commit:
     bash scripts/validate-local.sh        # uses docker exec god-runtime
3. Git commit & push:
     git add <files>
     git commit -m "..."
     git push origin feat/twitch-ne-mo-showrunner
4. Pull on cloud:
     ssh -p 10784 root@ssh7.vast.ai \
       "cd /workspace/god && git pull origin feat/twitch-ne-mo-showrunner"
5. Restart runtime (kills stale process first):
     ssh -p 10784 root@ssh7.vast.ai \
       "kill -9 \$(pgrep -f 'uvicorn src.main') 2>/dev/null; \
        fuser -k 8888/tcp 2>/dev/null; sleep 2; \
        cd /workspace/god/runtime && \
        source /opt/god-venv/bin/activate && \
        set -a && source /workspace/god/.env.local && set +a && \
        nohup python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8888 \
          > /tmp/runtime.log 2>&1 &"
6. Verify:
     ssh -p 10784 root@ssh7.vast.ai "curl -sf http://localhost:8888/health"
```

> **Important**: always kill by PID (`pgrep -f 'uvicorn src.main'`) before starting a new process. `fuser -k` alone may not reach processes that have already released the port from a previous failed restart attempt.

## Quick Commands

```bash
# SSH into instance
ssh -p 10784 root@ssh7.vast.ai

# Tail runtime log
ssh -p 10784 root@ssh7.vast.ai "tail -f /tmp/runtime.log"

# Check agents + avatar CIDs
ssh -p 10784 root@ssh7.vast.ai \
  "curl -sf http://localhost:8888/agents | python3 -m json.tool | grep -E 'current_name|avatar_cid'"

# Check DB directly
ssh -p 10784 root@ssh7.vast.ai \
  "psql \$DATABASE_URL -c \"SELECT current_name, avatar_cid FROM agents WHERE world_id='god-world-1';\""

# Open the public /one URL on the Vast host
http://ssh7.vast.ai:10517/one

# Open via SSH tunnel (tunnel must be active)
http://localhost:18888/stage
```

## Streaming Mode

The restart script now auto-enables live YouTube and OBS control when the
required credentials are present in `/workspace/god/.env.local`.

Required envs for live mode:

- `STREAMING_MODE=true` to force live mode, or leave `auto` and supply credentials
- `YOUTUBE_CHANNEL_ID`
- `YOUTUBE_ACCESS_TOKEN`
- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_CLIENT_SECRET`
- `OBS_WEBSOCKET_URL`
- `OBS_WEBSOCKET_PASSWORD`
- `OBS_BROWSER_SOURCE` defaults to `god-browser`
- `OBS_BROWSER_URL` defaults to `http://localhost:10517/one`

If those values are missing, the runtime stays up and the stream controls
remain in dry-run / observer-only mode.

## Service Map (Vast.ai native)

| Service | Port | Start cmd |
|---------|------|-----------|
| PostgreSQL | 5432 | `service postgresql start` |
| Redis | 6379 | `service redis-server start` |
| NATS + JetStream | 4222 | `nats-server -p 4222 --jetstream` |
| Ollama | 11434 | `ollama serve` |
| ComfyUI (SDXL) | 8188 | `cd /opt/ComfyUI && python3 main.py --listen 0.0.0.0 --port 8188` |
| fish-speech 2.0 | 7860 | `uv run python /opt/fish-speech/tools/api_server.py --llama-checkpoint-path /opt/fish-speech/checkpoints/s2-pro --decoder-checkpoint-path /opt/fish-speech/checkpoints/s2-pro/codec.pth --listen 0.0.0.0:7860` |
| GOD Runtime | 8888 | see restart cmd above |
| IPFS | 5001 (api) / 8080 (gateway) | `ipfs daemon` |
| nginx | 10515–10517 | `service nginx start` |

Restart all: `bash /workspace/god/scripts/vast-restart-services.sh`
This now blocks until PostgreSQL, Redis, NATS, IPFS, Ollama, ComfyUI,
fish-speech, the observer on `:3000`, nginx, and the runtime are all up.

## Current Progress (as of 2026-06-20)

### Done
- [x] 8 genesis agents created in `god-world-1` with archetypes
- [x] SDXL portraits generated for all 8 agents via ComfyUI — CIDs pinned to IPFS
- [x] `avatar_cid` column added to `agents` table (migration in `db_schema.py`)
- [x] `/agents` API returns `avatar_cid` and `voice_model_cid` per agent
- [x] `/stage` route serves `observer/stage.html` directly from the FastAPI runtime
- [x] `/observer/*` static mount serves the full observer directory
- [x] `/ipfs/{cid}` proxy endpoint fetches from local IPFS node and serves images
- [x] `stage.html` renders portrait images inside avatar orbs when `avatar_cid` is set
- [x] NATS JetStream bootstrapped at startup before agent daemons start
- [x] fish-speech 2.0 API endpoints corrected (`/v1/tts` + reference audio)
- [x] Restart script hardened (kills by PID before rebinding port)

### Pending
- [ ] Voice cloning: confirm fish-speech `/v1/tts` returned voice embeddings for all 8 agents
- [ ] `stage.html` RUNTIME_URL: local observers use `http://localhost:18888`, public uses cloudflare URL — confirm both work
- [ ] Public cloudflare tunnel: URL `folks-forming-bizrate-begins.trycloudflare.com` expires when process dies — needs permanent solution (ngrok auth token or Cloudflare named tunnel)
- [ ] Add cloudflared auto-start to `vast-restart-services.sh`
- [ ] Expression sheet CIDs: confirm expression sheet assets pinned for all 8 agents
- [ ] Observer `/one`: verify the Vite app is live on `:3000` and reachable through nginx at `http://ssh7.vast.ai:10517/one`

## Troubleshooting

**`/stage` returns 404 after code update**: The old uvicorn process is still running. Kill it by PID:
```bash
kill -9 $(pgrep -f 'uvicorn src.main'); sleep 2; fuser -k 8888/tcp
```

**`avatar_cid` missing from `/agents` response**: Runtime running old code or WORLD_ID env var wrong. Check:
```bash
cat /proc/$(pgrep -f 'uvicorn src.main')/environ | tr '\0' '\n' | grep WORLD_ID
```

**Portrait images don't load in browser**: The `/ipfs/{cid}` proxy endpoint requires the local IPFS daemon to be running. Check:
```bash
curl -sf http://localhost:5001/api/v0/id | python3 -m json.tool
```

**Genesis pipeline produces no portraits**: ComfyUI must be healthy. Check:
```bash
curl -sf http://localhost:8188/system_stats
```
