# Avatar Runtime Pivot: Spine

Parent issue: #91
Track issue: #159
Branch: `docs/159-spine-pivot`
Status: planning and proof branch

## Decision Test

Spine succeeds only if a live browser or engine-rendered puppet can recite the alphabet with live Fish audio, mouth-slot changes, expression changes, and gesture animation tracks driven by runtime state.

The proof must not use a prerecorded video. It must show a controllable 2D skeletal puppet.

## Upstream Fit

Spine is a 2D skeletal animation system with runtimes for many engines and web surfaces. It is strong when artists author reusable character rigs, mouth slots, gestures, prop interactions, and blended animation states.

The fit is strongest as a polished 2D puppet track, not as a generated-video track.

Primary references:

- https://en.esotericsoftware.com/spine-runtimes
- https://github.com/EsotericSoftware/spine-runtimes
- https://en.esotericsoftware.com/spine-player

## License Gate

Spine runtime source is available, but use and redistribution are governed by Spine's runtime/editor license. This branch must document whether the repo can ship a Spine proof, which assets can be committed, and whether contributors need a paid editor license to reproduce the work.

If licensing is not open-source-friendly enough for `main`, keep this as an optional integration or benchmark.

## Current Code Leverage

- `observer/src/hooks/useWorld.js` already supplies live audio playback state and Web Audio-derived `mouthAmplitude`.
- `observer/src/lipSync.js` can become a generic mouth-slot scheduler for 2D puppet attachments, not just VRM visemes.
- `observer/src/components/AgentAvatar.jsx` already splits minimal `/one` rendering from portrait/video fallback, so a Spine renderer can be tested without touching the stage portrait path.
- `observer/src/components/ControlledAvatar.jsx` already defines the useful control concepts: mouth, blink, breath, head motion, speaking state, and proof telemetry.
- Existing `/one` proof requirements apply unchanged: live Fish audio, no prerecorded video, screenshots, video, and telemetry.

## Features To Capitalize On

- Authored 2D skeletal animation with reusable bones, slots, skins, constraints, events, and animation timelines.
- Animation blending through state tracks, useful for speaking while gesturing or reacting.
- Procedural skeleton manipulation at runtime, useful for mouth scale/slot changes, eye/brow offsets, head/torso motion, and gesture overlays.
- Web, Three.js, Godot, Unity, and other runtime targets, which makes Spine useful as a cross-runtime asset format if licensing allows it.
- Deterministic exported skeleton and atlas data, useful for replayable show timing.

## Unique Use Case

Polished authored 2D debate-show puppets: reusable hosts with expressive mouth slots, brows, arms, props, interruption reactions, and animation-state blending.

This is the candidate for "cartoon-quality reusable 2D characters with strong authored gestures."

## Proposed Pipeline

1. Runtime/Fish produces live audio, utterance IDs, line text, and synthesis metadata.
2. Browser audio analyser updates `voicePlayback.mouthAmplitude`.
3. `lipSync.js` produces alphabet/mouth-slot timing.
4. Spine renderer maps state into:
   - mouth slot/attachment changes;
   - mouth bone scaling;
   - blink/eye state;
   - expression skins;
   - gesture animation tracks;
   - idle/breath overlays.
5. Agent commands select safe animation names and tracks.
6. Proof capture records screenshot, video, telemetry, and animation-state logs.

## Agent Command Contract

```json
{
  "agent_id": "fish",
  "utterance_id": "alphabet-run-001",
  "controls": [
    {"type": "spine.slot", "name": "mouth", "attachment": "mouth_aa"},
    {"type": "spine.track", "track": 1, "animation": "gesture_counting", "loop": false},
    {"type": "spine.bone", "name": "head", "rotation": -4.0},
    {"type": "spine.skin", "name": "confident"}
  ]
}
```

The implementation should allowlist skeleton slots, bones, skins, and animation names per puppet.

## Implementation Plan

1. Identify a legal sample/evaluation Spine asset and document whether it can be committed.
2. Add a minimal browser proof using Spine Player or a web runtime compatible with the current observer.
3. Map `mouthAmplitude` and alphabet visemes into mouth slots or bone scaling.
4. Add one gesture animation track layered over the speaking track.
5. Record A-Z proof and compare quality against Live2D and VRM.

## Validation

- Browser proof must show live speech-driven mouth changes.
- Animation-state logs must show active speaking and gesture tracks.
- Sample asset/editor licensing must be documented.
- No generated/prerecorded avatar video may drive the speaking result.

## Merge Gate

Merge only if the licensing story is acceptable and the proof quality justifies the authoring overhead. If not, use findings from this track to improve Live2D/VRM/Godot control schemas.
