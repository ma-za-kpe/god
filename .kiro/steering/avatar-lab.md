# Avatar Lab Steering

Goal: build a local, browser-first avatar pipeline that can become continuous
LLM-directed video. The LLM must drive dialogue and avatar behavior; the code
must provide renderer adapters, safety bounds, schema validation, telemetry, and
test fallbacks.

Non-negotiable rule: hard-coded avatar behavior is allowed only as an explicit
test fallback before the LLM is connected. It is not the product path. Code owns
the schema and clamps unsafe values; the LLM owns the dialogue, camera/framing,
mood, gesture, gaze, full-body pose, hair, face, hands/fingers, wardrobe/body
presentation, lighting, stage, and every exposed renderer node.

When touching avatar work:

- Treat examples and fixtures as test fixtures, not the live behavior source.
- Keep LLM output constrained by `avatar_intent`, not arbitrary bone commands.
- Let the LLM address every exposed avatar node through a renderer-published
  registry and bounded `avatar_intent.nodes[]` controls.
- Let renderer adapters map intent to TalkingHead, MotionEngine, VRM, Three.js,
  or future sidecars.
- Keep local browser proof independent of Fish, ComfyUI, OBS, Vast, and strict
  agent birth paths unless the task explicitly asks for those systems.
