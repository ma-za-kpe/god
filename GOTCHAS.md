# GOD Project - Operational Gotchas

Short notes on failure modes that look like bugs but are usually startup, readiness,
or environment issues.

---

## Fish Speech

- The rebuilt image may still take several minutes to load the model weights into
  memory. `health: starting` can be normal during that phase.
- `connection refused` from `build_voice_state` usually means the service is not
  listening on `:7860` yet, not that the runtime is broken.
- The health check can go unhealthy before the model is ready if `start_period`
  is too short.
- The container needs real checkpoints mounted at `/app/checkpoints`. Empty or
  root-owned mounts will fail or stay incomplete.
- The runtime uses `TTS_ENDPOINT` or `VOICE_HEALTH_URL`. If those point at the
  wrong host or port, voice setup will keep degrading.
- Do not prune the old fish-speech image until the rebuilt container is up and
  serving.
- The WebUI path is heavier than the API-server path. If the WebUI keeps
  timing out or hitting memory limits, prefer the API entrypoint for production
  voice synthesis and keep the browser UI for manual testing only.
- The WebUI startup can include extra warm-up work and Gradio overhead. That can
  push the container over memory limits on CPU-only hosts.

## ComfyUI

- A green container does not guarantee image generation is possible yet.
- ComfyUI may answer HTTP before model weights and workflow assets are ready.
- Portrait generation can fail cleanly and leave agents with only default
  `visual_state` fields.

## Genesis / Avatars

- `POST /creator/genesis` always creates the full 8-archetype cast when
  `confirm: true` is set.
- The `count` field is only a hint.
- If avatar generation fails, the agents still exist; the runtime just leaves
  `portrait_cid`, `voice_embedding_cid`, or `voice_state` empty or null.

## Docker

- Docker Desktop can throttle or fail when too many `docker run`, `docker logs`,
  and `docker stats` commands are started at once.
- When that happens, prefer `docker exec` against the already-running container
  instead of launching another one.
- Rebuilds that bake CUDA dependencies into the image are slow once, then much
  faster on later starts.
- The local `scripts/vastai.cmd` wrapper builds `god-vastai-cli:latest` on first
  use and reuses it afterward. The first call is slower; later calls skip the
  `pip install` step entirely.

## Vast.ai — Docker-in-Docker

Vast.ai instances are unprivileged containers. Two capabilities are blocked:

| Blocked | Effect |
|---------|--------|
| `cap_net_admin` | Can't create `docker0` bridge network |
| overlayfs bind-mounts | `docker pull` / `docker build` fail with "operation not permitted" |

`vast-setup.sh` works around both:
- `--bridge=none --iptables=false` — no bridge network needed (host networking instead)
- `--storage-driver=vfs` — vfs copies layers rather than using overlayfs; slower but works
- `docker-compose.vast-hostnet.yml` — forces `network_mode: host` on every service so
  container-name DNS (e.g. `redis:6379`) is replaced with `localhost`

GPU visibility: `nvidia-smi` works on the host but `docker run --gpus all` may not work
until the NVIDIA Container Toolkit is configured for the dockerd-vfs combo. The GOD stack
still runs; Ollama uses the GPU via its own CUDA calls without needing Docker GPU passthrough.

## What to check first

1. `docker compose ps`
2. `docker logs god-fish-speech --tail 40`
3. `curl http://localhost:7860/` or a real readiness endpoint
4. `curl http://localhost:8888/world/snapshot`
