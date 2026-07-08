# Local Browser Avatar Lab

Date: 2026-07-08
Branch: `feat/local-browser-avatar-lab`

## Goal

Build a local, browser-first avatar pipeline that can become continuous
LLM-directed video. The first proof runs in the browser, talks to local Ollama,
and does not require Fish Speech, ComfyUI, OBS, Vast, YouTube, Twitch, or strict
agent birth paths.

## Prime Rule

Hard-coded avatar behavior is allowed only as an explicit test fallback before
the LLM is connected. It is not the product path. Code owns the schema and
clamps unsafe values; the LLM owns the dialogue, camera/framing, mood, gesture,
gaze, full-body pose, hair, face, hands/fingers, wardrobe/body presentation,
lighting, stage, and every exposed renderer node.

This rule is also recorded in `AGENTS.md`, `.kiro/steering/avatar-lab.md`, and
the gap tracker in `docs/92-avatar-lab-gap-tracker.md`.

## Current Local Proof

The browser route is `/avatar-lab`.

It provides:

- A local Three.js avatar surface using the existing `ControlledAvatar` adapter.
- A local TalkingHead human GLB default at `observer/public/assets/avatars/brunette.glb`;
  remote Ready Player Me URLs are optional overrides, not the default.
- A constrained `avatar_intent` schema for LLM-directed behavior.
- Ollama browser calls for dialogue plus camera, mood, gesture, gaze, full-body
  pose, hair, face, hands/fingers, wardrobe, lighting, stage, and node intent.
- Browser speech as the first cheap audio proof.
- A visible JSON panel and hidden telemetry for renderer assertions.
- A manual `Test` fallback for renderer debugging only.

Start it on Windows:

```powershell
.\scripts\start-local-avatar-lab.ps1 -OpenBrowser
```

Dry run:

```powershell
.\scripts\start-local-avatar-lab.ps1 -DryRun
```

Direct URL:

```text
http://localhost:3000/avatar-lab?ollama=http%3A%2F%2Flocalhost%3A11434&model=llama3.1%3A8b
```

## Intent Contract

The live path is:

```text
LLM -> avatar_intent JSON -> validator/clamps -> renderer adapter -> browser video/audio
```

The renderer may clamp, reject, or degrade unsafe values. It should not invent
the performance when the LLM is available.

Initial fields:

- `voice.line`
- `voice.energy`
- `mood`
- `gesture`
- `gaze`
- `tempo`
- `hair.bend`
- `hair.sway`
- `hands.leftFingerCurl`
- `hands.rightFingerCurl`
- `hands.openPalm`
- full-body renderer bones such as head, neck, spine, hips, arms, hands,
  fingers, and legs when the renderer publishes them
- `face.brow`
- `face.smile`
- `appearance.avatar`
- `appearance.outfit`
- `appearance.palette`
- `appearance.accessory`
- `appearance.description`
- `nodes[]` for bounded per-node control against the renderer-published node
  registry

The next step is to make this contract the common adapter surface for
TalkingHead, MotionEngine, VRM, HeadTTS, HeadAudio, and future GPU sidecars.

Node control rule: the LLM should be able to control every exposed avatar node,
but only through the current renderer registry and bounded controls. It does not
get raw arbitrary JavaScript, shader, URL, or filesystem write access.

## Prompt Engineering Standard

The avatar prompt path must stay modular and testable:

- Prompt construction lives outside UI components.
- The system prompt defines the role, output-only-JSON rule, renderer registry
  grounding, and safety boundary.
- The user prompt includes requested line, previous intent, allowed enums,
  available node ids, and required JSON shape.
- Ollama requests use JSON mode, bounded generation options, and keep-alive.
- Invalid or incomplete model output gets one repair attempt with the exact
  parser error.
- Deterministic heuristics remain explicit test fallbacks only.

Software engineering standard:

- Keep `avatar_intent` as the stable contract.
- Keep renderers as adapters from intent to concrete APIs.
- Unit-test schema normalization, prompt construction, response parsing, and
  renderer-independent behavior.
- Do not bury behavior in React components when it belongs in a contract,
  parser, or adapter module.

## Library Inventory From Research

### Adopt Now

- TalkingHead: browser/Three.js realtime 3D avatar, lip sync, moods, gestures,
  Mixamo animation, ARKit/Oculus visemes, dynamic bones, morph target access.
  Best fit for local browser renderer and detailed control.
  URL: https://github.com/met4citizen/TalkingHead
- MotionEngine: semantic motion layer for TalkingHead. Best fit for the LLM
  control boundary because it maps named motions and safe JSON onto renderer
  behavior instead of asking the LLM to write raw bone values.
  URL: https://github.com/lhupyn/motion-engine
