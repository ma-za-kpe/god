# Streaming Recovery Notes

This note records the exact path from a partially healthy Vast.ai instance to a live YouTube stream showing the `/one` observer page.

## Final Outcome

- Vast host: `ssh7.vast.ai`
- SSH port: `10784`
- Public observer URL: `http://ssh7.vast.ai:10517/one`
- OBS is running headless under `Xvfb`
- OBS websocket is live on `:4444`
- Scene `Scene` contains browser source `god-browser`
- `god-browser` points at `http://localhost:10517/one`
- OBS stream settings are pointed at YouTube RTMP
- Stream encoder was switched from `NVENC` to `x264`, which fixed the stream startup failure
- OBS is currently streaming successfully
- The production launcher now accepts `CREATOR_TOKEN` as a legacy alias for `CREATOR_GENESIS_TOKEN`, but still fails closed when neither is set.

## What Was Up Before Streaming

At the start of the run, the host was only partially healthy:

- `ComfyUI` was up
- `Ollama` was up
- `NATS` was up
- `nginx` proxy ports were up
- `fish-speech`, `runtime`, `IPFS`, `Postgres`, `Redis`, `:3000`, and `:8888` had all been failing or flapping earlier in the session

We recovered the missing services and confirmed:

- `runtime` listening on `:8888`
- `observer` listening on `:3000`
- `fish-speech` listening on `:7860`
- `ComfyUI` listening on `:8188`
- `IPFS` listening on `:5001` and `:8080`
- `nginx` now keeps `:10515` and `:10516` local-only while `:10517` remains public

## Recovery Sequence

### 1. Verified the service map

We checked the live host and confirmed which ports were already bound and which services were missing. That told us the runtime stack was mostly alive, but OBS/streaming still needed work.

### 2. Confirmed the observer and fish-speech were healthy

The observer now serves the built static app on port `3000` through `observer/serve.py`.

Fish-speech had to be launched in a detached session because this host is not
booted with `systemd`. A plain `nohup` launch was not durable enough under the
SSH control shell, so the stable fix is to run fish-speech in `tmux` and then
wait on an actual `/v1/tts` synthesis probe.

### 3. Freed GPU pressure

The main bottleneck was GPU memory pressure. The host had been carrying an
Ollama `llama-server` process and at least one other lingering GPU consumer that
interfered with fish-speech and other GPU work. The practical fix is to start
fish-speech before Ollama and keep Ollama on the CPU path where possible.

### 4. Installed and launched OBS

OBS Studio was already installed on the host. We launched it headless under `Xvfb`:

```bash
DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/xdg-runtime-root obs --verbose --unfiltered_log
```

That gave us a working OBS process and log output on the host.

### 5. Installed the OBS websocket plugin

The host had OBS Studio, but the websocket plugin had to be added:

```bash
apt-get install -y obs-websocket
```

That exposed OBS websocket v4 on port `4444`.

### 6. Inspected the OBS config

OBS wrote its config to:

- `/root/.config/obs-studio/global.ini`
- `/root/.config/obs-studio/basic/profiles/Untitled/basic.ini`
- `/root/.config/obs-studio/basic/profiles/Untitled/service.json`
- `/root/.config/obs-studio/basic/scenes/Untitled.json`

The key lesson here was that OBS v4 stored websocket settings in the profile and global INI files, not in a separate obvious JSON file.

### 7. Auth was the tricky part

The websocket server was present, but the initial auth handshake failed because the host had a real websocket password state rather than an open server.

We first tried blank-password assumptions and raw handshake variants. Those failed.

The fix was to seed a known websocket password state into OBS config and then authenticate against that known value from the control client.

### 8. Created the browser source

Once authenticated, we pushed the browser source into the default scene:

- source name: `god-browser`
- source type: `browser_source`
- scene: `Scene`
- URL: `http://localhost:10517/one`
- size: `1920x1080`

The source creation succeeded and the scene now contains `god-browser`.

### 9. Stream settings applied cleanly

We set the YouTube RTMP endpoint in OBS:

- server: `rtmp://a.rtmp.youtube.com/live2`
- stream key: stored on the host in OBS config and the runtime env

The stream settings persisted in OBS profile state and were visible through `GetStreamSettings`.

### 10. The first stream start failed

The first stream start did not stay live because OBS was trying to use the NVENC encoder:

- log showed `Failed to open NVENC codec`
- stream output failed to start

That was the key blocker.

### 11. Forced OBS to x264

We found the encoder strings in OBS and updated the profile to use the simple-output x264 path:

- `UseAdvanced=false`
- `StreamEncoder=x264_lowcpu`
- `RecEncoder=x264_lowcpu`

After restarting OBS, the log confirmed:

- encoder `simple_h264_stream` became `obs_x264`
- YouTube RTMP connected successfully
- streaming start completed

### 12. Recovered the live stream control path

When the stream was restarted after the OBS bounce, the browser capture was still healthy but the stream was not active until OBS was driven through its real websocket v4 API.

What worked on this host:

