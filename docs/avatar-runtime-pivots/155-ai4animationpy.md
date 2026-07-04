# Avatar Runtime Pivot: AI4AnimationPy

Parent issue: #91
Track issue: #155
Branch: `feat/one-vrm-ai4animation-local`
Status: local control proof branch

## Decision Test

This track only succeeds if it helps the live show achieve granular avatar control without prerecorded video in the live path. The minimum local proof is one real-time rendered avatar controlled by an agent/LLM command stream across root movement, facing, head direction, spine/neck pose, arms, legs, idle sway, facial expression, and command-driven mouth open/close.

The local proof deliberately excludes Fish audio, LipDub, ComfyUI, LTX/Wan, prerecorded MP4 avatar loops, OBS, and YouTube. ComfyUI may remain on `main` as an asset-generation baseline, but this branch treats real-time embodiment as a separate runtime problem.

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

Confirmed local demo programs in the research checkout:

- `Demos/Actor/Program.py`
- `Demos/ECS/Program.py`
- `Demos/Empty/Program.py`
- `Demos/InverseKinematics/Program.py`
- `Demos/MotionEditor/Program.py`
- `Demos/MotionImport/BVH/Program.py`
- `Demos/MotionImport/FBX/Program.py`
- `Demos/MotionImport/GLB/Program.py`
- `Demos/MotionImport/Import_LaFan/Program.py`
- `Demos/MotionImport/Import_MANN/Program.py`
- `Demos/AI/ToyExample/Program.py`
- `Demos/AI/Autoencoder/Program.py`
- `Demos/AI/SequencePrediction/Program.py`
- `Demos/AI/MotionGrounding/Program.py`
- `Demos/Locomotion/Biped/Program.py`
- `Demos/Locomotion/Quadruped/Program.py`

Most relevant split:

- Biped Locomotion is the humanoid quality target for `/one` and world movement.
- Inverse Kinematics is the precision layer for pointing, reaching, foot planting, and hand placement.
- Motion Import is the bridge for BVH/FBX/GLB/NPZ clips and mocap evaluation.
- Actor and ECS are useful for rig/entity lifecycle patterns.
- Quadruped is useful later for non-human agents, but it is not the first `/one` target.
- AI training demos explain the training/inference patterns, but they are not a live avatar dependency yet.

The upstream code paths that matter most for our sidecar are:

- `Actor.SetTransforms(...)`, `Actor.SetPositions(...)`, `Actor.SetRotations(...)`, and `Actor.SyncToScene(...)` for writing sampled poses.
- `Motion.GetBoneTransformations(...)`, `Motion.GetBonePositions(...)`, and `Motion.GetBoneVelocities(...)` for turning BVH/FBX/GLB/NPZ clips into our pose stream.
- `RootModule.Series` and `MotionModule.Series` for splitting trajectory/root motion from per-bone motion.
- `GuidanceModule.Guidance` for style/action templates such as idle, big steps, zombie, star, walk, trot, and sit.
- `FeedTensor` and `ReadTensor` for the neural inference boundary: structured features in, root/joint predictions out.
- `FABRIK` and the demo `LegIK` wrappers for foot/hand contact correction.

Important constraint: AI4AnimationPy is source-available under CC BY-NC 4.0, not a permissive production dependency. This branch can evaluate it, learn from it, and run non-commercial proof harnesses. A production merge that vendors or depends on it requires either a licensing decision, an isolated optional research profile, or a replacement with a permissive runtime that satisfies the same GOD pose-stream contract.

## Biped Locomotion Demo Findings

The linked `Biped_Locomotion.gif` is the upstream `Demos/Locomotion/Biped` demo. It is the quality bar for this track because it is not a simple scripted walk cycle. It runs a trained neural locomotion controller and then post-processes the result for grounded feet and smooth full-body motion.

For the learning phase, Standalone mode is now the preferred AI4AnimationPy execution mode. It is the mode that opens the Raylib renderer, shows the grid room, camera, lighting, shadows, debug GUI, root/guidance controls, trajectory previews, and contact plots used by the official demos. GOD's browser `/one` page remains the eventual integration target, but it should not be used to judge AI4AnimationPy visual quality until the Biped controller has been adapted.

