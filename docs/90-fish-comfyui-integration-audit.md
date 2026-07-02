# Fish Speech + ComfyUI Integration Audit

Date: 2026-06-26
Branch: `feat/twitch-ne-mo-showrunner`
Scope: runtime integration between ComfyUI image generation and Fish Speech voice synthesis/cloning.
Current Status: Foundation is partially implemented. Live path is voice plus basic avatar state only. Procedural life, real-time embodiment, and GPU queueing are the immediate blockers for "alive on Twitch".

This is the working audit document for this session. Keep additions factual and cite either:

- Local code paths with line numbers.
- External primary sources or project sources.
- Explicit runtime observations from commands/tests.

## Evidence Policy

- "Confirmed" means directly observed in this repo or in cited upstream documentation.
- "Inference" means a conclusion drawn from code behavior. Mark it as inference.
- "Risk" means plausible failure mode supported by code/config evidence, but not necessarily reproduced.
- Avoid unsourced claims.

## External References

- ComfyUI upstream API example shows API-format workflow JSON being submitted to `http://127.0.0.1:8188/prompt` with a JSON envelope containing `"prompt"`: <https://github.com/Comfy-Org/ComfyUI/blob/master/script_examples/basic_api_example.py>
- Fish Speech upstream repository describes the project as open-source TTS: <https://github.com/fishaudio/fish-speech>
- Fish Audio S2 technical report states Fish Audio S2 is an open-source TTS system with multi-speaker, multi-turn generation and instruction-following control; code and weights are linked from the paper: <https://arxiv.org/abs/2603.08823>
- Fish Speech paper states Fish-Speech is a TTS framework using LLMs and supports voice cloning; implementation linked from the paper: <https://arxiv.org/abs/2411.01156>

## Current Architecture

Confirmed: Fish Speech and ComfyUI do not directly call each other. They are coordinated by the runtime's avatar genesis and live voice layers.

- ComfyUI endpoint resolution is in `runtime/src/avatar/genesis_pipeline.py:74-81`.
- Fish/TTS endpoint resolution is in `runtime/src/avatar/genesis_pipeline.py:82-89`.
- The genesis pipeline instantiates both sidecar clients at `runtime/src/avatar/genesis_pipeline.py:173-174`.
- ComfyUI work is handled by `PortraitGenerator` in `runtime/src/avatar/portrait_generator.py:27-39`.
- Fish Speech work is handled by `VoiceCloner` in `runtime/src/avatar/voice_cloner.py:27-38`.
- Live voice synthesis is handled by `runtime/src/voice/engine.py:586-625`.

Inference: the integration model is "parallel media capabilities sharing agent identity", not "Comfy feeds Fish" or "Fish feeds Comfy".

## Genesis Flow

Confirmed sequence from `runtime/src/avatar/genesis_pipeline.py`:

1. Validate archetype config during pipeline construction at lines `73-89`.
2. Construct `PortraitGenerator` and `VoiceCloner` at lines `173-174`.
3. Unload Ollama before ComfyUI work at lines `180-182`, implemented at lines `408-422`.
4. Check ComfyUI health and generate a portrait at lines `184-187`.
5. Pin portrait bytes to IPFS and update identity fields at lines `189-215`.
6. Generate expression variants from the portrait at lines `216-220`.
7. Pin expression images and expression manifest at lines `221-258`.
8. Retry Fish health check up to four times, sleeping fifteen seconds between attempts, at lines `266-271`.
9. Clone/validate voice with Fish at lines `272-280`.
10. Pin voice bytes and update `identity.voice_model_cid` at lines `281-287`.
11. Persist identity to IPFS/Postgres if any assets were produced at lines `313-341`.

Important implementation detail:

- `identity.rigged_avatar_cid` is set to the same CID as the static portrait at `runtime/src/avatar/genesis_pipeline.py:201-204`.
- This means "rigged avatar" currently means "same image asset reused", not an actually rigged avatar. Confirmed by code; this is not a runtime observation.

## ComfyUI Implementation

Confirmed:

- `PortraitGenerator.health_check()` calls `{COMFYUI_ENDPOINT}/system_stats` and returns true for any 2xx response: `runtime/src/avatar/portrait_generator.py:41-49`.
- Default portrait workflow template is `flux_portrait.json`: `runtime/src/avatar/portrait_generator.py:38`.
- Default expression workflow template is `flux_expression.json`: `runtime/src/avatar/portrait_generator.py:39`.
- Portrait generation replaces prompt tokens including style prompt, negative prompt, seed, width, height, and batch size: `runtime/src/avatar/portrait_generator.py:64-74`.
- Expression generation loops through requested expressions and submits one workflow per expression: `runtime/src/avatar/portrait_generator.py:91-112`.
- Workflow submission strips `_meta`, then posts `{"prompt": workflow}` to `/prompt`: `runtime/src/avatar/portrait_generator.py:115-123`.
- It polls `/history/{prompt_id}` until timeout: `runtime/src/avatar/portrait_generator.py:136-145`.
- It fetches generated images through `/view`: `runtime/src/avatar/portrait_generator.py:148-165`.
- If Comfy history has empty outputs, it attempts local disk fallback from `/opt/ComfyUI/output/*.png`: `runtime/src/avatar/portrait_generator.py:166-177`.

External confirmation:

- The upstream ComfyUI API example uses the same basic pattern of API JSON workflow plus POST to `/prompt` with a `"prompt"` payload envelope.

Risks:

- `system_stats` is a shallow health check. It proves HTTP service availability, not model availability, custom-node availability, or workflow validity.
- The default Flux templates require custom nodes/models according to their `_meta.required_custom_nodes` fields in `runtime/workflows/flux_portrait.json` and `runtime/workflows/flux_expression.json`.
- The Docker Compose ComfyUI service only starts `ghcr.io/ai-dock/comfyui:latest` and mounts model/input/output volumes; this file does not show installation of the required custom nodes: `docker-compose.yml:309-337`.
- The disk fallback path `/opt/ComfyUI/output` assumes runtime and ComfyUI share a filesystem. Docker Compose mounts ComfyUI output into the ComfyUI container volume, not into the runtime container: `docker-compose.yml:316-319`. Risk: stale or inaccessible fallback output.

## Fish Speech Implementation

Confirmed:

- Fish health check calls `{TTS_ENDPOINT}/v1/health`: `runtime/src/avatar/voice_cloner.py:40-53`.
- `clone_voice()` requires endpoint health, archetype config, and a readable seed utterance: `runtime/src/avatar/voice_cloner.py:55-76`.
- `_submit_clone()` posts to `/v1/tts` using inline base64 reference audio: `runtime/src/avatar/voice_cloner.py:111-130`.
- `_submit_clone()` returns the seed utterance bytes as the "embedding": `runtime/src/avatar/voice_cloner.py:112-130`.
- `_submit_verification_sample()` posts another `/v1/tts` call with the same inline reference audio and returns response bytes: `runtime/src/avatar/voice_cloner.py:132-151`.
- `voice_params` are derived from archetype config at `runtime/src/avatar/voice_cloner.py:100-109`.

Important implementation detail:

- The code comments state Fish Speech 2.0 has no persistent embedding step and the seed WAV is used as voice identity for future `/v1/tts` calls: `runtime/src/avatar/voice_cloner.py:111-130`.
- Therefore, `voice_embedding_cid` / `voice_model_cid` currently stores reference audio bytes, not a model embedding.

Risks:

- Naming risk: fields named `voice_embedding_cid` and `voice_model_cid` imply model/embedding semantics, while code stores the seed WAV.
- `voice_params` and `prosody_map` are derived but not included in the `/v1/tts` payloads at `runtime/src/avatar/voice_cloner.py:118-125` or `runtime/src/avatar/voice_cloner.py:140-147`.
- `detect_prosody_support()` exists at `runtime/src/avatar/voice_cloner.py:83-98` but no call site was found in this audit.

## Live Voice Runtime

Confirmed:

- `_reference_audio_for_agent()` reads `agent.voice_model_cid`, fetches bytes through IPFS `/api/v0/cat`, and returns response content: `runtime/src/voice/engine.py:267-282`.
- If no agent-specific reference is found, live voice falls back to `philosopher.wav`: `runtime/src/voice/engine.py:586-595`.
- Live synthesis posts `plan.line` plus inline base64 reference audio to `{endpoint}/v1/tts`: `runtime/src/voice/engine.py:598-625`.
- The voice engine unloads Ollama before Fish synthesis to free GPU bandwidth: `runtime/src/voice/engine.py:611-622`.
- Successful responses are cached by `utterance_id` and audio bytes are stored in `_audio_cache`: `runtime/src/voice/engine.py:624-655`.

Inference:

- The live voice path depends on genesis having pinned valid reference audio to `voice_model_cid`. If genesis voice failed or IPFS cat fails, the system degrades to philosopher reference audio.

## Avatar Runtime Use

Confirmed:

- Avatar state chooses the active expression from override/current expression logic: `runtime/src/avatar/engine.py:184-193`.
- Avatar asset fallback order includes `avatar_cid`, `rigged_avatar_cid`, then `voice_model_cid`: `runtime/src/avatar/engine.py:199-216`.
- `rigged_avatar_cid` defaults to active agent `rigged_avatar_cid` or `avatar_asset`: `runtime/src/avatar/engine.py:218-225`.
- Mouth openness is derived from speaking/expression state, not from Fish phoneme timing: `runtime/src/avatar/engine.py:264-288`.

Risks:

- Because `avatar_asset` can fall back to `voice_model_cid`, a voice reference CID could be exposed as an avatar asset if image fields are missing.
- There is no confirmed code path that uses the pinned expression manifest CID to retrieve and display expression images. The runtime uses expression labels/states, but this audit did not find a direct expression-CID lookup in avatar rendering.

