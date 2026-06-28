# Issue #99/#100 Video Model Readiness Field Check

Date: 2026-06-28
Parent: #91
Issues: #99, #100
Status: runtime preflight hardened; real LTX/Wan/LipDub generation blocked by missing Comfy nodes/models

## Vast.ai Host

- Instance: `42507936`
- GPU: NVIDIA RTX A6000, 48 GB VRAM
- Deployed commit: `58bd8e1`
- Free disk at inspection: about 152 GB
- ComfyUI endpoint: `http://localhost:8188`

## What Is Present

ComfyUI is running and reports `794` node classes through `/object_info`.

The host has base Comfy video blueprints under `/opt/ComfyUI/blueprints`, including:

- `Image to Video (LTX-2.3).json`
- `Text to Video (LTX-2.3).json`
- `Image to Video (Wan 2.2).json`
- `Text to Video (Wan 2.2).json`

Base Comfy includes some Wan node support:

- `WanImageToVideo` is present.

## What Is Missing

The runtime workflow templates still require node classes that are not installed on the host:

- `LoadImageFromIPFS`
- `LoadAudioFromIPFS`
- `LTXImageToVideo`
- `LTXLipDub`
- `VHS_VideoCombine`

Model storage inspection found SDXL only in active model directories. No LTX, Wan, or LipDub
model files were installed under the expected Comfy model folders.

## Live Runtime Preflight

After PR #139, `VideoGenerator` checks Comfy `/object_info` before submitting video jobs.
The live Vast preflight now fails explicitly before queueing or submitting impossible jobs:

```json
{
  "ltx": {
    "ok": false,
    "error": "missing_comfy_nodes:LoadImageFromIPFS,LTXImageToVideo,VHS_VideoCombine"
  },
  "wan": {
    "ok": false,
    "error": "missing_comfy_nodes:LoadImageFromIPFS,VHS_VideoCombine"
  },
  "lipdub": {
    "ok": false,
    "error": "missing_comfy_nodes:LoadImageFromIPFS,LoadAudioFromIPFS,LTXLipDub,VHS_VideoCombine"
  }
}
```

## Issue Impact

#99 cannot close yet because no real LTX loop was generated, pinned, or registered.

#100 cannot close yet because no real Wan cinematic clip or LTX LipDub/highlight clip was
generated, pinned, or registered.

The current blocker is provisioning/template alignment, not queue orchestration:

- either install the custom nodes expected by the runtime templates;
- or replace the runtime templates with API-format workflows that use the built-in Comfy
  LTX/Wan blueprint node classes;
- and install the required LTX/Wan/LipDub model files before retrying generation.

## Validation

- Docker focused tests: `runtime/tests/test_video_generator_ltx.py` and
  `runtime/tests/test_video_generator_quality.py` passed (`9 passed`).
- Scoped pre-commit for `runtime/src/avatar/video_generator.py` and
  `runtime/tests/test_video_generator_ltx.py` passed.
- PR #139 CI/security/pre-commit checks passed.
