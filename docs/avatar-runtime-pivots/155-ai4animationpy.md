# Avatar Runtime Pivot: AI4AnimationPy

Parent issue: #91
Track issue: #155
Branch: `docs/155-ai4animationpy-pivot`
Status: planning and proof branch

## Decision Test

This track only succeeds if it helps the live show achieve granular avatar control without prerecorded video in the speaking path. The minimum proof is one avatar reciting the alphabet while an agent-directed motion stream controls body pose, facing, timing, and stage movement live.

ComfyUI is not part of this path. ComfyUI may remain on `main` as an asset-generation baseline, but this branch treats real-time embodiment as a separate runtime problem.

## Upstream Fit

AI4AnimationPy is a Python framework for AI-driven character animation. The upstream project describes support for motion-capture processing, neural network training/inference, inverse kinematics, and GLB/FBX/BVH import, with both UI and headless/manual execution modes.

The practical fit is strongest as a motion sidecar rather than a final renderer:

- Python-native integration with the runtime is plausible.
- Motion outputs can be normalized into timestamped root transforms and joint rotations.
- It can provide world movement, posture, stage blocking, dancing, and nonverbal body language.
- License is CC BY-NC 4.0, so production/commercial use needs a separate licensing decision.

Primary references:

- https://github.com/facebookresearch/ai4animationpy
- https://facebookresearch.github.io/ai4animationpy/

## Tutorial And Demo Inventory

Official tutorial pages reviewed:

- Demo Programs: https://facebookresearch.github.io/ai4animationpy/tutorials/demos/
- Custom Component: https://facebookresearch.github.io/ai4animationpy/tutorials/custom-component/
- Custom Module: https://facebookresearch.github.io/ai4animationpy/tutorials/custom-module/
- Training a Network: https://facebookresearch.github.io/ai4animationpy/tutorials/training-network/

The demo index and repo tree map into these GOD-relevant slices:

| Upstream tutorial/demo | What it proves | GOD use |
| --- | --- | --- |
| `Empty` | Minimal `Program` bootstrap. | Harness smoke test with no rendering assumptions. |
| `ECS` | Entity hierarchy, parent-child transforms, custom `Component` lifecycle. | Agent action components for stage blocking, idle behavior, reactive gestures. |
| `Actor` | GLB character loading and `Actor.SyncFromScene()`. | Rig-loading adapter for a GOD avatar body. |
| `MotionImport/GLB` | `Motion.LoadFromGLB(...)` then `Actor.SetTransforms(...)`. | Convert authored GLB animation clips into our neutral pose stream. |
| `MotionImport/FBX` | `Motion.LoadFromFBX(...)`, `RootModule`, per-frame transforms. | Import larger mocap/action libraries for gestures and motion primitives. |
| `MotionImport/BVH` | `Motion.LoadFromBVH(..., scale=0.01)`, optional NPZ conversion. | BVH is the fastest evaluation path because the demo ships a BVH sample and calls `GetBoneTransformations`. |
| `MotionEditor` | `Dataset`, `RootModule`, `MotionModule`, `ContactModule`, `GuidanceModule`, `MirrorModule`. | Offline motion browser for picking walk, idle, emphasis, and dance primitives. |
| `InverseKinematics` | `FABRIK` over actor bone chains, target entity, `Actor.SyncToScene(...)`. | Reaching, pointing, foot locking, hand-on-podium, and body reactions. |
| `Locomotion/Biped` | Neural locomotion with `Network.pt`, `PostProcessor.pt`, `FeedTensor`, `ReadTensor`, `TimeSeries`, guidance templates, contacts, and leg IK. | The closest match for full-body live world movement, but it currently assumes keyboard/gamepad control and standalone rendering. |
| `Locomotion/Quadruped` | Similar inference loop with gait/action guidance and contact-aware IK. | Not for humanoid `/one`, but useful as proof that guidance/action states can control style and gait. |
| `AI/ToyExample` | Minimal PyTorch training loop. | CI-safe training smoke only, not avatar runtime. |
| `AI/Autoencoder` | Motion-feature autoencoder training. | Later compression/embedding of motion clips, not a live dependency. |
| `AI/SequencePrediction` | `DataSampler`, `FeedTensor`, future root/motion prediction, `ReadTensor` output decoding. | Template for predicting short future pose windows from current actor state. |
| `AI/MotionGrounding` | Learns pose from smoothed trajectory windows and reconstructs bone transforms. | Candidate for grounding LLM intent/trajectory into a full-body pose. |

