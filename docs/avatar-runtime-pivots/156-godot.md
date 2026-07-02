# Avatar Runtime Pivot: Godot

Parent issue: #91
Track issue: #156
Branch: `docs/156-godot-pivot`
Status: planning and proof branch

## Decision Test

Godot succeeds only if it gives the agents direct live control over a show stage: avatar parameters, actions, cameras, props, timing, and replayable scene direction. The minimum proof is one avatar reciting the alphabet while Godot receives live commands for mouth, head, gaze, gesture, and camera framing.

ComfyUI is not part of this speaking path. The Godot track is a real-time runtime track, not a diffusion/video-generation track.

## Upstream Fit

Godot is MIT-licensed and designed as a full real-time game/runtime engine. That makes it a strong candidate for deterministic show staging where agents manipulate scene graph nodes, animation trees, cameras, and props.

Useful adjacent projects:

- LimboAI provides behavior trees and hierarchical state machines for Godot 4.
- Godot steering frameworks can support movement, avoidance, and stage blocking.
- Godot's scene model fits multi-avatar theater better than trying to make every control path live inside React alone.

Primary references:

- https://godotengine.org/license/
- https://github.com/limbonaut/limboai
- https://github.com/GDQuest/godot-steering-ai-framework

## Unique Use Case

The full live show stage: controllable actors, camera cuts, podiums, props, reactions, walks, interruptions, audience-facing blocking, behavior trees, and deterministic replay logs.

Godot is the candidate for "the whole cartoon debate show becomes a controllable live scene."

## Proposed Pipeline

1. GOD runtime emits a scene command stream:
   - `speak_start`
   - `viseme`
   - `gesture`
   - `look_at`
   - `move_to`
   - `interrupt`
   - `react`
   - `camera_take`
2. A Godot bridge receives commands over WebSocket or NATS.
3. Godot maps commands into:
   - AnimationTree state changes;
   - face/mouth parameters;
   - head and eye targets;
   - behavior-tree blackboard values;
   - camera transitions;
   - prop and stage events.
4. Godot renders a live window for OBS capture.
5. Proof capture records the Godot window, browser/runtime diagnostics, command logs, and YouTube/OBS state when field-tested.

## Agent Command Contract

The command protocol should be renderer-neutral so we can compare Godot against Live2D and VRM:

```json
{
  "agent_id": "fish",
  "clock_ms": 2480,
  "speech": {
    "utterance_id": "alphabet-run-001",
    "text": "A B C D E F G"
  },
  "controls": [
    {"type": "mouth", "value": 0.73},
    {"type": "viseme", "name": "aa", "weight": 0.9},
    {"type": "look_at", "target": "camera"},
    {"type": "gesture", "name": "counting_left_hand"},
    {"type": "camera_take", "name": "single_closeup"}
  ]
}
```

The Godot bridge should reject unknown controls and keep a command log that can be replayed.

## Implementation Plan

1. Add a minimal Godot project under an experimental directory, not in the production runtime path.
2. Build one placeholder avatar with mouth, head, blink, gaze, and gesture controls.
3. Implement a local command receiver and a deterministic replay file.
4. Connect the current Fish/alphabet proof to Godot mouth and expression controls.
5. Capture the Godot window through OBS or a local screen recorder.
6. Compare latency and operational complexity against the browser rig.

## Validation

- Local proof video must show live mouth/head/gesture control from commands.
- Replay file must reproduce the same visual command timing.
- Runtime must be able to fail closed if Godot is unavailable.
- No generated/prerecorded avatar video may drive the speaking result.
- Licensing and export assumptions must remain compatible with the open-source repo.

## Merge Gate

Merge only if Godot demonstrably improves live controllability over the browser rig without making the YouTube path fragile. If Godot is too heavy for the immediate `/one` goal, keep it as a stage-runtime experiment and do not block the VRM/Live2D tracks.