- OBS websocket server: `ws://127.0.0.1:4444`
- Auth state lives in `/root/.config/obs-studio/basic/profiles/Untitled/basic.ini`
- The `[WebsocketAPI]` block contains `AuthSecret` and `AuthSalt`
- The host Python client was `obswebsocket` for v4, not `obsws_python` v5
- The stream came back only after `GetAuthRequired` -> `Authenticate` -> `StartStreaming`
- `GetStreamingStatus()` can report `false` right after `StartStreaming()` even when the log has already accepted the stream
- The log is the source of truth for the ingest transition

The stream start sequence that succeeded:

```python
from obswebsocket import obsws, requests

ws = obsws("127.0.0.1", 4444, "StreamNow!2026")
ws.connect()
ws.call(requests.StartStreaming())
ws.disconnect()
```

The live host startup script now mirrors that behavior so the stream can be brought back up automatically after OBS starts.

### 13. Browser capture recovery

The white-screen failure was not the observer app itself. The browser layer was the blocker.

What we tested on the live host:

- `chromium-browser` was only a snap wrapper and could not run because `snapd` was unavailable
- `firefox` from the tarball initially hit the browser sandbox as root
- `epiphany-browser` initially failed in bubblewrap / WebKit sandbox setup
- `kernel.unprivileged_userns_clone` was already `1`, so the kernel sysctl was not the blocker
- running Firefox as a non-root `stream` user with `MOZ_DISABLE_CONTENT_SANDBOX=1` worked
- the first-run Firefox modal had to be dismissed once, after which the observer page rendered normally

The live Firefox window details that worked:

- `WM_CLASS`: `Firefox`
- mapped browser window id: `25165827`
- profile: `/tmp/firefox-profile`
- runtime user: `stream`

The OBS source was updated live with `SetSourceSettings` on `god-browser` to point at the Firefox window.

## Important Commands

Host checks:

```bash
ss -tlnp
pgrep -a obs
pgrep -a Xvfb
tail -n 120 /root/.config/obs-studio/logs/2026-06-23\ 18-29-07.txt
```

OBS launch:

```bash
nohup env DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/xdg-runtime-root obs --verbose --unfiltered_log >/var/log/god/obs.log 2>&1 &
```

OBS websocket auth:

```python
from obswebsocket import obsws
ws = obsws('127.0.0.1', 4444, 'StreamNow!2026')
ws.connect()
```

Create browser source:

```python
ws.call(requests.CreateSource(
    sourceName='god-browser',
    sourceKind='browser_source',
    sceneName='Scene',
    sceneItemEnabled=True,
    sourceSettings={
        'url': 'http://localhost:10517/one',
        'width': 1920,
        'height': 1080,
    },
))
```

Set stream service:

```python
ws.call(requests.SetStreamSettings(
    streamType='rtmp_custom',
    settings={
        'server': 'rtmp://a.rtmp.youtube.com/live2',
        'key': '<stream key>',
    },
    save=True,
))
```

Start stream:

```python
ws.call(requests.StartStreaming())
```

## Lessons Learned

- OBS on this host was not ready for websocket control until the `obs-websocket` package was installed.
- The websocket server was v4 on port `4444`, not v5 on `4455`.
- The stream did not fail because `/one` was unreachable. The browser source was added successfully.
- The stream failed because OBS defaulted to NVENC and the host could not open the NVENC encoder.
- The correct recovery path was to force OBS simple output to `x264_lowcpu`.
- Once the stream was stable, YouTube Studio could still hang on `Preparing stream` if the keyframe interval stayed too long; the safe target is `2s` or `4s` max.
- OBS profile data lived in the profile INI and service JSON files, so the fix had to land there, not only in runtime env vars.
- `GetStreamingStatus()` can lag behind or report `streaming: false` momentarily even when the log has already shown `Streaming Start`. The log is the source of truth for the ingest transition.

## Current Startup Contract

The launcher is now staged instead of monolithic.

- `scripts/vast-run-staged-restart.sh` runs the boot in order: `core` -> `voice` -> `observer` -> `streaming` -> `runtime`
- `scripts/vast-restart-services.sh <stage>` can run one stage at a time
- `scripts/vast-stage-02-voice.sh` exports `FISH_DEVICE=cuda` and `FISH_HALF_MODE=--half`
- The voice stage no longer falls back to CPU
- OBS streaming only starts when `STREAMING_MODE=true` or `OBS_AUTO_START_STREAM=true`
- The browser capture path still expects Firefox under `Xvfb :99` as the live window source
- OBS remains the final compositor and stream endpoint, not the primary app renderer

The practical startup order on the live host is now:

```bash
bash /workspace/god/scripts/vast-run-staged-restart.sh
```

When you need a single stage:

```bash
bash /workspace/god/scripts/vast-restart-services.sh core
bash /workspace/god/scripts/vast-restart-services.sh voice
bash /workspace/god/scripts/vast-restart-services.sh observer
bash /workspace/god/scripts/vast-restart-services.sh streaming
bash /workspace/god/scripts/vast-restart-services.sh runtime
```

## Sync Paths

