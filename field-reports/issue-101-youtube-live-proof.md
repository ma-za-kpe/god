# Issue #101 YouTube Live Proof Readiness

Date: 2026-06-27
Parent: #91
Status: code path added, VOD not yet recorded

## Scope

Issue #101 requires a YouTube-first OBS/private stream proof where Fish voice,
procedural life, captions, and fallback state are visible. The current pass is
code-only: no Vast.ai host, OBS stream start, model loading, or YouTube VOD run.

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

## Remaining Blocker

The issue cannot close until a real private YouTube/OBS run records:

- a 5-10 minute VOD;
- benchmark JSON or notes;
- visible Fish voice plus procedural life;
- visible captions and live/fallback operator state;
- no black or silent stream when Comfy/video is unavailable.