## Deployment / Configuration

Confirmed:

- `.env.example` sets `COMFYUI_ENDPOINT=http://comfyui:8188` and `TTS_ENDPOINT=http://fish-speech:7860`: `.env.example:160-164`.
- Docker Compose ComfyUI binds host `127.0.0.1:8188` to container `8188`: `docker-compose.yml:320-321`.
- Docker Compose Fish binds host `127.0.0.1:8090` to container `7860`: `docker-compose.yml:352-353`.
- Docker Compose Fish entrypoint uses `--device cpu --half`: `docker-compose.yml:347`.
- Vast restart script requires Fish to run on CUDA and exits if `FISH_DEVICE` is not `cuda`: `scripts/vast-restart-services.sh:376-382`.
- Vast restart script starts ComfyUI before Ollama in core stage: `scripts/vast-restart-services.sh:975-980`.
- Vast restart script starts Fish in the voice stage: `scripts/vast-restart-services.sh:982-984`.
- Vast restart script unloads Ollama models before starting Fish: `scripts/vast-restart-services.sh:393-402`.

### Current Vast.ai Operator Config

Confirmed from operator command supplied on 2026-06-26:

```bash
ssh -p 18516 root@209.137.198.14 -L 8080:localhost:8080
```

- SSH target: `root@209.137.198.14`.
- SSH port: `18516`.
- Local tunnel: local `localhost:8080` forwards to Vast host `localhost:8080`.
- Operator browser/API entrypoint after connecting: `http://localhost:8080`.
- Vast host-network compose config keeps runtime-side service URLs on host-local endpoints: `docker-compose.vast-hostnet.yml:17-29`.

Inference:

- This is an operator-access tunnel, not the service-to-service runtime config.
- Runtime-side service URLs on the Vast host should stay host-local when using host networking:
  - `COMFYUI_ENDPOINT=http://localhost:8188`
  - `TTS_ENDPOINT=http://localhost:7860`
  - `VOICE_HEALTH_URL=http://localhost:7860`
  - `AVATAR_HEALTH_URL=http://localhost:8188`
  - `OLLAMA_BASE_URL=http://localhost:11434`
  - `NATS_URL=nats://localhost:4222`
  - `REDIS_URL=redis://localhost:6379`
  - `IPFS_API=http://localhost:5001`
  - `DATABASE_URL=postgresql://god:${POSTGRES_PASSWORD}@localhost:5432/god`

Operational notes:

- The tunnel only exposes remote port `8080` locally. It does not directly expose runtime `8888`, ComfyUI `8188`, Fish `7860`, Ollama `11434`, Postgres `5432`, Redis `6379`, NATS `4222`, or IPFS API `5001`.
- If port `8080` is an nginx/operator gateway, it should proxy only the surfaces intended for remote operation and leave GPU, model, database, and queue services bound to remote localhost.
- Do not publish `8188`, `7860`, `11434`, `5432`, `6379`, `4222`, or `5001` directly on the public Vast interface.
- For direct diagnostics, use additional short-lived SSH tunnels instead of opening host firewall ports.

### Vast.ai Instance Profile Decision

Date added: 2026-06-26

Confirmed from repo:

- `scripts/vast-provision.sh` defaults to `VAST_GPU=RTX_4090`, `VAST_MIN_RAM=32`, `VAST_MIN_DISK=120`, and `VAST_DISK=120`: `scripts/vast-provision.sh:15-18`.
- The script comments say RTX 4090 has 24 GB VRAM and fits fish-speech plus SDXL: `scripts/vast-provision.sh:15`.
- If no RTX 4090 offer is found, the provision script falls back to RTX 4080: `scripts/vast-provision.sh:53-57`.
- `docker-compose.vast.yml` states Fish is forced to CUDA and RTX 4090 handles Fish Speech easily: `docker-compose.vast.yml:4-7`.
- `docker-compose.vast.yml` sets SDXL templates for runtime avatar genesis, not Flux/LTX/Wan templates: `docker-compose.vast.yml:58-59`.
- ComfyUI-LTXVideo upstream lists 32 GB+ VRAM and 100 GB+ free disk as prerequisites; this exceeds the current RTX 4090 24 GB baseline for comfortable LTX-2.3 use.
- Wan2.1 upstream documents T2V-1.3B at 8.19 GB VRAM and about 4 minutes for a 5-second 480P clip on RTX 4090 without optimization.

Decision:

- Do not upgrade the Vast instance just to begin the immediate avatar-life work.
- The current RTX 4090-class profile is acceptable for:
  - YouTube-first live proof;
  - Fish voice;
  - procedural life signals;
  - OBS/browser observer work;
  - SDXL portrait generation;
  - manual one-off LivePortrait/MuseTalk feasibility tests if run serially.
- Upgrade before claiming production LTX/Wan background generation, because the current profile is below the documented comfortable LTX-2.3 VRAM recommendation and lacks queue protection today.

Recommended Vast profiles:

| Phase | Suggested Vast class | Minimum target | Why |
| --- | --- | --- | --- |
| Foundation / YouTube proof | RTX 4090-class, 1 GPU | 24 GB VRAM, 64 GB RAM preferred, 200 GB disk preferred | Fish + procedural life + observer + SDXL; no live LTX/Wan |
| Real-time embodiment eval | RTX 4090/5090-class, 1 GPU | 24-32 GB VRAM, 64 GB RAM, 200 GB disk | Benchmark LivePortrait/MuseTalk/Wav2Lip sidecar candidates serially |
| LTX asset factory | 48 GB VRAM class preferred | 48 GB VRAM, 64-128 GB RAM, 300 GB disk | LTX-2.3 docs recommend 32 GB+ VRAM; headroom avoids starving Fish |
| Wan cinematic/offline | 48-80 GB VRAM class preferred | 48 GB+ VRAM, 128 GB RAM, 300-500 GB disk | Quality clips are offline/background and can use larger models safely |

Upgrade triggers:

- Fish live synthesis success falls below 99% during background generation tests.
- GPU queue wait for `live_voice` is non-zero during stream tests.
- `nvidia-smi` shows less than 4-6 GB free VRAM before Fish synthesis.
- LTX/MuseTalk/LivePortrait/Wan workflow OOMs or forces unsafe model unloading during live mode.
- Disk usage exceeds 70% after model downloads and first video-loop experiments.
- Observer cannot preload loops from local cache without stutter because assets are too large or remote retrieval is too slow.

Queue policy on current Vast instance:

- One heavy GPU consumer at a time.
- During live YouTube tests, allowed GPU work:
  - Fish live synthesis;
  - current LLM call when needed;
  - procedural observer rendering.
- During live YouTube tests, disallowed unless explicitly idle/offline:
  - LTX generation;
  - Wan generation;
  - long Comfy video workflows;
  - full lipsynced highlight renders.
- Background video jobs must be cancellable/preemptible before they are enabled on the live host.

Deployment notes:

- Keep YouTube live proof and avatar-life validation on the current host until metrics say otherwise.
- Use short-lived SSH tunnels for diagnostics instead of opening public ports.
- Treat `8080` as operator gateway only.
- Keep Fish, ComfyUI, Ollama, Postgres, Redis, NATS, IPFS, and future GPU queue endpoints bound to host-local addresses.
- If upgrading Vast, prefer more VRAM/disk over more CPU first; the bottleneck is GPU memory and model/asset storage.
- Update `scripts/vast-provision.sh` only after the chosen model tier is proven. A premature default upgrade raises cost without proving avatar-life value.

Risks:

- Local Docker and Vast deployment disagree on Fish device mode: Compose uses CPU, Vast requires CUDA.
- Local host port for Fish is `8090`, but several runtime defaults and checks use `7860`.
- `POST /creator/genesis` hardcodes ComfyUI `localhost:8188` and Fish `localhost:7860` instead of using configured endpoints: `runtime/src/main.py:1611-1624`.
- Runtime `/ready` also hardcodes ComfyUI localhost probe and nginx probes: `runtime/src/main.py:395-407`.
- Non-host-network Vast Compose publishes Ollama as `11434:11434`: `docker-compose.vast.yml:23`. If the Vast firewall exposes that port, the Ollama API could be reachable publicly.

## Readiness / Health Checks

Confirmed:

- Runtime `/ready` checks ComfyUI through `http://localhost:8188/system_stats`: `runtime/src/main.py:399-400`.
- Runtime `/ready` performs a real Fish synthesis probe when voice is enabled/configured: `runtime/src/main.py:344-385` and `runtime/src/main.py:406-407`.
- Creator genesis checks Fish with `http://localhost:7860/v1/health`: `runtime/src/main.py:1623-1633`.
- Docker Compose Fish healthcheck calls `http://localhost:7860/`, not `/v1/health`: `docker-compose.yml:357-360`.

Risks:

- Fish health is inconsistent across Compose, `VoiceCloner`, `/ready`, and `/creator/genesis`.
- Comfy health is consistently shallow and may pass before model/workflow readiness.

## Tests / Verification

Command attempted from repo root:

```bash
pytest runtime/tests/test_avatar_genesis_pipeline.py runtime/tests/test_voice_surface.py runtime/tests/test_avatar_components.py runtime/tests/test_avatar_surface.py
```

Observed result:

- Collection failed.
- Error path: importing `avatar` imports `avatar.engine`; `avatar.engine` attempts `from ..banter.types` and then fallback `from banter.types`; `banter.types` is missing.

Command attempted from `runtime/`:

```bash
pytest tests/test_avatar_genesis_pipeline.py tests/test_voice_surface.py tests/test_avatar_components.py tests/test_avatar_surface.py
pytest tests/test_voice_surface.py
```

Observed result:

- Same collection failure.
- No avatar/voice integration tests could be executed until the `banter.types` import mismatch is fixed.

Confirmed relevant test expectations from code:

- `test_genesis_pipeline_pins_all_assets` expects portrait, expression manifest, and voice CID to be produced: `runtime/tests/test_avatar_genesis_pipeline.py:52-95`.
- `test_genesis_pipeline_uses_default_endpoints_when_env_missing` expects defaults `http://localhost:8188` and `http://localhost:7860`: `runtime/tests/test_avatar_genesis_pipeline.py:101-112`.
- Failure tests expect partial status when portrait pinning or expression manifest pinning fails: `runtime/tests/test_avatar_genesis_pipeline.py:115-180`.

## Strengths

- Clear separation between image generation (`PortraitGenerator`) and voice generation (`VoiceCloner`).
- Partial genesis is supported rather than all-or-nothing failure.
- Generated assets are pinned to IPFS and connected back to agent identity.
- Runtime has a real Fish synthesis readiness probe, not only a socket check.
- GPU pressure is explicitly addressed by unloading Ollama before ComfyUI/Fish operations.
- Concurrency is bounded with semaphores for ComfyUI and Fish.

## Weaknesses

- Config contracts drift between local Compose, Vast scripts, runtime defaults, and hardcoded readiness checks.
- "Voice embedding" naming does not match implementation; it stores reference WAV bytes.
- ComfyUI readiness is not a workflow readiness probe.
- Default Flux workflows appear to require custom nodes/models not provisioned by Docker Compose.
- Expression image generation likely depends on Comfy accepting a base64 data URI in `LoadImage`; this needs direct runtime validation against the deployed ComfyUI.
- Pinned expression CIDs are not clearly consumed by avatar rendering.
- Test collection is broken for avatar/voice paths due to missing `banter.types`.

## Highest Priority Follow-Up Work

1. Fix `banter.types` import mismatch so avatar/voice tests collect.
2. Normalize Fish and Comfy endpoint configuration; remove hardcoded `localhost` checks from creator genesis and `/ready` where configured endpoint exists.
3. Add a Comfy workflow readiness probe that submits a tiny known-good workflow or validates required models/nodes.
4. Decide whether production default is SDXL no-custom-node workflow or Flux custom-node workflow; make provisioning match that decision.
5. Replace expression reference data URI with Comfy upload flow if deployed Comfy does not support data URI `LoadImage`.
6. Rename or document `voice_model_cid` as reference audio CID, or introduce a separate metadata field.
7. Either wire archetype `voice_params`/prosody into Fish payloads or mark them as currently descriptive metadata only.
8. Verify whether expression manifest CIDs are consumed by observer/avatar renderer; if not, wire them or remove the claim that expressions are rendered from generated images.

## Open Questions

- Which deployment mode is the target for this branch: local Docker, Vast host-native, or both?
- Should default Comfy generation be reliable SDXL or higher-quality Flux?
- Does the deployed Fish Speech version expose `/v1/health`, `/v1/tts`, and `/capabilities` exactly as assumed?
- Does deployed ComfyUI accept data URI strings in `LoadImage`, or must images be uploaded first?
- Should Fish run before Comfy on single-GPU hosts, given Fish startup is stricter about CUDA residency?

## Wan + LTX-Video Incorporation Plan

Date added: 2026-06-26

Goal: move from static portrait + voice toward Twitch avatars that feel alive while preserving a factual, verifiable runtime path.

### Confirmed External Facts

- Wan2.1 is an open video generation suite. Its upstream README says it supports Text-to-Video, Image-to-Video, Video Editing, Text-to-Image, and Video-to-Audio: <https://github.com/Wan-Video/Wan2.1>
- Wan2.1 upstream says the T2V-1.3B model requires 8.19 GB VRAM and can generate a 5-second 480P video on an RTX 4090 in about 4 minutes without optimization: <https://github.com/Wan-Video/Wan2.1>
- Wan2.1 upstream says Wan2.1 was integrated into ComfyUI on 2025-02-27: <https://github.com/Wan-Video/Wan2.1>
- LTX-Video upstream says LTX-Video supports text-to-video and image-to-video generation: <https://github.com/Lightricks/LTX-Video>
- LTX-Video upstream says its model supports image-to-video, multi-keyframe conditioning, keyframe animation, video extension, and video-to-video transformations: <https://github.com/Lightricks/LTX-Video>
- LTX-Video upstream recommends using its ComfyUI workflow for best results: <https://github.com/Lightricks/LTX-Video>
- Lightricks' ComfyUI-LTXVideo repository describes itself as custom nodes/workflows for LTX-2 and says LTX-2 is built into ComfyUI core: <https://github.com/Lightricks/ComfyUI-LTXVideo>
- ComfyUI-LTXVideo prerequisites list CUDA-compatible GPU with 32GB+ VRAM and 100GB+ free disk space: <https://github.com/Lightricks/ComfyUI-LTXVideo>
- ComfyUI-LTXVideo includes example workflows for LTX-2.3, including text/image-to-video, control workflows, Lipdub, and text-to-audio: <https://github.com/Lightricks/ComfyUI-LTXVideo>
- ComfyUI-LTXVideo's Lipdub description says it can dub/rephrase speech in video and regenerate lips/audio to match target text while preserving speaker identity: <https://github.com/Lightricks/ComfyUI-LTXVideo>

### Correction To Proposed Mental Model

The user-provided summary is directionally useful, but the following claims need stricter wording:

- Confirmed: ComfyUI can act as the workflow/API host for image/video/audio nodes.
- Confirmed: Fish Speech can provide TTS/reference voice in our existing runtime through `/v1/tts`.
- Confirmed: LTX-Video/LTX-2 has ComfyUI workflows and audio/video capabilities according to upstream docs.
- Confirmed: Wan2.1 has ComfyUI integration and strong video-generation capabilities according to upstream docs.
- Not yet confirmed in this repo: LTX-Video "takes the Fish Audio file natively" in our deployment.
- Not yet confirmed in this repo: Wan plus a specific lip-sync node is installed, configured, and able to produce final lipsynced MP4s.
- Not yet confirmed in this repo: one-click final MP4 export exists in our current ComfyUI sidecar.

Therefore, the integration plan should treat LTX/Wan video as new avatar asset generation capabilities, not as already-working live rendering.

### Current Codebase Gaps For Video Models

Confirmed from current repo:

- Current avatar genesis produces still portrait and expression images, not video clips: `runtime/src/avatar/genesis_pipeline.py:184-258`.
- Current Comfy helper expects image bytes and validates PNG/JPEG only: `runtime/src/avatar/portrait_generator.py:148-177` and `runtime/src/avatar/portrait_generator.py:211-230`.
- Current `PipelineResult` has no video fields such as idle loop CID, talking loop CID, generated MP4 CID, or video manifest CID: `runtime/src/avatar/genesis_pipeline.py:33-55`.
- Current avatar runtime uses expression labels, motion labels, mouth-open values, and avatar CIDs; it does not consume generated video clips: `runtime/src/avatar/engine.py:264-324`.
- Current voice runtime can synthesize and cache audio bytes but does not pass audio to a Comfy video workflow: `runtime/src/voice/engine.py:598-655`.

Inference:

- Adding Wan/LTX cleanly requires a new video generation layer beside `PortraitGenerator` and `VoiceCloner`, not just adding model files to ComfyUI.

### Recommended Pipeline For Twitch Smoothness

The Twitch requirement is continuous perceived life, not only high-quality offline video. Based on current open-source model latency facts, diffusion video should not be the per-line live rendering path.

Recommended architecture:

1. Real-time layer:
   - Fish Speech synthesizes the current line.
   - Existing avatar runtime drives mouth-open/expression/pose immediately.
   - OBS/browser overlay displays the avatar with low-latency motion.
   - This keeps the Twitch stream responsive.

2. Background video asset layer:
   - ComfyUI generates avatar video loops asynchronously.
   - LTX is used first for fast draft/iteration and controlled image-to-video loops.
   - Wan is used for higher-quality cinematic loops and premium cutaways when time/GPU budget allows.
   - Generated MP4/WebM assets are pinned to IPFS and registered on the agent identity.

3. Playback/compositor layer:
   - Runtime chooses a pre-generated loop by agent + mood + scene.
   - Fish audio plays live.
   - Browser/OBS overlay blends generated loop, expression state, captions, and live mouth-open/lip approximation.

4. Optional high-quality post-generation layer:
   - For highlight clips, trailers, or replay moments, generate a full lipsynced MP4 with Fish audio + LTX/Wan/lipdub workflow.
   - This should be treated as asynchronous production, not the primary live Twitch path.

Why this is the recommended path:

- Wan2.1 1.3B 480P is documented at about 4 minutes for 5 seconds on RTX 4090 without optimization, so it is not a live per-utterance renderer.
- ComfyUI-LTXVideo lists 32GB+ VRAM and 100GB+ disk, which exceeds many single-GPU streaming hosts.
- The existing runtime already has real-time state and voice surfaces; extending those is lower-risk than blocking Twitch on diffusion video completion.

### New Code Modules Proposed

Proposed files:

- `runtime/src/avatar/video_generator.py`
  - New ComfyUI video workflow client.
  - Supports workflow templates for LTX and Wan.
  - Submits `/prompt`, polls `/history`, fetches MP4/WebM output.
  - Does not replace `PortraitGenerator`.

- `runtime/workflows/ltx_avatar_loop.json`
  - Image-to-video loop from canonical portrait.
  - Target: idle/listening/talking draft clips.

- `runtime/workflows/wan_avatar_cinematic.json`
  - Image-to-video or text-to-video cinematic clip.
  - Target: premium scenes, intros, transitions, cutaways.