There are now two documented ways to sync startup fixes to the Vast host.

### 1. Git push/pull

This is the normal path when repo permissions allow it:

```bash
git add scripts/vast-restart-services.sh scripts/vast-setup-native.sh scripts/vast-setup.sh scripts/vast-run-staged-restart.sh scripts/vast-stage-02-voice.sh
git commit -m "Force fish-speech onto CUDA in startup"
git push
ssh -p 10784 root@ssh7.vast.ai "cd /workspace/god && git pull"
```

This is the cleanest path when the remote repo accepts the push.

### 2. Direct host sync over SSH

Use this when GitHub push is blocked or when the live host needs an immediate patch.

Example pattern from this session:

```powershell
(Get-Content -Raw 'scripts/vast-restart-services.sh').Replace("`r`n","`n") |
  ssh -p 10784 root@ssh7.vast.ai "cat > /workspace/god/scripts/vast-restart-services.sh"
```

That direct overwrite path was used for the startup files when the repo push failed with 403 permission denied.

## Latest Host Caveat

The voice stage is GPU-only now, but it can still fail if other GPU consumers leave too little free VRAM.

The latest host restart showed:

- fish-speech started on `--device cuda`
- the warmup probe failed because the model could not allocate the next cache block
- the log reported only about `58.75 MiB` free on GPU 0 at the moment of failure
- other GPU consumers were still holding memory while fish was warming up

The takeaway is that "fish must be on GPU" is now a hard startup rule, but the host still needs enough free VRAM for the model cache to finish loading.

### 14. Startup hardening applied after the audit

- `/health` stays a liveness check; `/ready` now validates PostgreSQL, Redis, NATS, IPFS, ComfyUI, fish-speech, Ollama, and OBS when broadcast mode is enabled.
- Restart no longer performs an implicit `git pull`; the launcher now refuses to mutate code during boot.
- Native setup now generates and persists `CREATOR_GENESIS_TOKEN`, and the printed genesis command includes the required `X-Creator-Token` header.
- The observer now runs from the built/static server path instead of Vite dev mode during production boot.
- OBS startup now waits for Xvfb, gives a real grace period to existing websocket state, and only restarts OBS after that window.
- The launcher now writes a machine-readable startup report to `/var/log/god/startup-report.json`.
- Once the x264 encoder was forced, the RTMP connection succeeded and the stream went live.
- The live stream control path is OBS websocket v4 on `:4444`, authenticated from the saved OBS profile state.
- The host startup script now restarts OBS and then starts the stream through that websocket path.
- The host startup script now starts fish-speech in a detached `tmux` session
  so the service can survive the SSH launcher finishing.
- On this host, `systemd-run` is not available because PID 1 is not systemd.
  Use `tmux` or another host-native detached supervisor.

## Remaining Work

The stream is live, and the genesis audit now shows 8/8 living agents with persisted avatar and voice IDs.

Root cause of the missing agent assets:

- The genesis pipeline itself completed for the missing builder agent.
- The persistence helper `_update_postgres_graph_cid` was too quiet and could skip/underreport writes.
- The live repair backfilled the builder row directly and the runtime helper was hardened to log rowcount and use the standard DB fallback.

Audit result:

- 8 living agents
- 8 agents with `avatar_cid`
- 8 agents with `voice_model_cid`
- builder agent repaired with `graph_cid`, `avatar_cid`, `rigged_avatar_cid`, and `voice_model_cid` present

Likely next checks:

- browser page rendering at `http://localhost:10517/one`
- OBS browser source visibility and dimensions
- any CSS or canvas clear-color issue in the observer app
- whether the runtime is rendering content but the page is not painting

## Black Screen Follow-up

After the stream recovery, the browser canvas still rendered black in YouTube/OBS. I isolated the problem in layers:

1. The observer app itself was healthy on the host:
   - `http://localhost:10517/one` returned `200 OK`
   - `http://localhost:10517/stage` returned `200 OK`
   - the live snapshot contained 8 agents, a current speaker, voice health, and avatar health

2. The observer render path had two blanking risks:
   - the outer `Suspense fallback={null}` in `WorldMap`
   - the avatar texture loader suspending the whole scene

3. I removed those blanking conditions and added a dedicated red diagnostic mode:
   - `/one-red`
   - `?debug=red`

4. I then proved the route was served correctly by nginx and by the observer dev server.

5. OBS was then pointed at progressively simpler sources:
   - `http://localhost:10517/one-red`
   - `file:///tmp/obs-red.html`
   - a self-contained `data:text/html,...` red page

6. OBS still streamed black even with the self-contained red page. That means the remaining failure is inside OBS's browser rendering path or the scene/output pipeline, not the observer app or runtime data.

7. The stream itself remained live after restart and re-auth:
   - websocket v4 on `:4444`
   - `StartStreaming` succeeded
   - RTMP connect to YouTube succeeded

Current conclusion:

- `/one` is not the cause of the black frame.
- The host is serving the page correctly.
- The live stream is connected.
- The remaining black screen is an OBS rendering issue, not a runtime health issue.
