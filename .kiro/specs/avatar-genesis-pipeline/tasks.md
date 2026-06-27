# Implementation Plan: Avatar Genesis Pipeline

## Overview

This plan implements the Avatar Genesis Pipeline in 14 tasks, starting with data model foundations, then building the service integrations, the orchestrator, the runtime reactivity layer, and finally infrastructure wiring. Tasks are ordered by dependency — early tasks produce types and configs consumed by later tasks.

## Tasks

- [x] 1. Data model foundations
  - [x] 1.1 Add visual_state and avatar_base_cid to AgentIdentity in owned_graph.py
    - Add `avatar_base_cid: str = ""` field to AgentIdentity dataclass
    - Add `visual_state: dict` field with default factory containing: current_expression, expression_override, override_expiry_epoch, scar_layers, presentation_mode
    - Update `from_dict()` to load visual_state and avatar_base_cid with backward-compatible defaults
    - Update `to_dict()` to serialize visual_state and avatar_base_cid
    - _Requirements: R11-AC1,7 R13-AC4,5_

  - [x] 1.2 Create archetype_config.py with all 8 archetype style/voice/utterance configurations
    - Create `runtime/src/avatar/archetype_config.py`
    - Define `ArchetypeStyleConfig` frozen dataclass with fields: archetype, style_prompt_template (≤500 chars), color_palette, emblem, soul_trait_keywords, voice_timbre, voice_pitch_range (tuple Hz), voice_cadence_wpm, prosody_map (CRACK→wounded, ESCALATE→emphasis, CONCEDE→whisper, TAUNT→cold, SILENCE→pause), seed_utterance_path
    - Populate `ARCHETYPE_CONFIGS` dict for all 8 archetypes: trader, hoarder, explorer, parasite, cooperator, defender, philosopher, builder
    - Add `validate_archetype_configs()` startup validation function that checks exactly 8 entries exist with non-empty templates and complete voice parameters
    - Create `runtime/seed_utterances/` directory with placeholder .wav files for each archetype and a README
    - _Requirements: R7-AC1-7 R4-AC5,6_

- [x] 2. Infrastructure setup
  - [x] 2.1 Add Docker Compose sidecar services for ComfyUI and Fish Speech
    - Add `comfyui` service to docker-compose.yml with GPU access, port 8188, model volume mounts
    - Add `fish-speech` service with GPU access, port 8080, utterance volume mounts
    - Add environment variables to the runtime service: COMFYUI_ENDPOINT, TTS_ENDPOINT, PIPELINE_TIMEOUT_SECONDS, COMFYUI_CONCURRENCY, TTS_CONCURRENCY
    - Update `.env.example` with all new environment variables and their defaults
    - _Requirements: R8-AC1-6_

  - [x] 2.2 Create ComfyUI workflow JSON templates
    - Create `runtime/workflows/` directory
    - Create `flux_portrait.json` — Flux + IP-Adapter FaceID workflow for canonical portrait generation
    - Create `flux_expression.json` — expression variant workflow with portrait as IP-Adapter reference
    - Create `controlnet_evolution.json` — ControlNet inpainting workflow for evolution modifications
    - Document required custom nodes in each workflow file
    - Add `runtime/workflows/README.md` explaining workflow usage and custom node dependencies
    - _Requirements: R2,3-workflow R13-ControlNet_