- `runtime/workflows/ltx_lipdub_highlight.json`
  - Optional async full clip generation using generated or supplied audio.
  - Target: post-stream highlights, not live response.

- `runtime/src/avatar/video_manifest.py`
  - Manifest schema for per-agent generated loops.
  - Maps `agent`, `mood`, `motion`, `duration`, `model`, `workflow`, `cid`, and `source_audio_cid`.

### Data Model Proposed

Minimum new identity/runtime fields:

- `avatar_video_manifest_cid`
- `idle_loop_cid`
- `talking_loop_cid`
- `cinematic_clip_cids`
- `video_generation_status`
- `video_model_preference` with values such as `ltx_fast`, `wan_quality`, `none`.

These should be additive. Do not overload `avatar_cid`, `rigged_avatar_cid`, or `voice_model_cid`.

### ComfyUI Workflow Direction

Phase 1: Keep Fish outside ComfyUI.

- Reason: Fish is already integrated and tested by runtime paths.
- Runtime calls Fish `/v1/tts` and receives WAV bytes.
- Runtime pins audio or passes it to a video workflow when needed.

Phase 2: Add Comfy video workflow executor.

- Same API pattern as `PortraitGenerator`, but output validation must support MP4/WebM and metadata.
- Comfy workflow health should validate specific nodes/models, not only `/system_stats`.

Phase 3: Add LTX fast loop generation.

- Input: portrait image CID/bytes + agent motion prompt.
- Output: short idle/listening/talking clips.
- Runtime uses these as reusable Twitch assets.

Phase 4: Add Wan quality generation.

- Input: portrait/reference image + cinematic prompt.
- Output: higher-quality scene clips, transitions, and prebuilt reactions.
- Runtime uses these for non-immediate moments because generation latency is expected.

Phase 5: Add optional lipdub/highlight generation.

- Input: Fish audio + selected video or portrait/reference frames.
- Output: final MP4 for highlights or scheduled segments.
- This is the closest version of the "final lipsynced MP4" idea, but it should be asynchronous.

### Smoothness Strategy

For Twitch, "alive" should mean:

- zero dead air while video models run;
- immediate voice playback;
- continuous idle/talking/listening visual motion;
- expression changes tied to banter beats;
- generated cinematic clips entering when ready, not blocking the stream.

Implementation implication:

- The live path should remain browser/OBS/avatar-state-driven.
- Wan/LTX should be background asset factories and highlight renderers.
- A queue is required so video jobs do not starve Fish Speech or Ollama on a single GPU.

### Scheduler / GPU Policy Proposed

Priority order for a live stream:

1. Fish Speech live synthesis.
2. Ollama/current dialogue if needed for showrunner.
3. Lightweight avatar/browser rendering.
4. LTX fast loop generation when GPU is idle.
5. Wan quality generation during planned idle windows or off-stream.

Reason:

- Current code already unloads Ollama before Fish and Comfy work: `runtime/src/avatar/genesis_pipeline.py:408-422` and `runtime/src/voice/engine.py:611-622`.
- Vast scripts already recognize GPU contention and force Fish CUDA startup: `scripts/vast-restart-services.sh:376-402`.
- Video diffusion adds a much heavier GPU consumer than current still-image Comfy generation.

### Acceptance Criteria For Incorporation

Minimum factual proof before claiming success:

1. ComfyUI lists/loads required LTX/Wan nodes and models.
2. Runtime can submit one LTX workflow through `/prompt` and retrieve an MP4/WebM.
3. Runtime can submit one Wan workflow through `/prompt` and retrieve an MP4/WebM.
4. Generated video asset is pinned to IPFS.
5. Agent identity or manifest stores the video CID without overloading image/voice fields.
6. Observer/browser can play the video loop for an agent.
7. Fish live synthesis still works while video generation is queued or paused.
8. `/ready` distinguishes base Comfy health from LTX/Wan workflow readiness.

### Immediate Next Decision

Recommended first implementation path:

1. Fix test import blocker (`banter.types`) so avatar/voice tests run.
2. Add `VideoGenerator` with generic Comfy video output handling.
3. Add an LTX workflow first because upstream recommends Comfy workflows and LTX is positioned for faster iteration.
4. Add Wan second as the quality/cinematic backend.
5. Add queue/GPU policy before running both during a live Twitch session.

This keeps the live Twitch path stable while adding the new video models as increasingly capable background generators.

## Feedback Incorporation: Alive Twitch Avatars

Date added: 2026-06-26

User feedback accepted:

- The central product goal is not merely "generate MP4s"; it is to make avatars feel alive while streaming on Twitch.
- Wan/LTX diffusion video should not be treated as the live render loop.
- The live system needs a real-time animation layer, better lip sync, robust asset management, and background generation.
- This doc should track TODOs, use cases, personas, and concrete incorporation steps.

### Confirmed Additional External Facts

- LivePortrait is an official portrait animation implementation. The paper describes generating lifelike video from a source image using motion from driving video, audio, text, or generation, and reports 12.8ms generation speed on RTX 4090 with PyTorch: <https://arxiv.org/abs/2407.03168>
- LivePortrait's upstream repository describes it as official PyTorch implementation and includes source image/video plus driving video inference examples that produce MP4 outputs: <https://github.com/KlingAIResearch/LivePortrait>
- MuseTalk paper targets real-time talking-face video generation and reports online 256x256 face generation above 30 FPS with negligible startup latency: <https://arxiv.org/abs/2410.10122>
- MuseTalk upstream repository describes it as real-time high-quality lip synchronization with latent-space inpainting: <https://github.com/TMElyralab/MuseTalk>
- Wav2Lip paper addresses arbitrary-identity lip synchronization and released code/models at the Wav2Lip GitHub repository: <https://arxiv.org/abs/2008.10010>
- Wav2Lip upstream repository contains the code for "A Lip Sync Expert Is All You Need for Speech to Lip Generation In the Wild": <https://github.com/Rudrabha/Wav2Lip>
- ComfyUI-LTXVideo includes Lipdub workflows and describes Lipdub as regenerating lips/audio to match target text while preserving speaker identity: <https://github.com/Lightricks/ComfyUI-LTXVideo>

### Real-Time Embodiment Candidates - Facts And Integration Status

Confirmed external facts as of 2026-06-26:

- `kijai/ComfyUI-LivePortraitKJ` provides ComfyUI nodes for LivePortrait: <https://github.com/kijai/ComfyUI-LivePortraitKJ>
- `ComfyUI-LivePortraitKJ` documents realtime webcam, image-to-video, and video-to-video examples, and says a rework improved speed and efficiency with near-realtime view in Comfy at about 80-100ms delay: <https://github.com/kijai/ComfyUI-LivePortraitKJ>
- `ComfyUI-LivePortraitKJ` documents MediaPipe as an alternative to InsightFace, with licensing notes and model placement under `ComfyUI/models/liveportrait`: <https://github.com/kijai/ComfyUI-LivePortraitKJ>
- `chaojie/ComfyUI-MuseTalk` exists as a ComfyUI MuseTalk custom-node repository: <https://github.com/chaojie/ComfyUI-MuseTalk>
- `AIFSH/ComfyUI-MuseTalk_FSH` describes itself as a ComfyUI custom node for MuseTalk to make audio-driven videos: <https://github.com/AIFSH/ComfyUI-MuseTalk_FSH>
- `kijai/ComfyUI-WanVideoWrapper` describes itself as ComfyUI wrapper nodes for WanVideo and related models: <https://github.com/kijai/ComfyUI-WanVideoWrapper>
- `ComfyUI-WanVideoWrapper` includes related talking/portrait/video folders such as `fantasytalking`, `fantasyportrait`, `multitalk`, and `s2v`: <https://github.com/kijai/ComfyUI-WanVideoWrapper>
- `ComfyUI-LTXVideo` includes LTX-2.3 example workflows for image/text-to-video, IC-LoRA motion tracking, Lipdub, and text-to-audio: <https://github.com/Lightricks/ComfyUI-LTXVideo>
- `ComfyUI-LTXVideo` documents Lipdub IC-LoRA as a workflow that can dub or rephrase speech in video, regenerate lips/audio, and preserve speaker identity through reference audio tokens: <https://github.com/Lightricks/ComfyUI-LTXVideo>

Current integration status in this repo:

- None of `ComfyUI-LivePortraitKJ`, `ComfyUI-MuseTalk`, `ComfyUI-MuseTalk_FSH`, `ComfyUI-WanVideoWrapper`, or `ComfyUI-LTXVideo` are provisioned in `docker-compose.yml`.
- No custom-node installation script exists in this repo for these nodes.
- No runtime code path calls LivePortrait, MuseTalk, Wav2Lip, Wan lip-sync variants, LTX Lipdub, or Comfy video output workflows.
- Current Comfy integration is image-oriented and validates PNG/JPEG only: `runtime/src/avatar/portrait_generator.py:211-230`.

Risks:

- Adding these as Comfy nodes increases Comfy provisioning/model-readiness complexity.
- Adding them as sidecars increases endpoint, health-check, process-supervision, and GPU-scheduling complexity.
- Treating repository existence as project integration would be misleading. Integration requires Docker/native provisioning, model downloads, health probes, runtime calls, output fetching, and observer playback.

### Sidecar vs ComfyUI Embodiment Tradeoffs

Date added: 2026-06-26

Confirmed external facts:

- ComfyUI custom-node routes such as LivePortraitKJ, MuseTalk variants, WanVideoWrapper, and LTXVideo exist as separate projects from this repo.
- The current repo already uses ComfyUI through the `/prompt`, `/history`, and `/view` API pattern for image generation: `runtime/src/avatar/portrait_generator.py:115-165`.
- This repo does not yet provision or call LivePortraitKJ, MuseTalk, WanVideoWrapper, or LTXVideo.