Standalone research runner:

- `scripts/run-ai4animationpy-standalone-demos.py`
- Default AI4AnimationPy source root: `artifacts/ai4animationpy-src`
- Default logs: `artifacts/ai4animationpy-demo-smoke`
- Behavior: run each demo from its own directory, wait for a bounded startup window, then terminate the Raylib process tree. A demo that is still alive at the deadline counts as a successful startup smoke test because the upstream Standalone loop normally runs until the window is closed.
- CPU-only behavior: the runner wraps demo startup so CUDA-saved PyTorch weights are loaded with `map_location="cpu"` when `torch.cuda.is_available()` is false.
- Local Raylib 6 finding: skinned demos need `Mesh.boneIndices` and `Model.boneMatrices`; older AI4AnimationPy code that writes `Mesh.boneIds`/`Mesh.boneMatrices` exits during skinned actor startup. Local Raylib 6 builds also may not include GPU skinning support, which can leave only the room UI/skeleton visible. The runner now applies four compatibility patches to the external local checkout before launching demos: Raylib 6 mesh fields, Raylib 6 shader bone-attribute names, CPU skinning mesh-buffer updates, and non-skinned shader routing for CPU-skinned actors.
- FBX import is dependency-gated on Autodesk FBX SDK Python bindings (`fbx`). `pip index versions fbx` found no matching distribution in this environment, so the runner skips `MotionImport/FBX` unless the SDK bindings are installed externally.
- `MotionImport/Import_LaFan` and `MotionImport/Import_MANN` are dataset-gated because their `bvh/NPZ` folders are not present in the local checkout.
- Native visual launch: `python scripts/run-ai4animationpy-standalone-demos.py --only Biped --launch --launch-wait 10 --launch-camera-mode third --launch-camera-distance 4.6` leaves the selected Raylib Standalone window running and writes `artifacts/ai4animationpy-demo-smoke/launch.json`.
- Ollama-controlled visual launch: use `--launch-camera-mode fixed --launch-autodrive ollama --launch-ollama-plan-interval 4`. Fixed camera is preferred for this path because the upstream third-person camera can hit singular-matrix math while following neural actor transforms. The launch path fails closed if the model is unavailable, requires a trace path, asks Ollama to author the stage contract first, then runs periodic model planning on a background thread so the Raylib window remains responsive.
- LLM stream contract: Ollama authors the stage, movement vocabulary, style mapping, prop coordinates, prop colors, command labels, stage targets, velocities, sprint flags, and durations at runtime. The repo does not provide canned choreography, prop coordinates, action batches, or deterministic movement fallbacks in the Ollama path.
- LLM schema guardrails: the program only supplies the JSON schema, available AI4AnimationPy guidance names, renderer primitive names, current root/telemetry facts, and safety/serialization constraints. Invalid JSON/style/target/numbers or unsafe boundary motion triggers `AI4_BIPED_LLM_RETRY`; repeated invalid model output logs `AI4_BIPED_LLM_REJECTED` and keeps the avatar paused/braked while the model is asked again. Infrastructure failures still trigger `AI4_BIPED_LLM_ERROR`. A logged `AI4_BIPED_BOUNDARY_BRAKE` pauses unsafe outbound motion near the soft stage boundary while waiting for a corrected model command.
- Coordinate contract: Ollama still chooses the stage numbers, but x/z are the horizontal room axes and y is vertical base height. Stage profiles are rejected if `floor_marker_y` or target `position_y` drifts away from the live actor floor; this prevents model-authored props from being buried under the Standalone room.
- Layout contract: prop scale and height are still model-authored, but profiles are rejected when a prop is too large for the model-authored stage radius. This prevents the live model from filling the camera with a block instead of a controllable avatar.
- Visibility contract: target positions are still model-authored, but profiles are rejected when targets sit outside the model-authored camera distance. This keeps the room, avatar, and props visible in the Standalone proof instead of hiding the stage off camera.
- Continuous stream safety: model command velocities/speeds/durations are rejected when out of range rather than silently clamped. When a model-authored command expires and the queue is empty, the runner pauses movement while waiting for the next Ollama response instead of continuing an expired velocity.
- Learning trace: every Ollama stage request, raw stage response, accepted stage profile, plan request, raw plan response, parsed plan, applied command, rejected command, boundary brake, and telemetry sample is appended to `artifacts/ai4animationpy-demo-smoke/Locomotion_Biped.llm_trace.jsonl`. The active trace filename and current model-authored action/style/target/queue state are displayed in the AI4AnimationPy window.
- Latest Biped launch proof: window title `AI4AnimationPy`, log `artifacts/ai4animationpy-demo-smoke/Locomotion_Biped.launch.log`, screenshot `artifacts/local-avatar-control/ai4animationpy-standalone-llm-stage-trace-visible.png`, GIF `artifacts/local-avatar-control/ai4animationpy-standalone-llm-stage-trace-visible.gif`.
- Latest LLM-control proof: the screenshot shows the trained Biped actor, model-authored room props, current AI4 style, and the live overlay with model, stage title, action, target, speed, queue, trace file, and rationale. The log and JSONL trace show model-authored commands plus rejected invalid responses and fail-closed pauses.
- Launch status: the native Biped renderer now shows the surfaced Geno avatar body in the checkered room instead of only the grid/skeleton. Current local validation target is continuous model-authored motion with visible trace-backed state, not keyboard-driven or pre-scripted movement.