- HeadTTS: Kokoro ONNX in browser or Node, with phoneme timing and Oculus
  viseme output. Best fit for the first real TTS swap after browser speech.
  URL: https://github.com/met4citizen/HeadTTS
- HeadAudio: browser audio worklet for realtime audio-driven viseme detection.
  Good fallback when a TTS source lacks timestamps.
  URL: https://github.com/met4citizen/HeadAudio

### Sidecar Later

- OpenAvatarChat: full modular ASR/LLM/TTS/avatar/WebRTC stack. Use as
  architecture reference and possible duplex sidecar source, not the local
  default.
  URL: https://github.com/HumanAIGC-Engineering/OpenAvatarChat
- LiteAvatar: lightweight realtime 2D audio-to-face model. Useful CPU sidecar
  candidate, but not the deep 3D hand/hair control path.
  URL: https://github.com/HumanAIGC/lite-avatar
- LAM_Audio2Expression: audio to ARKit blendshape expressions. Useful bridge
  for realistic 3D face control.
  URL: https://github.com/aigc3d/LAM_Audio2Expression
- MuseTalk: high-quality realtime lip-sync sidecar. Useful for lips/video, not
  full semantic body control.
  URL: https://github.com/TMElyralab/MuseTalk
- FasterLivePortrait: optimized portrait animation with ONNX/TensorRT paths.
  Useful GPU sidecar candidate for portrait video.
  URL: https://github.com/warmshao/FasterLivePortrait
- LivePortrait: efficient portrait animation baseline.
  URL: https://github.com/KlingAIResearch/LivePortrait
- SoulX-FlashHead: high-fidelity realtime streaming talking head. Strong future
  GPU/cloud candidate, too heavy for default local lab.
  URL: https://github.com/Soul-AILab/SoulX-FlashHead
- SadTalker: single portrait plus audio to talking-head video. Useful offline
  baseline, not realtime body control.
  URL: https://github.com/OpenTalker/SadTalker
- Wav2Lip: lip-sync baseline and benchmark only.
  URL: https://github.com/Rudrabha/Wav2Lip
- Linly-Talker: full digital human pipeline that integrates several talker
  models. Useful reference, too broad for default local lab.
  URL: https://github.com/Kedreamix/Linly-Talker

### Reference Only

- FLAME / 3DMM: important face representation layer for future realism.
  URL: https://github.com/soubhiksanyal/FLAME_PyTorch
- NeRF and 3D Gaussian Splatting avatar projects: future photorealism lane, not
  the first browser proof.
- FaceVid2Vid-style warping, ExpNet, PoseVAE: model-family concepts already
  represented in SadTalker-style systems.
- Unity/Unreal: deeper production engines, not needed for the local browser
  proof.
- gradio-webrtc / FastRTC: useful when browser-to-Python sidecars need WebRTC.
  URL: https://github.com/HumanAIGC-Engineering/gradio-webrtc
- wind-comic, Anim-Director, AniMaker, AniME, AnimeAgent: useful offline
  storyboard or animation-generation references, not live avatar control.
- Fish Speech, ComfyUI, OBS, Vast: production and cloud lanes. They remain
  opt-in and are not local lab defaults.

## Architecture

Stage A: local browser proof.

- `/avatar-lab`
- `avatar_intent` schema
- Ollama-generated intent
- browser speech fallback
- existing procedural/VRM renderer adapter

Stage B: browser avatar stack.

- Add TalkingHead behind a renderer flag.
- Add MotionEngine as the semantic motion adapter.
- Map `avatar_intent` onto TalkingHead `setMood`, `playGesture`, `playPose`,
  morph targets, full-body bone overlays, and dynamic bones.

Stage C: local TTS and visemes.

- Add HeadTTS as Kokoro browser/Node TTS.
- Feed HeadTTS visemes/timestamps to TalkingHead or the existing rig.
- Add HeadAudio as fallback audio-to-viseme when timestamps are missing.

Stage D: optional sidecars.

- LiteAvatar for low-end CPU 2D face proof.
- LAM_Audio2Expression for ARKit expression bridge.
- MuseTalk/FasterLivePortrait/SoulX-FlashHead for GPU portrait video.
- OpenAvatarChat or gradio-webrtc when duplex streaming is needed.

## Non-Goals For This Branch

- Do not make Fish Speech or ComfyUI required for local avatar iteration.
- Do not require `/creator/one`, avatar genesis, OBS, Vast, or stream setup.
- Do not let the LLM issue raw unbounded bone/morph commands.
- Do not treat deterministic sample behavior as the live product path.