Tradeoff matrix:

| Approach | Provisioning effort | Typical latency on RTX 4090 class | Streaming stability | Maintenance burden | Recommendation for this project |
| --- | --- | --- | --- | --- | --- |
| Pure ComfyUI nodes | High: custom-node install, model download, workflow JSON | 100-500ms+ plus queue, must measure | Medium: polling and VRAM contention | High: workflow/node update breakage | Good for offline LTX/Wan assets; marginal for real-time |
| Dedicated sidecar, FastAPI or equivalent | Medium: Docker/native service plus model download | 30-150ms target, must measure | High if queue/GPU policy is explicit | Medium | Preferred candidate for MuseTalk/LivePortrait live layer |
| Browser-native WASM/canvas | Low if a viable model exists | Under 50ms target | Highest | Low | Ideal long-term, not yet assumed viable at quality target |
| Hybrid: Comfy for assets, sidecar for live | Medium-high | Mixed | High | Medium | Current best path |

Risks:

- Treating ComfyUI as the universal executor for real-time embodiment may introduce avoidable polling latency and queue contention with Fish.
- Sidecars multiply services to supervise, health-check, and GPU-schedule.

Inference:

- For Twitch "alive" feel, the real-time embodiment layer should default to a dedicated sidecar candidate while ComfyUI remains focused on background asset generation: LTX/Wan loops, cinematic clips, and highlights.

### Real-Time Embodiment Sidecar API Contract

Date added: 2026-06-26

Proposed minimal sidecar contract for MuseTalk, LivePortrait, Wav2Lip, or equivalent candidates:

```http
POST /embody
Content-Type: application/json
```

```json
{
  "portrait_cid": "bafk...",
  "portrait_bytes": "base64 optional",
  "audio_bytes": "base64 wav",
  "duration_ms": 5000,
  "emotion": "neutral",
  "motion_seed": 42
}
```

Required successful responses:

- `200` with binary MP4/WebM bytes or a streaming chunked response.
- `X-Latency-Ms` response header.
- JSON metadata when available:
  - `mouth_landmarks`;
  - `confidence`;
  - `model`;
  - `duration_ms`;
  - `frame_count`.

Async response option:

- `202` with `job_id` for requests too slow for live interaction.
- `GET /jobs/{job_id}` for status.
- `GET /jobs/{job_id}/result` for video output.

Health contract:

```http
GET /health
```

Expected health fields:

- model loaded status;
- device;
- current VRAM estimate if available;
- queue depth;
- average latency;
- last error.

Implementation options:

- FastAPI plus PyTorch, preferred for low-latency live sidecars.
- Gradio only for quick manual testing.
- Docker service named `embodiment` with GPU device passthrough when containerized.

Risk:

- Without this contract, each embodiment candidate will require custom runtime integration code.

### Issue #96 Benchmark Status

Date added: 2026-06-27

Candidate selected for the first real-time embodiment benchmark: MuseTalk.

Integration path to test first: dedicated sidecar, not ComfyUI. This follows the sidecar
recommendation above because the live path needs low request latency and explicit GPU
scheduling, while ComfyUI polling/custom-node provisioning is better reserved for background
asset generation until measured otherwise.

Current status: blocked, not measured.

Exact blocker:

- The prior Vast.ai instance was deleted.
- The current operator constraint for this pass is code only: no Vast.ai work and no model
  loading.
- No target GPU host with MuseTalk models and a sidecar service is available for `nvidia-smi`
  capture, dependency installation, or an `/embody` request.

Added repo artifacts:

- Benchmark record model: `runtime/src/avatar/embodiment_benchmark.py`.
- Sidecar benchmark runner: `scripts/benchmark-embodiment-sidecar.py`.
- Contract tests: `runtime/tests/test_embodiment_benchmark.py`.
- Field report: `field-reports/issue-96-embodiment-benchmark.md`.

Command to run when a target GPU host exists:

```bash
python scripts/benchmark-embodiment-sidecar.py \
  --candidate musetalk \
  --endpoint http://localhost:7861 \
  --portrait-file avatar.png \
  --audio-file fish.wav \
  --host-label vast-4090 \
  --gpu-name "RTX 4090" \
  --vram-total-mb 24576 \
  --out field-reports/issue-96-musetalk.json
```

Decision:

- Do not integrate MuseTalk, LivePortrait, Wav2Lip, or any real-time embodiment sidecar into
  the live path until a target GPU run records latency, VRAM, output quality, and failure
  behavior.
- Keep the live baseline on Fish audio amplitude plus procedural life signals until the first
  sidecar benchmark is measured.

### Revised Target Architecture

The target should be a hybrid avatar system with four layers:

1. **Live control layer**
   - Existing showrunner/banter/audience state decides who speaks and what emotional beat is active.
   - Runtime emits `speaking`, `expression`, `pose`, `motion`, `mouth_open`, captions, and scene metadata.
   - This layer must be low-latency and cannot wait for diffusion video.

2. **Real-time embodiment layer**
   - Procedural breathing, blinking, idle sway, eye focus, head micro-movement, and expression easing.
   - Optional real-time lip/face driver such as MuseTalk, Wav2Lip, or LivePortrait-style portrait driving.
   - This is the layer that makes Twitch avatars feel alive moment-to-moment.

3. **Background generative asset layer**
   - LTX generates reusable fast loops and lipdub/highlight clips through ComfyUI.
   - Wan generates higher-quality cinematic clips, cutaways, scene transitions, and premium reactions.
   - Jobs run asynchronously and must never starve Fish live synthesis.

4. **Playback/composition layer**
   - Browser/OBS overlay chooses the best available visual source:
     - real-time procedural avatar;
     - pre-generated idle/talking/listening loop;
     - high-quality cinematic clip when ready;
     - fallback portrait if video fails.
   - Fish audio remains the canonical live voice path.

### Observer / Browser Overlay Requirements

The browser/OBS layer must handle hybrid sources without perceptible glitches. Generating video assets is not enough if the observer cannot play, blend, and switch them cleanly.

Required capabilities to confirm or implement in code:

- Seamless switching between procedural canvas/WebGL avatar, pre-generated MP4/WebM loop, cinematic clip, and static fallback.
- Layer blending for live audio mouth amplitude, expression overrides, captions, and current scene state.
- Low-latency video texture updates through `<video>` plus `requestAnimationFrame`, canvas, Three.js, or another measured renderer path.
- State synchronization from runtime to observer through WebSocket or a sufficiently low-latency polling path.
- Manifest-aware asset selection by agent, mood, motion, scene, and fallback priority.
- Preloading and crossfading so loop swaps do not produce black frames or visible buffering.

Current repo observations:

- Observer has avatar components, but this audit has not confirmed a video-manifest playback path.
- Runtime avatar state produces expression, motion, mouth-open, and asset CIDs; it does not yet select generated video loop CIDs: `runtime/src/avatar/engine.py:264-324`.

Risk:

- If the observer only supports static images or simple mouth-open state, LTX/Wan/LivePortrait investment will not produce visible Twitch improvement.

### Personas / Runtime Use Cases

These personas describe what the pipeline must satisfy, not human marketing personas.

**The Live Speaker**

- Needs immediate voice playback and visible mouth/activity when the agent speaks.
- Cannot wait for Wan/LTX generation.
- Uses Fish live synthesis plus real-time mouth/expression driver.
- Success metric: no dead air, no frozen avatar during dialogue.

**The Listener**

- Needs subtle motion while another agent speaks.
- Uses procedural breathing/blinking/head-turning plus pre-generated idle/listening loops.
- Success metric: stage feels populated, not like static portraits.

**The Emotional Reactor**

- Needs visible beat response to CRACK, TAUNT, CONCEDE, ESCALATE, SILENCE.
- Uses current visual state overrides plus generated mood loops when available.
- Success metric: expression changes align with banter beats.

**The Cinematic Cutaway**

- Needs high-quality short visual moments for transitions, dramatic beats, intros, and recaps.
- Uses Wan quality generation or LTX high-quality workflow in the background.
- Success metric: high visual quality without blocking the live dialogue loop.

**The Highlight Producer**

- Needs full lipsynced MP4 clips after the fact or during low-pressure windows.
- Uses Fish audio plus LTX Lipdub or another verified lip-sync workflow.
- Success metric: generated clip can be exported, pinned, replayed, or published.

**The Operator**

- Needs predictable resource use and clear readiness.
- Uses health probes, model readiness probes, queues, and visible job states.
- Success metric: knows whether Fish, Comfy, LTX, Wan, and lip-sync are usable.

### Technique Matrix

| Technique | Best use | Live Twitch role | Risk |
| --- | --- | --- | --- |
| Fish Speech | Live TTS/reference voice | Primary voice path | GPU/endpoint drift; reference WAV naming ambiguity |
| Procedural animation | Breathing, blinking, idle sway, mouth approximation | Primary live aliveness layer | Can look simple unless tuned |
| MuseTalk | Real-time/near-real-time talking face lip sync | Candidate live lip layer | Requires integration/provisioning; resolution/quality tradeoffs |
| Wav2Lip | Robust lip-sync baseline | Candidate fallback/offline lip layer | Older quality profile; integration work |
| LivePortrait | Portrait animation from source + driving motion | Candidate real-time/near-real-time embodiment layer | Needs driving motion/template design |
| LTX / LTX-2 | Fast video loops, image-to-video, Lipdub/highlights | Background asset factory and possible highlight renderer | VRAM/disk requirements; workflow validation needed |
| Wan | Cinematic/high-quality video clips | Background premium/cutaway generator | Too slow for per-line live use |

### Latency And Hardware Reality Matrix

These values are planning estimates until measured on the target host. Mark any production claim invalid until benchmarked in `runtime/tests/benchmarks/` or equivalent field logs.

