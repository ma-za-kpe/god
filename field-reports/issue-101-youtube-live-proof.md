# Issue #101 YouTube Live Proof Readiness

Date: 2026-06-27
Parent: #91
Status: YouTube `/one` live proof captured

## Scope

Issue #101 requires a YouTube-first OBS/private stream proof where Fish voice,
procedural life, captions, and fallback state are visible. The initial pass was
code-only; later Vast field runs added OBS, Fish, runtime, and rendered-stage evidence.

## Code Contract Added

- Readiness report: `runtime/src/broadcast/live_proof.py`
- Runtime endpoint: `GET /broadcast/youtube-proof`
- Contract tests: `runtime/tests/test_youtube_live_proof.py`

The report is a pure projection over supplied snapshot state. It does not call
OBS, YouTube, Fish, ComfyUI, IPFS, or GPU services by itself.

## Required Checks

- Fish voice is configured and has audio evidence.
- Avatar visual source is available.
- Procedural life signals are visible.
- Mouth state reacts while voice is active.
- Captions are present.
- Comfy/video failure degrades to a visual fallback instead of a black stage.

The GPU queue state is surfaced as an advisory so live YouTube tests can keep
background LTX/Wan/offline video work disabled.

## Vast.ai Field Run - 2026-06-28

Instance: Vast.ai `42507936`, RTX A6000.

Deployed commit: `aa91102`.

Run window:

- OBS RTMP stream start: `2026-06-28 14:52:25 UTC`.
- Captured proof snapshot after `00:06:38.166` stream time.
- OBS streaming status: `streaming=true`.
- OBS output: `1280x720`, `30 FPS`, x264.
- OBS encoder log: `keyint: 60`.
- OBS custom x264 settings: `keyint=60 min-keyint=60 scenecut=0`.
- OBS output skipped frames at capture: `0`.
- OBS render path still reports high render-missed frames on the headless/Xvfb host;
  treat this as a performance follow-up before public production.

Runtime readiness at capture:

- `/ready`: `ok=true`, `status=ready`.
- Fish TTS probe: `ok=true`, `byte_count=94252`.
- ComfyUI probe: `ok=true`.
- IPFS probe: `ok=true`.
- Agents: `8/8` alive, all with avatar CIDs and voice reference CIDs.

Voice evidence at capture:

- Provider: `fish`.
- Model: `fish-speech-s2-pro`.
- Synthesis: `ok=true`, `content_type=audio/wav`.
- Audio bytes: `192556`.
- Audio RMS: `0.111411`.
- Mouth amplitude: `0.36488`.

`/broadcast/youtube-proof` at capture:

- Status: `degraded_private_test_ready`.
- `ready_for_private_stream=true`.
- Required checks passing:
  - `fish_voice_audio`.
  - `avatar_visual_available`.
  - `procedural_life_visible`.
  - `mouth_reacts_to_voice`.
  - `captions_visible`.
  - `comfy_video_optional`.
- Operator state:
  - `visual_mode=portrait_fallback`.
  - `voice_mode=fish_audio`.
  - `caption_mode=captioned`.
  - `black_screen_risk=false`.
  - `silence_risk=false`.
- Advisory still false: `background_video_jobs_disabled_for_live`, because background jobs
  are allowed with queue depth `0`.

VOD status:

- The host has `YOUTUBE_ENABLED=true`, `YOUTUBE_DRY_RUN=false`, and OBS is connected to
  YouTube RTMP.
- `YOUTUBE_BROADCAST_ID` is not configured.
- `YOUTUBE_AUTO_GO_LIVE` is not configured.
- The restart script therefore leaves YouTube Studio/manual go-live as the final step.
- No VOD URL was available to link from the runtime or YouTube API during this run.

## Remaining Blocker

The issue cannot close until a real private YouTube/OBS run records:

- a 5-10 minute VOD;
- benchmark JSON or notes;
- visible Fish voice plus procedural life;
- visible captions and live/fallback operator state;
- no black or silent stream when Comfy/video is unavailable.

## Post-LTX/Wan Field Run Update - 2026-06-28

