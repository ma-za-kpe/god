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

1. Add an AI4AnimationPy evaluation harness outside the blocking `/one` route.
2. Load a tiny test motion asset and prove deterministic pose-stream export.
3. Add a runtime adapter that turns GOD action plans into AI4AnimationPy commands.
4. Render the output through the existing browser scene using a simple GLB/VRM target.
5. Add a `/one?runtime=ai4animationpy` or equivalent local proof path only after the pose stream is stable.
6. Run the alphabet proof with screenshots and video.

## Validation

- Unit test command validation and pose-stream normalization.
- Local browser proof must show visible non-mouth body motion.
- Proof artifacts must include screenshot and video.
- No generated/prerecorded avatar video may drive the speaking result.
- The branch must document whether CC BY-NC 4.0 blocks any production merge.

## Merge Gate

Merge only if the branch proves a real-time controllable motion sidecar and does not weaken the live speaking goal. If another track supplies the face/lip layer, this track may still merge later as the body-motion layer rather than the primary avatar runtime.
