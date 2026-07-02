# Avatar Runtime Pivot: Unity / Convai

Parent issue: #91
Track issue: #160
Branch: `docs/160-unity-convai-pivot`
Status: benchmark and proof branch

## Decision Test

Unity/Convai succeeds only if it demonstrates a clearly better live controllable avatar proof than the open candidates, with acceptable licensing, cost, privacy, and API dependency.

This is a benchmark track first. It should not become the default open-source path unless it proves the original `/one` goal materially better than VRM, Live2D, or Godot.

## Upstream Fit

Convai's Unity integration targets conversational NPCs and character behavior. Its WebGL SDK describes a full conversation pipeline with speech recognition, language understanding/generation, TTS, text-to-action, and lip-sync support.

That makes it useful as a reference implementation for what a polished avatar/NPC platform exposes, even if we do not merge it into the open default path.

Primary references:

- https://docs.convai.com/api-docs/plugins-and-integrations/unity-plugin
- https://github.com/Conv-AI/Convai-Unity-WebGL-SDK
- https://convai.com/pricing

## Current Code Leverage

- GOD already has speech generation, utterance IDs, audio URLs, browser playback state, and proof capture.
- `observer/src/hooks/useWorld.js` already centralizes playback status and mouth amplitude.
- `observer/src/components/ControlledAvatar.jsx` already models renderer-neutral controls: mouth, viseme, blink, gaze/head motion, gesture, emotion, and telemetry.
- The benchmark can reuse the same A-Z alphabet proof and compare quality/latency against open candidates.
- A Unity bridge should consume GOD commands rather than replacing runtime dialogue, memory, or world state.

## Features To Capitalize On

- Conversational NPC pipeline: speech recognition, language generation, TTS, and lip-sync are already platform concepts.
- Text-to-action/action callbacks: useful reference for mapping agent dialogue into animations and scene actions.
- Avatar ecosystem integrations: Ready Player Me/Reallusion-style avatar flows are useful for comparison against VRM/Live2D asset policies.
- Unity animation tooling: Animator controllers, blend trees, timeline/cinemachine-style camera workflows, and asset store integrations.
- Benchmark value: helps define what "production avatar control" should feel like even if we build the final path with open tools.

## Unique Use Case

Commercial-quality NPC benchmark: quickly compare our open stack against a platform built for voice characters, action callbacks, and Unity avatar behavior.

This is the candidate for "what are we missing compared with a productized conversational avatar stack?"

## Proposed Pipeline

1. GOD runtime keeps ownership of world state, agent identity, and the alphabet proof.
2. A bridge sends selected commands into Unity:
   - `speak_start`
   - `audio_url`
   - `line_text`
   - `viseme`
   - `gesture`
   - `emotion`
   - `action_callback`
3. Unity/Convai renders the character and returns telemetry:
   - playback status;
   - action status;
   - lip-sync status;
   - frame/proof marker.
4. OBS captures the Unity output.
5. Proof compares Unity/Convai against VRM, Live2D, and Godot.

## Agent Command Contract

```json
{
  "agent_id": "fish",
  "utterance_id": "alphabet-run-001",
  "audio_url": "http://runtime.local/voice/audio/alphabet-run-001",
  "line": "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z.",
  "controls": [
    {"type": "unity.animator", "name": "isSpeaking", "value": true},
    {"type": "unity.animator", "name": "gesture", "value": "counting"},
    {"type": "convai.action", "name": "look_at_camera"},
    {"type": "emotion", "name": "confident"}
  ]
}
```

API keys and service credentials must never be committed. The bridge should support local mock mode for CI.

## Implementation Plan

1. Document account/API setup without committing secrets.
2. Build a tiny Unity scene or benchmark harness with one character and a command relay.
3. Run the A-Z proof using GOD-provided audio and commands.
4. Capture latency, visual quality, lip quality, setup steps, service calls, and failure modes.
5. Translate useful ideas back into open tracks: action callbacks, animator schemas, gesture libraries, and quality gates.

## Validation

- Benchmark proof video and screenshot.
- Latency and setup report.
- Secret-handling audit.
- Explicit cost/API dependency note.
- No claim that this is open-source default unless licensing/service dependency is accepted.

## Merge Gate

Do not merge as mainline avatar runtime unless it demonstrably beats open candidates on the original live `/one` goal and the project explicitly accepts the service dependency. Otherwise, keep the PR as a benchmark artifact.
