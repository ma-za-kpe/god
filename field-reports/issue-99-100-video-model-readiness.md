# Issue #99/#100 Video Model Readiness Field Check

Date: 2026-06-28
Parent: #91
Issues: #99, #100
Status: LTX and Wan field generation passed; LipDub remains explicitly blocked

## Vast.ai Host

- Instance: `42507936`
- GPU: NVIDIA RTX A6000, 48 GB VRAM
- Deployed commit after fixes: `18d1843`
- Field report and proof assets synced on `main` at `b4e177c`
- ComfyUI endpoint: `http://localhost:8188`
- IPFS API: `http://localhost:5001`
- Disk after model install and field runs: about 67 GB free on the 220 GB root volume

## Installed Comfy Support

ComfyUI reported `1156` node classes after installing the video custom nodes.

Required node availability:

- `LoadImage`: present
- `SaveVideo`: present
- `CreateVideo`: present
- `LTXVImgToVideoInplace`: present
- `WanImageToVideo`: present
- `LoadAudio`: present
- `LTXLipDub`: not present

Installed model files included:

- LTX: `ltx-2.3-22b-dev-fp8.safetensors`
- LTX text encoder: `gemma_3_12B_it_fp4_mixed.safetensors`
- LTX LoRA: `ltxv/ltx2/ltx-2.3-22b-distilled-lora-384.safetensors`
- LTX upscaler: `ltx-2.3-spatial-upscaler-x2-1.1.safetensors`
- Wan low/high diffusion models: `wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors`,
  `wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors`
- Wan LoRAs: `wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors`,
  `wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors`
- Wan text encoder: `umt5_xxl_fp8_e4m3fn_scaled.safetensors`
- Wan VAE: `wan_2.1_vae.safetensors`

## Workflow Fixes Validated

Field generation exposed live Comfy schema requirements that static node-presence checks do not catch.
The runtime workflows were aligned through PRs #143 and #144:

- LTX: added required resize, preprocess, strength, LoRA strength, CFG, and tiled VAE inputs.
- Wan: added required LoRA strength, sampler control, batch, FPS, and `ModelSamplingSD3.shift` inputs.

## #99 LTX Loop Result

Input portrait CID:

- `QmWxZbQXziZGVrdFehBTdfJi3pFoehPDvPCAV2tEumrehn`

Generated output:

- Filename: `god_ltx_avatar_loop_00001_.mp4`
- Proof video:
  `field-reports/assets/2026-06-28-vast-video-proof/god_ltx_avatar_loop_00001_.mp4`
- Proof frame:
  `field-reports/assets/2026-06-28-vast-video-proof/ltx-avatar-loop.png`
- Prompt ID: `dc449bf7-f70b-4660-918e-317e82988b7e`
- Runtime: `154.575` seconds
- Output bytes: `98703`
- Content type: `video/mp4`
- Pinned CID: `bafkreidbdx66etbmvllhlxu6yybefrm6gc5piw26tttvawgp7wczfi6z2u`

Manifest asset:

- Asset ID: `ltx-a4bf1ce0-a62b-432c-8bdc-184a051fb666-1782667625`
- Variant: `low_res_live`
- Resolution: `512x288`
- Duration: `1000 ms`
- Status: `ready`
- Motion: `subtle breathing idle loop, natural blink, slight head sway, living portrait`

GPU/disk:

- Before: `269 MiB` used, `48283 MiB` free
- After: `36773 MiB` used, `11779 MiB` free
- Disk after run: about `67 GB` free

## #100 Wan Result

Input portrait CID:

- `QmWxZbQXziZGVrdFehBTdfJi3pFoehPDvPCAV2tEumrehn`

Generated output:

- Filename: `god_wan_cinematic_00001_.mp4`
- Proof video:
  `field-reports/assets/2026-06-28-vast-video-proof/god_wan_cinematic_00001_.mp4`
- Proof frame:
  `field-reports/assets/2026-06-28-vast-video-proof/wan-cinematic.png`
- Prompt ID: `df30f3c0-7aea-4e03-ba99-0bc6a617ca9c`
- Runtime: `53.38` seconds
- Output bytes: `180868`
- Content type: `video/mp4`
- Pinned CID: `bafkreih42kgyvihcriiuznswvbofyos7tfxvhamw2sneevx7ocuogfchci`

Manifest asset:

- Asset ID: `wan-a4bf1ce0-a62b-432c-8bdc-184a051fb666-1782668089`
- Variant: `high_res_highlight`
- Resolution: `512x288`
- Duration: `1000 ms`
- Status: `ready`
- Motion: `slow cinematic breathing and head movement`

GPU/disk:

- Before: `269 MiB` used, `48283 MiB` free
- After: `34375 MiB` used, `14177 MiB` free
- Disk after run: about `67 GB` free

## LipDub Status

LipDub remains explicitly blocked, which satisfies the #100 acceptance branch that allows a measured blocker:

- The installed Comfy environment does not expose `LTXLipDub`.
- The available ComfyUI-LTXVideo path is an IC-LoRA source-video workflow, not the
  portrait-plus-audio node assumed by the first runtime skeleton.
- The attempted LipDub IC-LoRA model URL returned HTTP 401 during provisioning.
- Runtime workflow `ltx_lipdub_highlight.json` therefore fails closed with
  `workflow_disabled:ltx_lipdub_requires_source_video_workflow`.

## Live Safety

Before offline video generation, Vast live runtime was restarted from `main` with
`GPU_BACKGROUND_JOBS_ALLOWED=false`. `/diagnostics/gpu` reported:

```json
{
  "background_jobs_allowed": false,
  "queue_depth": 0,
  "current_job": null
}
```

The post-generation stream restart restored Fish, runtime, and OBS. A proof snapshot at
`2026-06-28 17:49:56 UTC` reported `degraded_private_test_ready` with no failed checks and
`background_video_jobs_disabled_for_live` passing. Later proof/readiness probes showed Fish
can still time out while S2-Pro is busy; this remains a #101 field stability caveat, not a
new #99/#100 blocker.

Rendered proof captured after the post-generation restart:

- Live stage screenshot:
  `field-reports/assets/2026-06-28-vast-video-proof/live-surface-20260628-181009.png`
- Live stage 8 second capture:
  `field-reports/assets/2026-06-28-vast-video-proof/live-surface-20260628-181009.mp4`

The screenshot was visually inspected and shows the Firefox stage rendering the ensemble,
`OBSERVER LIVE runtime healthy`, active procedural mouth bars, and no browser audio-muted
overlay after the stage was clicked to unlock audio.

## Validation

- Docker focused tests:
  `tests/test_video_generator_ltx.py tests/test_video_generator_quality.py tests/test_gpu_job_queue.py`
  passed (`18 passed`, one existing websockets warning).
- Full `python -m pre_commit run --all-files` passed for PRs #142, #143, and #144.
- GitHub checks passed for PRs #142, #143, and #144.