| Component | Typical latency on RTX 4090/5090 class | Live Twitch feasible? | VRAM peak | Key loophole / risk |
| --- | --- | --- | --- | --- |
| Fish Speech live TTS | Sub-second to a few seconds, deployment-dependent | Yes | Low to medium | Reference-audio fallback can mask broken per-agent voices |
| Procedural life signals | Under 16ms per frame target | Yes | Negligible | Looks mechanical if untuned |
| MuseTalk / LivePortrait via Comfy or sidecar | Tens to hundreds of ms if optimized | Marginal to yes, must measure | Medium to high | Speed usually trades against resolution/quality |
| LTX-2.3 Lipdub / loops | Seconds to tens of seconds per short clip | No, background only | High, documented 32GB+ recommendation for ComfyUI-LTXVideo | Timeline drift or identity drift on long clips |
| Wan 2.1/2.2 cinematic | Minutes per clip depending model/settings | No | High | Too slow for reactive use |
| Full lipsynced highlight | Minutes to tens of minutes | Offline only | High | Phoneme accuracy and identity consistency must be evaluated |

Inference:

- Any path claiming "alive on Twitch" while routing live speech through diffusion video generation will fail smoothness criteria unless measured latency proves otherwise.
- The credible live path is Fish plus procedural/real-time embodiment. LTX/Wan should be background asset generation and highlight production.

### Incorporation Strategy For New Models

The model incorporation order should optimize for perceived aliveness first, cinematic quality second.

**Step 1: Stabilize existing avatar/voice foundation**

- Fix `banter.types` import blocker so avatar and voice tests run.
- Normalize Comfy/Fish endpoint config and remove hardcoded local probes where configured endpoints exist.
- Rename/document `voice_model_cid` as reference audio or add separate `voice_reference_cid`.

**Step 2: Add procedural life immediately**

- Add deterministic live animation signals to `runtime/src/avatar/engine.py` or a new `avatar/life_signals.py`.
- Signals:
  - breathing phase;
  - blink timer;
  - micro head sway;
  - eye focus/attention target;
  - expression easing;
  - mouth openness driven by audio amplitude when available.
- This gives the fastest path to "alive" without waiting for video generation.

**Step 3: Add real-time lip/face candidate layer**

- Evaluate MuseTalk, Wav2Lip, and LivePortrait as separate sidecars or Comfy nodes.
- Do not assume they belong inside ComfyUI until deployment is verified.
- Start with one candidate and a small API contract:
  - input: portrait/video frame + Fish WAV bytes or audio stream;
  - output: short video frames or MP4/WebM;
  - latency: measured on target GPU;
  - fallback: procedural mouth if unavailable.

**Step 4: Add `VideoGenerator` for Comfy video workflows**

- Generic Comfy client for video outputs.
- Reuse `/prompt`, `/history`, `/view` pattern from `PortraitGenerator`.
- Add MP4/WebM validation.
- Add output manifest metadata.

**Step 5: Add LTX first**

- Use LTX for fast reusable loops:
  - idle breathing loop;
  - listening loop;
  - talking-neutral loop;
  - emotional reaction loops.
- Add optional LTX Lipdub/highlight workflow only after basic loop generation works.

**Step 6: Add Wan second**

- Use Wan for:
  - intros;
  - scene transitions;
  - cinematic cutaways;
  - high-quality recap clips;
  - premium reactions.
- Do not put Wan in the blocking live speaker path.

**Step 7: Add asset selection and seamless playback**

- Observer/browser chooses the best available source per agent state.
- Required fallback order:
  - live procedural/real-time driven avatar;
  - matching pre-generated loop;
  - neutral idle loop;
  - static portrait.

### GPU / Resource Contention Model

Confirmed risks from this repo:

- Single-GPU hosts are already treated as resource-constrained by the Vast scripts.
- Fish is forced to CUDA in `scripts/vast-restart-services.sh:376-382`.
- Ollama is explicitly unloaded before Fish startup in `scripts/vast-restart-services.sh:393-402`.
- Runtime unloads Ollama before Comfy genesis work at `runtime/src/avatar/genesis_pipeline.py:408-422`.
- Runtime unloads Ollama before live Fish synthesis at `runtime/src/voice/engine.py:611-622`.

Inference:

- The existing unload-Ollama pattern is useful but insufficient for video diffusion because LTX/Wan jobs can hold VRAM for much longer than still-image generation or one TTS call.

Recommendation:

- Add a central GPU job queue before adding production video generation.
- Proposed module path: `runtime/src/gpu/job_queue.py`.
- Required behavior:
  - priority classes: `live_voice`, `live_llm`, `observer_render`, `ltx_background`, `wan_background`, `offline_highlight`;
  - one active heavy GPU job unless host capability says otherwise;
  - explicit model unload/reload hooks;
  - cancellation/preemption for background jobs when Fish live synthesis needs GPU;
  - status surfaced through `/ready` or a new diagnostics endpoint;
  - metrics for queue wait time, runtime, failure reason, VRAM before/after.

### Full GPU Job Queue Specification

Date added: 2026-06-26

Proposed module:

- `runtime/src/gpu/job_queue.py`

Priority levels, strict ordering:

1. `live_voice`: Fish synthesis; highest priority and preemptive.
2. `live_llm`: Ollama/current dialogue work.
3. `observer_render`: procedural/avatar render support.
4. `real_time_embodiment`: LivePortrait/MuseTalk/Wav2Lip sidecar calls.
5. `ltx_background`: reusable loop generation.
6. `wan_background`: cinematic/quality generation.
7. `offline_highlight`: non-live highlight rendering.

Required features:

- Single heavy-GPU consumer by default, configurable for multi-GPU hosts.
- Context-manager API for acquire/release.
- Explicit unload/reload hooks for Ollama, ComfyUI, and embodiment models.
- Cancellation token for background jobs.
- Preemption hook when `live_voice` arrives during background work.
- In-memory stats first; Prometheus-style metrics later if needed.
- Diagnostics endpoint, proposed path: `/diagnostics/gpu`.

Minimum stats:

- current job;
- queue depth by priority;
- active and pending jobs;
- last start/end time;
- last error;
- total completed;
- total cancelled;
- total failed;
- total rejected;
- total preemption requests;
- average wait time by priority;
- average runtime by priority.

Risk:

- Without a queue, LTX/Wan jobs can monopolize VRAM and make Fish voice unreliable during live streaming.

### Issue #97 GPU Queue Status

Date added: 2026-06-27

Implemented in this repo:

- `runtime/src/gpu/job_queue.py` now provides a priority-aware `GPUJobQueue`.
- Default policy remains one active heavy GPU consumer, matching single-GPU Vast.ai hosts.
- Priority order is `live_voice`, `live_llm`, `observer_render`, `real_time_embodiment`,
  `ltx_background`, `wan_background`, `offline_highlight`.
- `async with queue.acquire(...)` now yields a `GPUJobLease` cancellation token.
- When `live_voice` arrives during active background work, the queue requests cooperative
  cancellation on active LTX/Wan/offline jobs.
- Live mode can reject new LTX/Wan/offline work through `enter_live_mode()` or
  `set_background_jobs_allowed(False)`.
- Optional hooks exist for adapter-level unload/reload behavior without coupling the queue to
  Fish, ComfyUI, or embodiment implementations.
- Runtime exposes queue state at `/diagnostics/gpu`.

### Issue #101 YouTube Live Proof Readiness

Date added: 2026-06-27

Implemented in this repo:

- YouTube private-stream readiness report: `runtime/src/broadcast/live_proof.py`.
- Operator endpoint: `GET /broadcast/youtube-proof`.
- Contract tests: `runtime/tests/test_youtube_live_proof.py`.
- Field report/checklist: `field-reports/issue-101-youtube-live-proof.md`.

The report checks the exact pre-stream surface needed for the YouTube proof:

- Fish voice is configured and has audio evidence.
- Avatar visual source is available.
- Procedural life signals are visible.
- Mouth state reacts while voice is active.
- Captions are present.
- Comfy/video failure degrades to portrait/generated fallback instead of a
  black stage.

Operational status:

- Code-only readiness is implemented.
- The real 5-10 minute private YouTube/OBS VOD and benchmark JSON/notes remain
  blocked until a live host/stream test window is available.
- Do not close issue #101 from code alone.

### Issue #102 Twitch Platform Boundary

Date added: 2026-06-27

Implemented in this repo:

- Shared platform audience boundary: `runtime/src/platforms/boundary.py`.
- Twitch adapter routes incoming EventSub/Helix-style events through that
  boundary before producing world events.
- Boundary tests: `runtime/tests/test_platform_boundary.py`.
- Expanded Twitch replay/moderation/routing tests:
  `runtime/tests/test_twitch_adapter.py`.
- Field report/checklist: `field-reports/issue-102-twitch-platform-boundary.md`.

The boundary makes Twitch expansion explicit without moving the immediate target
away from YouTube:

- platform events route to showrunner/audience state only;
- direct avatar, voice, OBS, broadcast, and GPU effects are not allowed;
- moderation state is represented before a chat event can affect presentation;
- rate-limit bucket metadata is attached to chat/audience events;
- replay keys remain stable across EventSub duplicate delivery;
- Twitch status exposes bot/channel identity readiness.

Operational status:

- Code-only platform boundary is implemented.
- Twitch launch remains gated on completion of the YouTube avatar-life milestone.
- Do not close issue #102 from code alone.

### Issue #103 Avatar Acceptance Suite

Date added: 2026-06-27

Current matrix:

- Runtime contract: `runtime/src/avatar/acceptance_suite.py`.
- Contract tests: `runtime/tests/test_avatar_acceptance_suite.py`.
- Field report/checklist: `field-reports/issue-103-avatar-acceptance-suite.md`.