Latest local Standalone smoke result:

- Command: `python scripts/run-ai4animationpy-standalone-demos.py`
- Result: 13 passed, 0 failed, 3 skipped.
- Compatibility: `raylib6_skinned_mesh=already_compatible`, `raylib6_skinned_shader_attributes=already_compatible`, `raylib6_cpu_skinning=already_compatible`, `raylib6_cpu_shader_selection=already_compatible`.
- Passed: `Actor`, `AI/Autoencoder`, `AI/MotionGrounding`, `AI/SequencePrediction`, `AI/ToyExample`, `ECS`, `Empty`, `InverseKinematics`, `Locomotion/Biped`, `Locomotion/Quadruped`, `MotionEditor`, `MotionImport/BVH`, `MotionImport/GLB`.
- Skipped: `MotionImport/FBX` because Autodesk `fbx` Python bindings are absent; `MotionImport/Import_LaFan` and `MotionImport/Import_MANN` because their external dataset folders are absent.
- Biped and Quadruped both reached the Standalone loop with their neural-controller assets loaded. That is now the source of truth for studying natural locomotion before adapting controller output back into `/one`.

Latest local browser bridge proof:

- Screenshot: `artifacts/local-avatar-control/one-room-ai4animationpy-live-upright.png`
- The observer waited for a non-default local-control caption before capture.
- The avatar is upright after the browser pose-stream sampler was changed to treat root rotation as yaw-only. This fixes the 180-degree quaternion ambiguity that could roll the procedural avatar onto its side.
- This browser proof is only a contract/integration check. It is not the final natural-motion quality target; the official Standalone Biped demo is now the motion-quality reference.

Confirmed local files:

- `artifacts/ai4animationpy-src/Demos/Locomotion/Biped/Program.py`
- `artifacts/ai4animationpy-src/Demos/Locomotion/Biped/Sequence.py`
- `artifacts/ai4animationpy-src/Demos/Locomotion/Biped/LegIK.py`
- `artifacts/ai4animationpy-src/Demos/Locomotion/Biped/Network.pt` - about 60 MB.
- `artifacts/ai4animationpy-src/Demos/Locomotion/Biped/PostProcessor.pt` - about 1.6 MB.
- `artifacts/ai4animationpy-src/Demos/Locomotion/Biped/Guidances/*.npz`

Guidance templates found locally:

- `BigSteps`
- `Chicken`
- `Dinosaur`
- `DragLeftLeg`
- `HandsBetweenLegs`
- `Idle`
- `LeanRight`
- `LegsApart`
- `Neutral`
- `OnHeels`
- `Star`
- `Zombie`

Code-visible architecture:

- `Program.Start()` loads the Geno `Model.glb`, the trained `Network.pt`, the `PostProcessor.pt`, the guidance templates, contact bones, and two `LegIK` solvers.
- `Control()` currently reads raylib gamepad/keyboard/mouse input and converts it into desired velocity, facing direction, speed, and guidance selection.
- `Predict()` uses `FeedTensor` to feed current actor transforms, velocities, future root control, and guidance positions into the network, then decodes root trajectory and full-body motion through `ReadTensor`.
- The post-processor predicts contacts for left ankle, left ball, right ankle, and right ball.
- `Animate()` blends previous/current predicted sequences, applies root locking, writes actor transforms, restores bone lengths/alignments, solves leg IK, and syncs the actor to the scene.
- `Draw()` and `GUI()` expose root control, guidance control, previous/current sequence visualization, contacts, timescale, and synchronization. These diagnostics explain the trajectory arrows/contact UI visible in the GIF.

Why it looks more natural than the current `/one` proof:

- The Biped demo predicts full-body pose from learned motion data instead of assembling isolated scripted actions.
- Root movement, legs, arms, spine, contacts, and timing are generated together, so arm swing, torso lean, gait timing, and weight transfer are coupled.
- Contacts plus leg IK reduce foot skating and help the character feel grounded.
- Guidance templates give style/action control without hand-writing every joint pose.
- The visible room, trajectory/debug controls, and grounded floor context make movement readable.

Current gap:

- Standalone Biped now runs the trained neural controller from `Network.pt` with Ollama-authored programmatic input vectors.
- This is still a local research harness, not the production `/one` browser renderer or headless sidecar contract.
- The current installed model, `llama3.1:8b`, is slow and often needs correction retries for duration, target, and velocity constraints. The JSONL traces are now the learning data for improving prompts/models.

Biped adapter TODO:

1. Create an optional non-commercial research sidecar entrypoint for `Demos/Locomotion/Biped` without vendoring the upstream tree or weights into this repo.
2. First run the upstream Biped demo in Standalone mode and record exactly which controls, guidance states, trajectory visuals, contacts, and IK outputs are visible.
3. Load `Network.pt`, `PostProcessor.pt`, `Sequence.py`, `LegIK.py`, Geno `Model.glb`, and guidance `.npz` files from an external AI4AnimationPy checkout.
4. Replace raylib input reads with a programmatic control object:
   - desired root velocity;
   - desired facing direction;
   - sprint/normal speed;
   - selected guidance style;
   - target waypoint and room bounds.
5. Let Ollama author the complete live control stream: stage contract, movement vocabulary, style mapping, command labels, target choices, velocities, sprint flags, and durations. The repo may validate and apply the stream, but it must not inject canned choreography.
6. Let the trained Biped controller generate root trajectory, joint transforms, contacts, and IK-corrected pose samples.
7. Normalize each generated frame into GOD pose stream fields: `timestamp_ms`, `root_position`, `root_rotation`, `joint_rotations`, `contacts`, and `gesture_label`.
8. Feed the pose stream into `/one` through the existing browser sampler and keep expression/mouth commands separate.
9. Add screenshot/video proof that the room fills the browser, the avatar stays in scale, trajectory is visible, feet do not obviously skate, and the model-authored intent changes movement.
10. Keep a hard fail when Ollama is unavailable or the selected model is missing. No hidden deterministic fallback sequence.
11. Evaluate a stronger local model by verifying and pulling a Qwen 14B/27B Ollama tag before judging naturalness against the GIF.
12. Persist every raw model response and every accepted/rejected command into JSONL so later runs can be mined for prompt/model improvements.
13. Display the active model, model-authored stage title, action, style, target, queue depth, rationale, and trace filename in the Standalone window.

## Upstream Feature Status