- [x] 3. Service integrations
  - [x] 3.1 Implement PortraitGenerator (ComfyUI integration) in portrait_generator.py
    - Create `runtime/src/avatar/portrait_generator.py`
    - Implement `PortraitGenerator` class with comfyui_endpoint and semaphore params
    - Build ComfyUI Flux + IP-Adapter workflow JSON payload from archetype config
    - Submit workflow via POST, poll queue/history API for completion, retrieve output image
    - Validate output: PNG/JPEG format, ≥1KB size, ≥512×512 dimensions
    - Implement `generate_expressions()` method that generates 7 variants (neutral, angry, playful, calm, intense, vulnerable, flinch) using portrait as IP-Adapter reference
    - Per-request timeout 60 seconds
    - Implement `health_check()`: GET endpoint expect HTTP 200 within 10 seconds
    - _Requirements: R2-AC1-6 R3-AC1-7 R8-AC1,3_

  - [x] 3.2 Implement VoiceCloner (Fish Speech S2 / CosyVoice integration) in voice_cloner.py
    - Create `runtime/src/avatar/voice_cloner.py`
    - Define `VoiceCloneResult` dataclass with embedding_bytes, voice_params, verification_sample fields
    - Implement `VoiceCloner` class with tts_endpoint and semaphore params
    - Submit zero-shot clone request with seed utterance audio
    - Validate embedding is non-zero-byte payload
    - Generate 1-10 second verification sample using the embedding
    - If verification sample fails (zero bytes or generation error): discard embedding entirely
    - Derive voice_params dict from ArchetypeStyleConfig including prosody_map
    - Implement `health_check()`: GET endpoint expect HTTP 200
    - Detect prosody tag support from capabilities endpoint response
    - _Requirements: R4-AC1-8 R8-AC2,3 R14-AC7_

  - [x] 3.3 Implement VisualReactor for runtime beat-to-expression binding in visual_reactor.py
    - Create `runtime/src/avatar/visual_reactor.py`
    - Define `MOVE_EXPRESSION_MAP` dict: ESCALATE→intense, TAUNT→angry, CONCEDE→calm, DEFLECT→playful, QUESTION→attentive, PIVOT→animated, SILENCE→calm, CALLBACK→playful, COUNTER→intense, CRACK→vulnerable
    - Implement `on_beat_delivered()` that updates speaker's visual_state.current_expression based on Move type
    - Implement CRACK handling: force "vulnerable" expression for 15-40s (configurable via CRACK_EXPRESSION_DURATION_SECONDS, default 25)
    - Implement `on_landed_hit()`: force "flinch" on receiver for 5-15s (configurable via FLINCH_EXPRESSION_DURATION_SECONDS, default 8)
    - Implement override expiry check: if current epoch >= override_expiry_epoch, clear override
    - _Requirements: R11-AC2-7_

  - [x] 3.4 Implement SceneComposer for multi-Elder layout in scene_composer.py
    - Create `runtime/src/avatar/scene_composer.py`
    - Define `ElderLayout` dataclass: soul_id, position (x,y normalized 0-1), scale (0.5-1.0), z_order (int), expression
    - Define `SceneLayout` dataclass: elders list, transition_duration_s, composition_type (duo/trio/quad)
    - Define `BASE_LAYOUTS` for 2, 3, and 4 Elder configurations
    - Implement `compose_scene()`: has_the_room Elder gets dominant position (center, scale=1.0)
    - Z-order assigned by speaking recency (active speaker foreground)
    - Tension > 7 between two Elders reduces visual distance between them
    - Transition duration 2-4 seconds when layout changes
    - Output layout spec suitable for rendering layer consumption
    - _Requirements: R12-AC1-7_

  - [x] 3.5 Enhance VoiceSurface with prosody binding in voice/engine.py and voice/state.py
    - Add `prosody_tag`, `emotional_texture_score`, `tension_speed_modifier`, `tension_pitch_modifier` fields to VoicePlan in `runtime/src/voice/state.py`
    - In `compose()` method of voice engine: read prosody_map from agent's voice_params, select Prosody_Tag for current Move type
    - Wrap beat text in tag syntax: `[tag]text[/tag]`
    - When tension > 7: apply speed +8% and pitch +5% modifiers
    - When reconciliation_arc active: apply speed -5%
    - When quality_score > 12 (Landed_Hit): stack `[emphasis]` tag
    - Pass emotional_texture score (0-3) to TTS service
    - Fallback: if TTS doesn't support prosody tags, use speed/pitch modifiers only and log degraded-mode warning
    - _Requirements: R14-AC1-7_