Personas covered:

- Live Speaker.
- Listener.
- Emotional Reactor.
- Cinematic Cutaway.
- Highlight Producer.
- Operator.

Use cases covered:

- Agent speaks normally.
- Agent listens silently for 30 seconds.
- Emotional beat changes expression within one second.
- Fish failure degrades visibly instead of hiding silence risk.
- Comfy/video failure stays alive through visual fallback.
- Background asset jobs do not block Fish.
- Observer switches between procedural/static fallback, loop, and cinematic
  sources.
- Offline highlight clip export has a benchmark/manual evidence path.
- Operator can see health, fallback, queue, and current visual-source state.

Validation status:

- `build_acceptance_suite_report()` returns `status=complete` and no validation
  gaps for the shipped matrix.
- Manual VOD evidence is still required by the individual cases during later
  live field runs, but the acceptance suite definition is complete.

Vast.ai policy:

- Keep background LTX/Wan/offline jobs disabled during live YouTube proof runs until the jobs
  are proven cooperative with cancellation and Fish synthesis remains reliable.
- Keep GPU/model services host-local behind SSH/operator gateway; this queue does not require
  opening public model ports.
- Treat `live_voice` wait time above near-zero as a deployment blocker before enabling
  background video generation.

### Asset Management And IPFS Realities

Date added: 2026-06-26

Confirmed current repo status:

- Current genesis pipeline pins still images and JSON manifests, not video assets: `runtime/src/avatar/genesis_pipeline.py:189-258`.
- No video pinning path, video manifest lifecycle, or observer video preloading path has been confirmed in this repo.

Risks:

- Video loops are much larger than still images. Multiple agents times moods times motions times resolutions can quickly consume storage and IPFS pinning bandwidth.
- First-load retrieval latency for large IPFS blobs can break seamless playback if the observer waits until the moment of display.
- Without lifecycle rules, generated variants can accumulate faster than they create stream value.

Mitigations proposed:

- Generate two variants per loop:
  - low-resolution live variant, such as 480p, for observer playback;
  - high-resolution variant only for highlights/export.
- Use manifest-driven lazy loading plus local browser cache.
- Preload the next likely loop before expression/motion transitions.
- Add expiration/garbage-collection policy for old video CIDs.
- Consider hybrid storage:
  - IPFS for durable asset identity;
  - local cache or S3-compatible hot storage for stream-time playback.

Inference:

- Short 5-15 second loops at moderate resolution are the practical live asset unit. Longer or high-resolution cinematic clips should be optional/offline until storage, bandwidth, and playback behavior are measured.
- Without explicit asset size and lifecycle policies, video generation will create operational debt faster than value.

### Issue #98 Video Manifest And Cache Policy

Date added: 2026-06-27

Implemented in this repo:

- Versioned video manifest schema: `runtime/src/avatar/video_manifest.py`.
- Asset variants:
  - `low_res_live` for hot observer playback loops.
  - `high_res_highlight` for durable/export-quality clips.
- Manifest fields track asset id, CID, variant, model, resolution, duration, source image/audio
  CIDs, expression, motion, priority, status, size, local cache path, creation time, and expiry.
- Manifest serialization deliberately does not include `avatar_cid`, `rigged_avatar_cid`, or
  `voice_model_cid`; video assets stay separate from identity image and voice references.
- Deterministic selection helper:
  - live path prefers matching low-res live loop;
  - then neutral low-res live loop;
  - then any low-res live loop;
  - then static portrait;
  - then no asset.
- Highlight path prefers matching high-res highlight clips, then low-res live fallback, then
  static portrait.
- IPFS retrieval failure is represented through failed CIDs and falls back to local cache or
  static portrait instead of black video.
- Retention policy marks expired or old low-priority CIDs as GC candidates while retaining
  highlight clips by default.
- Local cache policy separates hot playback cache from durable IPFS identity.

Operational policy:

- Generated video CIDs should be pinned durably only when they are useful enough for the
  manifest priority floor.
- Low-res live loops may be kept hot in local/browser cache for stream-time playback.
- High-res highlight clips should remain durable/export-focused and should not be selected for
  the default live observer path unless explicitly requested.
- IPFS failures should degrade to cached video, then static portrait, never to a black stage.

### Issue #99 LTX Background Loop Path

Date added: 2026-06-27

Implemented in this repo:

- `runtime/src/avatar/video_generator.py` now has a richer `VideoGenerationResult` path for
  Comfy workflow submission, polling, MP4/WebM fetch, timeout, and error reporting.
- `LTXLoopRequest` and `generate_ltx_loop_asset()` queue LTX generation as
  `ltx_background`, pin returned video bytes through an injected pin adapter, and register the
  result as a `low_res_live` asset in `VideoManifest`.
- LTX generation is rejected when the GPU queue disables background jobs for live mode.
- Mocked tests cover Comfy submission, history polling, output fetch, timeout behavior, pinning,
  manifest registration, and live-mode rejection.
- Added background-only workflow template: `runtime/workflows/ltx_image_to_video_loop.json`.

Current constraint:

- No actual LTX model was loaded or run in this code-only pass.
- The workflow template still requires a provisioned ComfyUI-LTXVideo environment before a real
  MP4/WebM can be produced on a GPU host.
- Production enablement still requires a field run showing Fish synthesis is not starved while
  LTX jobs are queued or cancelled.

### Issue #100 Offline Quality Layer Path

Date added: 2026-06-27

Implemented in this repo:

- `QualityClipRequest` and `generate_quality_clip_asset()` register offline/high-quality clips
  as `high_res_highlight` manifest assets.
- Wan cinematic clips run through the GPU queue as `wan_background`.
- LTX LipDub/highlight clips run through the GPU queue as `offline_highlight`.
- Both paths use injected pin adapters and remain separate from observer playback selection.
- Added offline-only workflow templates:
  - `runtime/workflows/wan_cinematic_clip.json`;
  - `runtime/workflows/ltx_lipdub_highlight.json`.
- Mocked tests cover Wan manifest registration, LipDub audio-source registration, and
  live-mode/background-job rejection.

Current constraint:

- No Wan, LTX LipDub, or equivalent quality model was loaded or run in this code-only pass.
- No generation time, VRAM, disk, or output-quality measurements exist yet for these quality
  workflows on the target GPU class.
- Do not claim quality gains until a field benchmark attaches measured hardware/profile data and
  output review notes.

### Issue #91 /one Live Design Re-Audit

Date added: 2026-07-01

Field report:

- `field-reports/issue-91-one-live-design-audit-20260701.md`

Confirmed from the live Vast run:

- The `/one` feature should stay narrowly scoped to one visible avatar reciting the alphabet.
- This baseline path must not depend on LTX, Wan, LipDub, or offline cinematic generation.
- Vast native setup had boot-layer gaps that blocked proof before the observer could be captured:
  missing `zstd`, missing `ss`/`fuser` packages, brittle `find | head -1` under `pipefail`, and
  Fish setup downloading `fishaudio/fish-speech-1.5` while restart launched S2-Pro paths.
- The corrected design is to align Vast setup and restart on Fish Audio S2-Pro:
  download `fishaudio/s2-pro` into `checkpoints/s2-pro`, then launch with
  `checkpoints/s2-pro/codec.pth`.

Current status:

- `/one` observer/runtime behavior has code and static tests.
- Vast boot hardening has code and static tests.
- Live proof remains open until a fresh S2-Pro run captures screenshot and video of `/one`.

### TODO Backlog

Status legend: `todo`, `blocked`, `in_progress`, `done`.

| Status | Area | Task | Evidence / note |
| --- | --- | --- | --- |
| todo | Tests | Fix `banter.types` import blocker | Current avatar/voice tests fail during collection |
| todo | Config | Normalize Comfy/Fish endpoint resolution across runtime, Compose, Vast | Drift documented in Deployment / Configuration section |
| todo | Health | Add Comfy workflow readiness probe | `/system_stats` is too shallow |
| done | Data model | Add video manifest fields instead of overloading image/voice CIDs | #98 adds versioned video manifest schema, deterministic selection, cache policy, and GC candidate helpers |
| todo | Live animation | Add procedural breathing/blink/head-sway/mouth-amplitude layer | Fastest path to perceived life |
| blocked | Lip sync | Evaluate MuseTalk vs Wav2Lip vs LivePortrait on target hardware | #96 selected MuseTalk sidecar first; target GPU/model run is blocked because the Vast.ai instance was deleted and this pass is code-only |
| done | Comfy video | Implement `VideoGenerator` for MP4/WebM outputs | #99 adds mocked Comfy submission, polling, fetch, timeout, and MP4/WebM validation path |
| blocked | LTX | Run one LTX image-to-video loop workflow from avatar portrait | #99 adds workflow/template/queue/manifest path; actual LTX model run is blocked until a GPU/model window |
| blocked | LTX Lipdub | Verify Fish WAV -> LTX Lipdub/highlight workflow | #100 adds offline workflow/template/manifest path; actual LipDub model run and benchmark remain blocked until GPU/model window |
| blocked | Wan | Run one Wan image/text-to-video cinematic workflow | #100 adds offline Wan workflow/template/manifest path; actual Wan model run and benchmark remain blocked until GPU/model window |
| done | Queue | Add GPU job priority: Fish > Ollama live > real-time render > LTX > Wan | #97 adds priority scheduling, cooperative background cancellation, live-mode background rejection, and `/diagnostics/gpu` |
| todo | Observer | Add video loop playback and fallback selection | Current avatar runtime does not consume video CIDs |
| in_progress | Assets | Pin generated video and store manifest CID | #98 defines durable video CIDs, source CIDs, expiry, priority, local cache status, and retention/GC policy; actual generation/pinning remains for later model issues |
| blocked | Benchmarks | Record generation time, VRAM, disk per model/workflow | #96 benchmark contract and runner added; real latency/VRAM/output evidence still requires a target GPU host |