The upstream README feature matrix matters because several tempting capabilities are not implemented yet. Treat these as verified upstream status, not GOD assumptions:

| Feature | Upstream status | GOD interpretation |
| --- | --- | --- |
| Entity-Component-System | Present | Good fit for agent action components and sidecar lifecycle. |
| Update loop (`Update` / `Draw` / `GUI`) | Present | Useful in harnesses; GOD production should prefer headless/manual output over a standalone renderer loop. |
| Math library | Present | Valuable for FK, quaternions, axis-angle, matrices, mirroring, and pose normalization. |
| Neural networks | Present | MLP, Autoencoder, and Codebook Matching are useful for research/runtime inference experiments. |
| Real-time renderer | Present | Useful for local visual inspection, but GOD should keep browser/OBS as the live renderer. |
| Skinned mesh rendering | Present | Useful for harness proof and rig inspection, not required in the browser speaking path. |
| Inverse kinematics | Present | FABRIK should be evaluated for foot locking, pointing, reaching, and gesture correction. |
| Animation modules | Present | Joint contacts plus root/joint trajectory modules map directly to GOD's pose-stream fields. |
| Camera system | Present | Useful for local demo recording; not part of the runtime sidecar contract. |
| Motion import | Present | GLB, FBX, BVH import is the first real implementation target. |
| Execution modes | Present | Standalone, Headless, and Manual support make a server-side evaluation harness plausible. |
| Physics simulation | Planned | Do not design live collision/rigid-body behavior around AI4AnimationPy yet. |
| Path planning and spline tooling | Planned | GOD must supply path/stage planning for now. |
| Audio support | Planned | AI4AnimationPy does not solve speech, TTS, or lip audio. This branch disables audio and uses explicit mouth/expression commands instead. |

## Motion Import And Datasets

AI4AnimationPy's motion import is the most practical bridge into GOD. The upstream README documents:

```python
from ai4animation import Motion

motion = Motion.LoadFromGLB("character.glb")
motion = Motion.LoadFromFBX("character.fbx")
motion = Motion.LoadFromBVH("character.bvh", scale=0.01)
motion.SaveToNPZ("character")
```

It also documents the internal `.npz` motion format as 3D positions and 4D quaternions for each skeleton joint per frame, plus a batch conversion CLI:

```bash
convert --input_dir path/to/motions --output_dir path/to/output
```

Public dataset leads from upstream:

| Dataset | Character | Formats |
| --- | --- | --- |
| Cranberry | Cranberry | FBX, GLB |
| 100Style retargeted | Geno | BVH, FBX |
| LaFan | Ubisoft LaFan | BVH |
| LaFan resolved | Geno | BVH, FBX |
| ZeroEggs retargeted | Geno | BVH, FBX |
| Motorica retargeted | Geno | BVH, FBX |
| NSM | Anubis | BVH |
| MANN | Dog | BVH |

Implementation implication: start with a tiny BVH/NPZ clip because it gives us deterministic root/joint samples without needing the standalone renderer, physics, path planning, or audio.

## Current Code Leverage

The current repo already has a React/Three renderer surface this track should reuse:

- `observer/src/components/ControlledAvatar.jsx` drives a procedural rig or VRM model through sampled root, joint, and expression commands.
- `observer/src/components/WorldMap.jsx` selects the active `/one` controller and passes `vrm_avatar_url` into the avatar component when available.
- `observer/src/hooks/useWorld.js` can now short-circuit `/one` snapshots with `control_mode: "llm-avatar-control"` before any audio playback path runs.
- `/one` proof plumbing keeps telemetry attributes and `preserveDrawingBuffer` so screenshot/video validation can inspect the live-rendered avatar.

## Features To Capitalize On

