# Avatar Runtime Pivot: Live2D

Parent issue: #91
Track issue: #157
Branch: `docs/157-live2d-pivot`
Status: planning and proof branch

## Decision Test

Live2D succeeds only if one browser-rendered avatar can recite the alphabet with live audio-driven mouth movement and agent-driven expression controls. The proof must show a real controllable puppet, not a prerecorded video and not a static portrait.

ComfyUI is not part of this speaking path. Live2D assets may be authored or loaded, but runtime speech and facial controls must be live.

## Upstream Fit

Live2D Cubism is built for 2D characters controlled by model parameters. The SDK supports rendering Cubism models and lip-sync workflows where audio volume or analysis is applied to mouth parameters. Cubism SDK for Web fits our browser/OBS path better than a GPU video-generation path.

Constraints:

- Cubism SDK/runtime and editor licensing must be reviewed before any production merge.
- The branch must use legally redistributable sample assets or document a local-only evaluation asset.
- We should not commit paid/proprietary model files unless their license explicitly allows it.

Primary references:

- https://www.live2d.com/en/sdk/about/
- https://www.live2d.com/en/sdk/license/
- https://docs.live2d.com/en/cubism-sdk-manual/lipsync/
- https://docs.live2d.com/en/cubism-sdk-tutorials/native-lipsync-from-wav-web/

## Current Code Leverage

The current repo already has the inputs a Live2D renderer needs:

- `observer/src/hooks/useWorld.js` turns Fish synthesis into browser playback state and updates `voicePlayback.mouthAmplitude` through a Web Audio analyser.
- `observer/src/lipSync.js` builds and samples the alphabet viseme track, so Live2D can start with volume-driven mouth open and later add text/phoneme-assisted mouth-form control.
- `observer/src/components/ControlledAvatar.jsx` already defines telemetry fields for proof: `data-avatar-control-mode`, `data-avatar-video-mode`, `data-voice-mouth-amplitude`, and `data-voice-lip-sync-source`.
- `observer/src/components/AgentAvatar.jsx` already routes minimal `/one` away from portrait/video fallback into a controllable avatar component.
- `/one` already forbids bundled prerecorded avatar video; that invariant must remain.

## Features To Capitalize On

- Web runtime: Cubism SDK for Web can live in the current Vite/browser/OBS surface.
- Parameter-level control: mouth, eyes, brows, head/body angle, breathing, expressions, motions, and model-specific parameters.
- Lip sync: official SDK workflows support applying real-time audio volume to lip-sync parameters such as mouth-open controls.
- Motion layering: expression and motion clips can be layered over speech without generating video.
- Asset-specific parameter maps: each model can expose a safe allowlist for agent commands.

## Unique Use Case

Expressive 2D cartoon hosts: clean talking-head and half-body characters with direct control over mouth shape, smile, eyes, brows, head tilt, body angle, breathing, and emotion states.

This is the strongest candidate for a fast, polished `/one` proof if the goal is "one avatar speaks naturally live."

## Proposed Pipeline

1. Observer loads a Cubism model through a Live2D Web renderer.
2. Runtime/Fish supplies live audio and utterance metadata.
3. Browser audio analyser computes mouth amplitude in real time.
4. Optional viseme layer maps known text/phonemes into mouth shapes when available.
5. Agent controls drive Cubism parameters:
   - mouth open;
   - mouth form;
   - eye open;
   - brow angle;
   - head X/Y/Z;
   - body angle;
   - breathing;
   - expression or motion clip.
6. OBS captures the browser stage as it does today.
7. Proof capture records screenshot, video, mouth telemetry, audio status, and parameter-command logs.

## Agent Command Contract

```json
{
  "agent_id": "fish",
  "utterance_id": "alphabet-run-001",
  "controls": [
    {"type": "live2d.parameter", "name": "ParamMouthOpenY", "value": 0.82},
    {"type": "live2d.parameter", "name": "ParamMouthForm", "value": 0.2},
    {"type": "live2d.parameter", "name": "ParamAngleX", "value": -7.5},
    {"type": "live2d.expression", "name": "confident"},
    {"type": "live2d.motion", "group": "gesture", "name": "counting"}
  ]
}
```

The bridge should expose a safe allowlist of parameters for each model, because Cubism models can differ in parameter names and ranges.

## Implementation Plan

1. Pick a legally usable sample Cubism model for local proof.
2. Add a Live2D observer proof route or runtime flag, separate from the current `/one` default until stable.
3. Implement a parameter mapper from GOD avatar controls to Cubism parameters.
4. Wire existing audio analyser mouth amplitude into the Cubism mouth-open parameter.
5. Add expression/motion controls for blinks, head movement, and one or two gestures.
6. Run the alphabet proof and record screenshot/video artifacts.

## Validation

- Browser proof must show live mouth movement synchronized to audible alphabet speech.
- Parameter logs must show nonzero mouth changes during audio playback.
- The avatar must visibly blink or change expression from a live control path.
- Sample asset licensing must be documented.
- No generated/prerecorded avatar video may drive the speaking result.

## Merge Gate

Merge only if Live2D produces a better live `/one` proof than the current procedural rig and the license/asset policy is acceptable for an open-source repository. If licensing blocks mainline use, preserve the branch as an optional integration path and keep the open VRM track moving.