### Acceptance Criteria For "Alive On Twitch"

Do not claim success until these are true:

1. Agent can speak with Fish audio while avatar visibly moves immediately.
2. Avatar does not freeze when LTX/Wan generation is running.
3. There is a procedural or real-time lip/mouth path independent of offline diffusion video.
4. At least one generated idle/listening/talking loop can be selected and played by the observer.
5. At least one emotional beat changes visible expression/motion within one second.
6. Fish live synthesis retains priority over video jobs.
7. If Comfy/LTX/Wan is down, the Twitch stream still runs with degraded visuals.
8. Runtime status distinguishes:
   - base Comfy health;
   - LTX readiness;
   - Wan readiness;
   - lip-sync readiness;
   - Fish synthesis readiness.

### Loopholes To Avoid

- Do not call a static portrait CID a rigged avatar.
- Do not call a seed WAV a model embedding without clarifying semantics.
- Do not claim "perfect live lip sync" when runtime only has mouth-open heuristics.
- Do not claim LTX/Wan are live renderers until measured latency supports it.
- Do not claim ComfyUI is ready because `/system_stats` returns 200.
- Do not claim one-click MP4 export until the workflow exists, runs, and output is fetched/pinned.
- Do not let video generation block Fish, showrunner dialogue, or OBS/browser overlay.
- Do not claim active movement when only speech-driven head nods exist without continuous idle breathing, blinking, or micro-sways.
- Do not overload `rigged_avatar_cid`, `avatar_cid`, or `voice_model_cid` with video assets.
- Do not treat ComfyUI node availability as integration until Docker/native provisioning, health probes, and runtime `VideoGenerator` or equivalent calls exist.
- Avoid "Hollywood-grade" quality claims until side-by-side human evaluation on Twitch VODs shows consistent superiority over the procedural plus LivePortrait/MuseTalk baseline.
- Do not ignore single-GPU contention. Video jobs must be asynchronous and preemptible or disabled during live mode.

### Failure Mode Playbook

Date added: 2026-06-26

Graceful degradation matrix:

| Failed component | Visual fallback path | Voice path | Stream impact | Operator visibility |
| --- | --- | --- | --- | --- |
| Fish Speech | Procedural mouth from existing voice/audio if available, otherwise no mouth movement | Pre-recorded fallback or silence | Degraded, but visuals continue | High through readiness probe |
| Procedural life | Static portrait with expression labels | Fish unaffected | Frozen look, audio OK | Medium |
| Real-time embodiment, MuseTalk/LivePortrait/Wav2Lip | Procedural only | Fish | Reduced lip/face quality | High if sidecar health exists |
| LTX/video loops | Procedural plus static portrait fallback | Fish | No quality loop boost | High through manifest/job status |
| Wan cinematic | LTX or procedural fallback | Fish | Lower production value | Medium |
| Observer video playback | Procedural or static only | Fish | Degraded visuals | High |
| Full ComfyUI | Procedural plus static portrait | Fish | Baseline alive mode | High |
| IPFS video retrieval | Local cache, lower-res cached variant, or static fallback | Fish | Possible loop downgrade | Medium to high if manifest reports fetch state |

Policy:

- The live Twitch stream must never go fully black or silent because a generative component failed.
- Every failure path must be explicitly coded and tested.
- Baseline mode should be Fish plus procedural/static avatar, independent of ComfyUI.

### Metrics And Evaluation Plan

Define "alive on Twitch" as measurable behavior rather than a vague impression.

Metrics:

- Perceived aliveness score: percentage of on-stream time with visible micro-movement while speaking or listening.
- Mouth reaction latency: Fish audio playback to visible mouth/expression reaction under 300ms target.
- Lip-sync quality: human preference score or phoneme-alignment proxy on fixed test utterances.
- Fish reliability: Fish synthesis success rate over 99% while background jobs are queued or running.
- Stream fallback robustness: stream continues with degraded visuals when Comfy, LTX, Wan, or lip-sync sidecar fails.
- Queue health: live voice queue wait remains near zero during background video generation.
- Visual consistency: identity drift and loop artifacts scored on generated assets before promotion to live use.
- Operator observability: `/ready` or diagnostics clearly reports Fish, base Comfy, LTX, Wan, lip-sync, and queue state.

Benchmark suite proposal:

- Add `runtime/tests/benchmarks/`.
- Track generation time per workflow, peak VRAM, output duration, output resolution, IPFS pin time, observer playback success, and visual consistency notes or score.

Testing harness proposal:

- Proposed module: `runtime/tests/benchmarks/avatar_liveness.py`.
- Automated checks:
  - end-to-end mouth reaction latency from Fish TTS/audio playback start to visible mouth amplitude change, target under 300ms;
  - procedural life frame rate for breathing, blink, and sway while Fish and background queue load are active, target at least 60 FPS in observer;
  - video loop switch seamlessness, measuring black-frame or stutter duration during manifest-driven swaps;
  - lip-sync proxy using fixed test utterances through the chosen embodiment layer, with saved frames for human review if automated scoring is not reliable;
  - resource contention test where live Fish synthesis runs while LTX/Wan jobs are queued, target Fish success rate at or above 99%.

Sample test utterance set:

- neutral: "The world is still listening."
- fast: "No, no, no, that was not the deal."
- emotional: "I endured the fracture and came back speaking."
- whisper/concede: "Fine. I will yield this once."
- sharp consonants: "Pick the lock, cut the thread, keep the proof."

Field evaluation:

- Each milestone should include a short Twitch/private OBS test recording.
- Attach measured results to this doc or a linked field report before promoting a technique to production.
- Record 5-10 minute private OBS/Twitch test streams after each milestone.
- Score segments on perceived aliveness from 0-10, emotional beat responsiveness, lip-sync quality, and viewer-retention proxy where available.
- Store raw VODs plus benchmark JSON alongside this audit or in a linked field report.

Exit rule:

- No technique advances to production without passing both automated harness checks and short VOD human review.

### Versioned Roadmap And Milestones

Milestone 0 - Foundation, 1-2 weeks:

- Fix avatar/voice test collection.
- Normalize endpoint/config drift.
- Add procedural life signals.
- Add basic video manifest schema.
- Add no-regression tests for current Fish and avatar state paths.

Exit criteria:

- Avatar/voice tests run.
- Runtime can emit breathing/blink/micro-sway state.
- Existing Twitch/observer flow still works with Comfy/Fish unavailable.

Milestone 1 - Visible Alive, 2-4 weeks:

- Add observer support for procedural life rendering.
- Evaluate one real-time embodiment candidate: LivePortrait, MuseTalk, or Wav2Lip.
- Add Fish-driven mouth amplitude or better mouth driver.
- Play at least one idle loop for one agent.

Exit criteria:

- Short Twitch/OBS VOD shows no frozen avatar during dialogue.
- Mouth reaction latency measured.
- Candidate real-time embodiment latency measured on target host.

Milestone 2 - Asset Factory:

- Implement `VideoGenerator`.
- Add LTX image-to-video loop workflow.
- Add GPU job queue.
- Pin generated video and store manifest CID.
- Observer selects pre-generated loop by agent/state.

Exit criteria:

- One LTX loop generated, fetched, pinned, and played in observer.
- Fish synthesis still succeeds while video jobs are queued.
- Queue metrics recorded.

Milestone 3 - Quality Layer:

- Add Wan cinematic workflow.
- Add LTX Lipdub or equivalent highlight workflow.
- Add full fallback logic for missing video assets.

Exit criteria:

- One Wan clip generated and stored without blocking live mode.
- One lipsynced highlight clip generated asynchronously.
- `/ready` distinguishes base Comfy, LTX, Wan, lip-sync, and Fish readiness.

Milestone 4 - Polish:

- Consume expression manifests in renderer or remove misleading expression-asset claims.
- Wire Fish prosody/voice parameters if supported by the deployed Fish endpoint.
- Improve observer blending, preloading, and crossfades.
- Run side-by-side visual evaluation: procedural only vs real-time embodiment vs LTX loop vs Wan clip.

Exit criteria:

- Updated benchmark report.
- Short Twitch test VOD.
- Documented go/no-go decision for each technique.

### Next 48-Hour Action Items

Date added: 2026-06-26

Immediate next steps:

1. Fix `banter.types` import blocker. This unblocks avatar/voice tests.
2. Add procedural life signals to `runtime/src/avatar/engine.py` or a new `runtime/src/avatar/life_signals.py`:
   - breathing phase;
   - blink timer;
   - micro head sway;
   - mouth amplitude from live audio when available.
3. Spin up ComfyUI locally or on the target GPU host and manually test one LivePortraitKJ or MuseTalk workflow.
4. Record actual latency, VRAM use, output quality, and provisioning issues from that manual test, then append observations to this document.
5. Draft `runtime/src/gpu/job_queue.py` skeleton with priority classes and unload hooks, even if not fully wired.
6. Update observer prototype to render basic procedural signals from runtime state.
7. Run one short Twitch/OBS test recording with procedural signals enabled and measure subjective alive improvement.

Success condition for 48 hours:

- Procedural breathing and blinking are visible on stream while Fish voice plays.
- At least one real-time embodiment candidate has been benchmarked on the target hardware or documented as blocked with exact provisioning errors.

Rationale:

- These steps deliver measurable Twitch improvement before heavy video generation code is written.
- They keep risk low by proving the live path first: Fish plus procedural/real-time embodiment.
- LTX/Wan remain background asset work until queueing, observer playback, and resource measurements are in place.