- [x] 4. Orchestrators
  - [x] 4.1 Implement GenesisPipeline orchestrator in genesis_pipeline.py
    - Create `runtime/src/avatar/genesis_pipeline.py`
    - Define `PipelineResult` dataclass: soul_id, correlation_id, status (complete/partial/failed), portrait_cid, expression_sheet_cid, voice_embedding_cid, assets_produced, duration_ms, errors
    - Implement `GenesisPipeline` class with shared asyncio.Semaphore for ComfyUI (default 2) and TTS (default 4)
    - Execute pipeline: health check → portrait → expressions → voice → identity registration → re-pin IPFS → update PostgreSQL
    - Overall timeout via asyncio.wait_for (PIPELINE_TIMEOUT_SECONDS, default 300)
    - IPFS retry: 3 attempts with exponential backoff (2s/4s/8s)
    - Concurrency slot wait max 30 seconds (treat as failed if exceeded)
    - Maintain in-memory status registry for observability
    - Implement graceful degradation: skip unavailable services, continue with what succeeds
    - _Requirements: R1-AC1-3 R5-AC1-8 R6-AC1-6 R9-AC1-6_

  - [x] 4.2 Implement EvolutionEngine for long-term portrait evolution in evolution_engine.py
    - Create `runtime/src/avatar/evolution_engine.py`
    - Define `EvolutionEvent` dataclass: soul_id, event_type (betrayal_scar/reconciliation_soften/prestige_mark), triggered_at, metadata
    - Implement queue-based async processing
    - Implement `on_betrayal()`: queue scar/blemish layer addition via ControlNet inpainting
    - Implement `on_reconciliation()`: queue softened expression base generation
    - Implement `on_survival_milestone()`: queue prestige marks for agents surviving >7 rent cycles
    - Rate limit: max 1 evolution per agent per hour
    - All modifications use IP-Adapter reference from avatar_base_cid for identity consistency
    - Store pending events if ComfyUI unavailable, retry on next health probe
    - _Requirements: R13-AC1-8_

- [x] 5. Integration layer
  - [x] 5.1 Implement pipeline observability with structured JSON logging
    - Add structured JSON logging to GenesisPipeline
    - Log pipeline start: soul_id, archetype, timestamp, correlation_id
    - Log step completions: step_name, duration_ms, success/failure
    - Log finish summary: total_duration_ms, assets_produced (0-4), status, which specific assets produced/skipped
    - Implement status query interface: accepts soul_id, returns pending/running/complete/partial/failed
    - Return no-record indication for unknown soul_ids
    - Retain status for process lifetime
    - _Requirements: R10-AC1-7_

  - [x] 5.2 Integrate pipeline dispatch into seed_agents.py
    - In `seed_one_agent()`, after graph creation + IPFS pin, dispatch `GenesisPipeline.execute()` via `asyncio.create_task()`
    - Pass soul_id, archetype, and graph reference
    - Wrap in try/except: log warning on failure, return result unchanged
    - Gate on `AVATAR_GENESIS_ENABLED` env var (default true)
    - Ensure non-blocking: seed_one_agent() returns immediately without waiting for pipeline
    - _Requirements: R1-AC1-3_

  - [x] 5.3 Integrate VisualReactor and SceneComposer into AvatarSurface in avatar/engine.py
    - In `compose()` method: check visual_state.expression_override
    - If override active and not expired (current epoch < override_expiry_epoch): use override expression
    - If override expired: clear the override fields
    - Call SceneComposer when multiple agents are present in scene
    - Update `runtime/src/avatar/__init__.py` exports to include VisualReactor, SceneComposer, and new components
    - _Requirements: R11-AC6 R12-integration_

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "2.1", "2.2", "3.4", "3.5"] },
    { "id": 1, "tasks": ["3.1", "3.2", "3.3"] },
    { "id": 2, "tasks": ["4.1", "4.2"] },
    { "id": 3, "tasks": ["5.1", "5.2", "5.3"] }
  ]
}
```

## Notes

- All tests must run via `docker exec` per workspace testing convention.
- ComfyUI and Fish Speech services require GPU access — local dev may use CPU fallback with degraded quality.
- Seed utterances (.wav files) are archetype-specific audio samples that must be recorded/sourced separately — Task 1.2 creates placeholders only.
- The IPFS integration reuses the existing `pin_to_ipfs()` pattern from owned_graph.py.
- Evolution engine (Task 4.2) is event-driven and should integrate with the existing event_emitter.py pattern if available.