- Python + NumPy/PyTorch runtime fit for a sidecar near the existing Python services.
- Headless/manual execution modes for server-side motion generation.
- ECS-style update loops that map cleanly to agent action components.
- Inverse kinematics for pointing, reaching, foot placement, and body reactions.
- GLB/FBX/BVH import and internal joint quaternion data for normalizing authored or captured motion.
- Root and joint trajectory modules for walking, pacing, dancing, and stage blocking.
- Dataset/module structure for cataloging reusable gesture clips and guidance templates.
- `FeedTensor`/`ReadTensor` inference boundary for swapping deterministic commands with learned pose prediction behind the same output schema.
- Optional renderer/skinned-mesh/camera stack for local diagnostics and proof recording, while production remains browser-rendered.

## Sidecar Design Lessons From The Tutorials

The sidecar should not start by running the full biped demo unchanged. That demo is valuable, but it is a standalone interactive program with keyboard/gamepad input, bundled model files, guidance templates, and an internal `Sequence` object. GOD needs a narrower server contract:

1. Import or load one tiny BVH/NPZ motion clip and prove deterministic pose extraction.
2. Normalize each frame into the existing GOD schema: timestamp, root transform, joint rotations, contacts, gesture label.
3. Expose a headless/manual evaluation entrypoint that can be called by tests without opening a renderer.
4. Add a biped adapter only after the import path works. Its first input should be a programmatic velocity/facing/guidance vector, not raylib keyboard state.
5. Keep AI4AnimationPy output as data. The browser remains the live renderer, and local proof uses command-driven mouth/expression values instead of audio.

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
   - temporary procedural Three.js proof renderer for local contract visualization only.
4. Local proof keeps audio disabled.
5. Mouth open/close and facial expression are owned by the command stream while AI4AnimationPy owns body motion.
6. Proof capture records screenshot, video, pose-command log, and local-control telemetry.

## Agent Command Contract

The sidecar should accept high-level commands, not raw bone twiddling from the LLM:

```json
{
  "agent_id": "fish",
  "control_id": "local-control-run-001",
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
10. Run the local `/one` control proof with screenshots and video.

## Implemented Slice

This branch now includes the first non-heavy implementation slice:

- `runtime/src/avatar/body_motion.py` defines the AI4AnimationPy-targeted body-motion contract.
- `AvatarState` and `AvatarPlan` expose `body_motion` to the observer.
- `scripts/local_avatar_control_server.py` publishes a local-only `llm-avatar-control` snapshot with no audio, no prerecorded video, and no generation stack dependency.
- `scripts/start-local-avatar-control.ps1` starts the local control server and React observer together.
- `observer/src/avatarMotion.js` validates/samples the same command contract into root position, root rotation, joint rotations, contacts, and gesture labels.
- `ControlledAvatar.jsx` applies the sampled motion to the procedural rig and the VRM rig path.
- The temporary procedural proof renderer now has visible arms and legs plus command-driven face/mouth state, so root movement, gestures, expressions, and mouth commands can show up in browser contract captures.

This browser proof creates the stable command/pose boundary that the real sidecar must satisfy. The active AI4AnimationPy quality proof is now the Standalone Biped path above, where Ollama authors the live control stream and AI4AnimationPy runs the trained controller.

## Open Local Quality Gates

- Download and evaluate a stronger local Ollama motion-brain model before judging avatar naturalness. `llama3.1:8b` is only the currently installed baseline and has already shown repetitive/basic motion planning.
- Preferred model candidates for the next local run are `qwen3.5:14b` first, then `qwen3.6:27b` if the machine can handle it. The startup path must fail closed when the selected model is not installed.
- Keep `OLLAMA_NUM_CTX`/`--ollama-num-ctx` high enough for the room layout, persona, previous action, and operator intent to fit in context. The local script default is 8192.
- Keep the prompt limited to state, available AI4AnimationPy guidance names, renderer capabilities, schema, safety constraints, previous model output, and current telemetry. The model must choose the stage and movement plan; the app must not invent fallback action sequences.
- Every local validation pass must include screenshot proof of `/one`; use screenshots to check room scale, avatar scale, trajectory visibility, and whether the pose stream looks natural.

Current visual QA status:

- Improved: AI4AnimationPy Standalone is active locally with the trained Biped controller. Ollama now authors the stage, movement vocabulary, and live command batches, and every raw/applied/rejected item is persisted to JSONL.
- Improved: trajectory and timing are coherent enough for a first local loop, and the persona can influence broad spine/head attitude.
- Still weak: `llama3.1:8b` produces robotic, repetitive, overly basic movement plans. It should not be the quality target.
- Still weak: persona embodiment is shallow on the 8B model; “cautious,” “deliberate,” or “wistful” style needs stronger model reasoning and longer context.
- Still weak: point/smile gestures remain static and need better secondary motion, hand pose nuance, facial blending, head/gaze following, breathing, weight shift, and locomotion smoothing.

This branch now also includes the optional motion-export evaluation slice:

- `runtime/src/avatar/pose_stream.py` defines GOD's neutral pose-stream schema and validation.
- `scripts/eval-ai4animationpy-motion.py` loads an AI4AnimationPy-style NPZ export and emits summary, JSON, or NDJSON.
- The loader accepts common aliases such as `rotations`, `positions`, and `times`, while preserving the canonical GOD fields.
- The validator rejects non-monotonic timestamps, non-finite transforms, zero quaternions, missing joints, malformed contacts, and out-of-stage root movement.
- The pure-Python NPZ reader supports CI/runtime environments without NumPy, so the harness does not add AI4AnimationPy, PyTorch, renderer, or model dependencies to `/one`.
- The stream metadata carries `license_profile: optional-research-noncommercial` to make the CC BY-NC 4.0 boundary visible in generated proof artifacts.

This still does not make AI4AnimationPy production-ready. It proves that a motion import or sidecar output can be checked against GOD's contract before any browser/runtime integration.

## Source-Backed Eval Proof

The eval harness has now been run against a real upstream AI4AnimationPy demo export without vendoring the source asset:

- Upstream path: `facebookresearch/ai4animationpy@main:Demos/MotionImport/BVH/WalkingStickLeft_BR.npz`
- Upstream blob SHA: `90d06b48e1c790c24088b4c6ec794fae17ae4610`
- Local proof-file SHA-256: `0b70056faa08b576fe19b0f5b089591d4f1928c7b9ca2c7092c7f1cb75197fdb`
- Command: `python scripts/eval-ai4animationpy-motion.py --npz C:\tmp\god-ai4animationpy-proof\WalkingStickLeft_BR.npz --agent-id upstream-walking-stick --max-frames 120 --stride 30 --format summary`

Observed summary:

```json
{
  "agent_id": "upstream-walking-stick",
  "contact_count": 0,
  "duration_seconds": 59.501,
  "frame_count": 120,
  "joint_count": 23,
  "last_timestamp_ms": 59501,
  "license_profile": "optional-research-noncommercial",
  "root_bounds": {
    "max": [0.902579, 0.885022, 0.672077],
    "min": [-1.497222, 0.810247, -3.224509]
  },
  "source": "ai4animationpy-eval",
  "target_runtime": "ai4animationpy"
}
```

The first attempt exposed a real adapter gap: upstream `Motion.SaveToNPZ(...)` emits `positions`, `quaternions`, `framerate`, `bone_names`, `parent_names`, and `parent_indices`, while the initial GOD loader only accepted `joint_rotations`/`rotations` and tried to load every NPZ member with `allow_pickle=False`. The harness now recognizes `quaternions`, uses source `framerate` for generated timestamps, and loads only relevant safe members so pickle-only metadata cannot break the eval path.

Local visual proof artifacts were generated from the same upstream export without committing the asset:

- `C:\tmp\god-ai4animationpy-proof\walking-stick-pose-proof.png`
- `C:\tmp\god-ai4animationpy-proof\walking-stick-pose-proof.gif`

These artifacts prove the observer sampler can turn the upstream pose stream into visible root movement and mapped rig joints. They are proof artifacts only; they do not satisfy the final `/one` live YouTube proof gate.

## Validation

- Unit test command validation and pose-stream normalization.
- Unit test NPZ motion import, alias normalization, NDJSON export, and the CLI summary path.
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
