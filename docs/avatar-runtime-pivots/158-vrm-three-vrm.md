# Avatar Runtime Pivot: VRM / three-vrm

Parent issue: #91
Track issue: #158
Branch: `docs/158-vrm-three-vrm-pivot`
Status: planning and proof branch

## Decision Test

VRM/three-vrm succeeds only if `/one` can show one real 3D avatar reciting the alphabet live with mouth movement, blink, gaze/head motion, and at least one non-mouth gesture or expression driven by live runtime state.

This path must not use a PNG, a portrait fallback, or prerecorded/generated video as the speaking proof.

## Upstream Fit

VRM is a glTF-based avatar format for humanoid 3D avatars. It standardizes humanoid pose, facial expressions, gaze, material conventions, spring bones, and avatar metadata/license information. `@pixiv/three-vrm` plugs VRM loading and runtime control into Three.js through `GLTFLoader` and `VRMLoaderPlugin`.

This is the most direct open 3D path because it aligns with the existing observer stack.

Primary references:

- https://vrm-consortium.org/en/
- https://vrm.dev/en/vrm/vrm_features/
- https://github.com/pixiv/three-vrm

## Current Code Leverage

This branch starts from code already on `main`:

- `observer/package.json` already depends on `@pixiv/three-vrm`, `three`, `@react-three/fiber`, and `@react-three/drei`.
- `observer/src/components/ControlledAvatar.jsx` already imports `VRMLoaderPlugin` and `VRMUtils`.
- `observer/src/components/WorldMap.jsx` already passes `agent.vrm_avatar_url`, `snapshot.avatar?.vrm_avatar_url`, or `VITE_DEFAULT_VRM_URL`.
- `observer/src/lipSync.js` already produces VRM-style viseme weights for `aa`, `ih`, `ou`, `ee`, and `oh`.
- The procedural fallback in `ControlledAvatar.jsx` already models jaw, mouth, blink, brows, breath, head sway, and speech telemetry.
- `runtime/tests/test_observer_react_one_static.py` already asserts that `/one` uses a controllable rig and not a bundled video loop.

## Features To Capitalize On

- Browser-native Three.js integration with the current React observer.
- VRM expression manager for blink, emotion, and mouth-shape control.
- Standard humanoid bone mapping for head, neck, arms, hands, torso, and full-body pose.
- Gaze/look-at and spring-bone conventions for livelier motion.
- Avatar metadata/license fields that can support asset policy checks.
- Existing glTF pipeline compatibility for future Godot/AI4AnimationPy bridge work.

## Unique Use Case

Open browser-native 3D avatars: controllable humanoid bodies with face, bones, gaze, gestures, and reusable avatar assets inside the current OBS/browser stack.

This is the candidate for "make the current `/one` architecture real with a proper controllable 3D avatar."

## Proposed Pipeline

1. Runtime/Fish produces live audio, utterance IDs, line text, and synthesis metadata.
2. `useWorld.js` updates `voicePlayback` and `mouthAmplitude`.
3. `lipSync.js` builds the alphabet viseme timeline for the current utterance.
4. `ControlledAvatar.jsx` loads a VRM from a trusted URL or local sample policy.
5. The VRM adapter maps runtime state into:
   - mouth viseme weights;
   - jaw/mouth amplitude;
   - blink;
   - gaze/look target;
   - head/neck motion;
   - emotion expression;
   - gesture/bone clips.
6. Playwright or local capture records screenshot/video proof and telemetry.

## Agent Command Contract

```json
{
  "agent_id": "fish",
  "utterance_id": "alphabet-run-001",
  "controls": [
    {"type": "vrm.expression", "name": "aa", "weight": 0.84},
    {"type": "vrm.expression", "name": "blink", "weight": 0.0},
    {"type": "vrm.look_at", "target": "camera"},
    {"type": "vrm.bone", "name": "rightUpperArm", "rotation": [0.1, -0.3, 0.2]},
    {"type": "gesture", "name": "counting"}
  ]
}
```

The command layer should validate expression names, bone names, ranges, and gesture IDs before touching the model.

## Implementation Plan

1. Define a sample VRM asset policy: repo-controlled, fetched during setup, or explicitly operator-supplied through `VITE_DEFAULT_VRM_URL`.
2. Expand the current VRM adapter from basic loading into expression, look-at, and bone/gesture control.
3. Add renderer telemetry that differentiates real VRM from procedural fallback.
4. Add a `/one` proof that fails if no VRM asset loaded when the VRM track is selected.
5. Record screenshot/video while Fish audio recites A-Z.
6. Compare naturalness against Live2D and Godot using the same command contract.

## Validation

- `npm test` and `npm run build` in `observer`.
- Static tests for no prerecorded `/one` video fallback.
- Browser proof with a real VRM model, visible mouth movement, blink/head motion, and one gesture.
- Proof artifacts must include screenshot, video, and telemetry showing `vrm-rig` as the source kind.

## Merge Gate

This is the most open-source-friendly 3D candidate and the lowest integration cost. Merge only if it stops looking like a static image in proof captures and achieves the original live alphabet goal with a real controllable avatar.