After PRs #142-#144 and the #99/#100 offline video generation run, Vast was restored to
the live stream path on commit `18d1843`.

Verified after restart:

- `GPU_BACKGROUND_JOBS_ALLOWED=false` was exported by the Vast runtime stage.
- `/diagnostics/gpu` reported `background_jobs_allowed=false`, queue depth `0`, and no
  active GPU job.
- A fresh `/ready` probe on runtime port `8888` returned `ok=true` with no failed checks.
- OBS was already streaming and the restart script restarted the RTMP stream to clear
  stale ingest state.
- Fish S2-Pro restarted and a direct synthesis probe returned `86060` WAV bytes.
- `/broadcast/youtube-proof` reached `degraded_private_test_ready` at
  `2026-06-28 17:49:56 UTC` with no failed checks.

Additional rendered proof captured from the Vast Xvfb display at `2026-06-28 18:10:09 UTC`:

- Live stage screenshot:
  `field-reports/assets/2026-06-28-vast-video-proof/live-surface-20260628-181009.png`
- Live stage 8 second capture:
  `field-reports/assets/2026-06-28-vast-video-proof/live-surface-20260628-181009.mp4`

The first capture showed OBS live and the stage rendering, but also exposed the browser's
`AUDIO MUTED` overlay. The stage was clicked on the Vast display to unlock browser audio,
then the final screenshot/video were captured. The final screenshot was visually inspected
and shows the ensemble stage, `OBSERVER LIVE runtime healthy`, procedural mouth bars, and
no audio-muted overlay.

Remaining caveat:

- Fish S2-Pro can still take longer than the 90 second `/ready` synthesis probe when it is
  already busy generating speech. Later proof/readiness probes intermittently fell back to
  `voice_fallback` while Fish completed long TTS requests. Treat this as a #101 field
  stability issue; it does not block #99/#100 video asset acceptance.

## YouTube `/one` Live Proof - 2026-07-02

Instance: Vast.ai `43411625`, RTX PRO 6000 S.

Merged code:

- PR #148 merged into `main` at `cf44033`.
- Vast checkout synced to `main` at `cf44033`.

Live broadcast:

- YouTube video ID: `xiypwf59Ho0`.
- Watch URL: `https://www.youtube.com/watch?v=xiypwf59Ho0`.
- Studio URL: `https://studio.youtube.com/video/xiypwf59Ho0/livestreaming`.
- YouTube API state at final check: `lifeCycleStatus=live`.
- Bound stream state at final check: `streamStatus=active`.
- OBS status at final check: `streaming=true`, stream timecode over `00:22:00`.

Live `/one` proof:

- Runtime `/ready`: `ok=true`; Fish, ComfyUI, IPFS, OBS dependencies healthy.
- Voice plan line: `A B C D E F G H I J K L M N O P Q R S T U V W X Y Z.`
- Fish synthesis evidence: `audio_byte_count=712748`, `duration_seconds=8.080544`,
  `audio_rms=0.155328`.
- Final Pulse/OBS proof clip audio: `mean_volume=-19.5 dB`, `max_volume=-2.8 dB`.
- Final OBS scene: `god-display` XSHM display capture rendered, `god-audio` PulseAudio
  monitor rendered, stale `god-browser` xcomposite source hidden.

Proof artifacts:

- Final screenshot:
  `field-reports/assets/2026-07-02-one-live-proof/one-youtube-live-final-clean-audio.png`
- Final 12 second capture:
  `field-reports/assets/2026-07-02-one-live-proof/one-youtube-live-final-clean-audio.mp4`

Observed fixes from this run:

- The original broadcast ID was already `complete`; YouTube rejected it as not
  transitionable. A fresh broadcast was created and bound to the active default stream.
- A fresh broadcast created while OBS was already ingesting remained stuck at `ready`.
  The successful sequence was: stop OBS ingest, wait for the stream to become inactive,
  create and bind the broadcast, restart OBS ingest, wait for active ingest, then
  transition the broadcast live.
- Firefox's sandbox-disabled browser chrome warning was removed from the live capture by
  launching the Vast Firefox profile without `MOZ_DISABLE_CONTENT_SANDBOX=1`.