The upstream code paths that matter most for our sidecar are:

- `Actor.SetTransforms(...)`, `Actor.SetPositions(...)`, `Actor.SetRotations(...)`, and `Actor.SyncToScene(...)` for writing sampled poses.
- `Motion.GetBoneTransformations(...)`, `Motion.GetBonePositions(...)`, and `Motion.GetBoneVelocities(...)` for turning BVH/FBX/GLB/NPZ clips into our pose stream.
- `RootModule.Series` and `MotionModule.Series` for splitting trajectory/root motion from per-bone motion.
- `GuidanceModule.Guidance` for style/action templates such as idle, big steps, zombie, star, walk, trot, and sit.
- `FeedTensor` and `ReadTensor` for the neural inference boundary: structured features in, root/joint predictions out.
- `FABRIK` and the demo `LegIK` wrappers for foot/hand contact correction.

Important constraint: AI4AnimationPy is source-available under CC BY-NC 4.0, not a permissive production dependency. This branch can evaluate it, learn from it, and run non-commercial proof harnesses. A production merge that vendors or depends on it requires either a licensing decision, an isolated optional research profile, or a replacement with a permissive runtime that satisfies the same GOD pose-stream contract.

## Current Code Leverage

The current repo already has the live speech and renderer surface this track should reuse:

- `observer/src/hooks/useWorld.js` starts Fish audio for `/one` with `transport: 'fish-audio+rigged-avatar'` and updates `voicePlayback.mouthAmplitude` from a Web Audio analyser.
- `observer/src/lipSync.js` builds the alphabet viseme track and samples it efficiently with binary search.
- `observer/src/components/ControlledAvatar.jsx` consumes `voicePlayback`, `mouthAmplitude`, and alphabet visemes, then drives a procedural rig or VRM model.
- `observer/src/components/WorldMap.jsx` selects the active `/one` speaker and passes `vrm_avatar_url` into the avatar component.
- `/one` proof plumbing already includes telemetry attributes, screenshot/video capture, and `preserveDrawingBuffer`.

## Features To Capitalize On

- Python + NumPy/PyTorch runtime fit for a sidecar near the existing Python services.
- Headless/manual execution modes for server-side motion generation.
- ECS-style update loops that map cleanly to agent action components.
- Inverse kinematics for pointing, reaching, foot placement, and body reactions.
- GLB/FBX/BVH import and internal joint quaternion data for normalizing authored or captured motion.
- Root and joint trajectory modules for walking, pacing, dancing, and stage blocking.
- Dataset/module structure for cataloging reusable gesture clips and guidance templates.
- `FeedTensor`/`ReadTensor` inference boundary for swapping deterministic commands with learned pose prediction behind the same output schema.

## Sidecar Design Lessons From The Tutorials

The sidecar should not start by running the full biped demo unchanged. That demo is valuable, but it is a standalone interactive program with keyboard/gamepad input, bundled model files, guidance templates, and an internal `Sequence` object. GOD needs a narrower server contract:

1. Import or load one tiny BVH/NPZ motion clip and prove deterministic pose extraction.
2. Normalize each frame into the existing GOD schema: timestamp, root transform, joint rotations, contacts, gesture label.
3. Expose a headless/manual evaluation entrypoint that can be called by tests without opening a renderer.
4. Add a biped adapter only after the import path works. Its first input should be a programmatic velocity/facing/guidance vector, not raylib keyboard state.
5. Keep AI4AnimationPy output as data. The browser remains the live renderer and Fish/audio remains the live speech source.

This means the next real #155 code should be an evaluation harness, not a larger React change:

- `scripts/eval-ai4animationpy-motion.py` or equivalent optional tool.
- Inputs: demo BVH/NPZ path, bone map, command plan.
- Outputs: JSON/NDJSON pose stream plus a short diagnostic summary.
- Tests: schema validation, monotonic timestamps, finite transforms, bounded root movement, non-empty contacts when available, and license-gated optional execution.

## Unique Use Case

