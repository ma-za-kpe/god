# Agent Steering

## Avatar Lab Prime Directive

Goal: build a local, browser-first avatar pipeline that can become continuous
LLM-directed video. The LLM must drive dialogue and avatar behavior; the code
must provide renderer adapters, safety bounds, schema validation, telemetry, and
test fallbacks.

Rule: hard-coded avatar behavior is allowed only as an explicit test fallback
before the LLM is connected. It is not the product path. Code owns the schema
and clamps unsafe values; the LLM owns the dialogue, camera/framing, mood,
gesture, gaze, full-body pose, hair, face, hands/fingers, wardrobe/body
presentation, lighting, stage, and every exposed renderer node.

Implementation reminder:

- Do not bake real speech lines, moods, gestures, camera choices, full-body
  motion, wardrobe, lighting, hair motion, face expression, or finger movement
  into production avatar flow.
- Keep deterministic examples behind explicit test or fallback controls.
- Prefer a constrained `avatar_intent` contract over raw free-form renderer
  commands.
- The LLM should eventually control every exposed avatar node. Do this through
  a renderer-published node registry and bounded `avatar_intent.nodes[]`
  controls, not arbitrary JavaScript, shader, URL, or filesystem writes.
- Renderer code may reject, clamp, or degrade unsafe intent. It should not
  invent the performance when the LLM is available.
- Local development should prove the loop in the browser first, without Fish,
  ComfyUI, OBS, Vast, or strict agent-creation gates as default requirements.