Full-world body movement: walking to a podium, turning to face another agent, pacing while speaking, dancing, cheering, reacting physically to interruptions, and producing believable body timing beyond mouth movement.

This is the candidate for "avatars move around the world," not the candidate for mouth-quality alone.

## Proposed Pipeline

1. Runtime emits an avatar action plan over NATS/WebSocket:
   - `walk_to`
   - `turn_to`
   - `gesture`
   - `dance`
   - `idle`
   - `emphasis`
   - `look_at`
2. AI4AnimationPy sidecar converts the plan into a pose stream:
   - `timestamp_ms`
   - `root_position`
   - `root_rotation`
   - `joint_rotations`
   - `contacts`
   - `gesture_label`
3. Observer receives the pose stream and applies it to a browser avatar renderer:
   - first target: VRM/three-vrm test avatar;
   - fallback target: procedural Three.js rig for proof.
4. Fish/live speech remains the audio source.
5. Lip sync remains owned by the renderer track, while AI4AnimationPy owns body motion.
6. Proof capture records screenshot, video, pose-command log, and audio/lip-status diagnostics.

## Agent Command Contract

The sidecar should accept high-level commands, not raw bone twiddling from the LLM:

```json
{
  "agent_id": "fish",
  "utterance_id": "alphabet-run-001",
  "commands": [
    {"at_ms": 0, "type": "look_at", "target": "camera"},
    {"at_ms": 200, "type": "gesture", "name": "introduce"},
    {"at_ms": 1200, "type": "walk_to", "x": 0.2, "z": -0.4, "duration_ms": 1800},
    {"at_ms": 3200, "type": "gesture", "name": "emphasis_right_hand"}
  ]
}
```

The implementation should keep command validation deterministic and reject unknown command names, impossible durations, and out-of-stage targets.

## Implementation Plan

1. Add the GOD-side command and pose-stream contract.
2. Wire the observer to consume the contract through a deterministic sampler.
3. Apply the sampled root and joint motion to the procedural rig and VRM rig path.
4. Add an AI4AnimationPy evaluation harness outside the blocking `/one` route.
5. Start with the BVH import demo path because it is the smallest source-backed pose export surface.
6. Load a tiny test motion asset and prove deterministic pose-stream export without launching the standalone renderer.
7. Add a biped locomotion adapter by replacing raylib keyboard/gamepad input with GOD command vectors: velocity, facing, guidance style, and action.
8. Replace the deterministic sampler with sidecar output behind the same contract.
9. Add a `/one?runtime=ai4animationpy` or equivalent local proof path only after the sidecar stream is stable.
10. Run the alphabet proof with screenshots and video.

## Implemented Slice

This branch now includes the first non-heavy implementation slice:

- `runtime/src/avatar/body_motion.py` defines the AI4AnimationPy-targeted body-motion contract.
- `AvatarState` and `AvatarPlan` expose `body_motion` to the observer.
- `AvatarSurface.compose()` publishes a deterministic alphabet movement plan for speaking snapshots and an idle plan for listening snapshots.
- `observer/src/avatarMotion.js` validates/samples the same command contract into root position, root rotation, joint rotations, contacts, and gesture labels.
- `ControlledAvatar.jsx` applies the sampled motion to the procedural rig and the VRM rig path.
- The procedural fallback now has visible arms and legs, so root movement and gestures can show up in proof captures.

This does not claim AI4AnimationPy model inference yet. It creates the stable command/pose boundary and visible live proof path that the real sidecar must satisfy.

## Validation

- Unit test command validation and pose-stream normalization.
- Local browser proof must show visible non-mouth body motion.
- Proof artifacts must include screenshot and video.
- No generated/prerecorded avatar video may drive the speaking result.
- The branch must document whether CC BY-NC 4.0 blocks any production merge.

## Merge Gate

Merge only if the branch proves a real-time controllable motion sidecar and does not weaken the live speaking goal. If another track supplies the face/lip layer, this track may still merge later as the body-motion layer rather than the primary avatar runtime.

Because upstream is CC BY-NC 4.0, a production merge must not silently make AI4AnimationPy a mandatory dependency. Acceptable merge shapes are:

- optional non-commercial research profile;
- sidecar contract and tests only, with no vendored upstream code/models;
- separate licensing approval;
- or a permissive reimplementation/replacement that honors the same pose-stream contract.
