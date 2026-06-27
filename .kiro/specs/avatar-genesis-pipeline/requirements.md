# Requirements Document

## Introduction

The Avatar Genesis Pipeline automatically generates visual and voice identity assets when an agent is seeded via `seed_one_agent()`, and keeps those assets **alive** by binding them to the banter engine's emotional state, relationship memory, and dramatic beats. It produces a canonical portrait, expression sheet, voice embedding with prosody tags, and associated metadata — all pinned to IPFS and registered in the agent's `AgentIdentity`. At runtime, the avatar visibly reacts to CRACK moments, landed hits, betrayals, and tension shifts — making the Elders feel like living cosmic entities, not static portraits with audio.

The pipeline runs asynchronously so agent seeding is never blocked, and degrades gracefully when generation services (ComfyUI, Fish Speech / CosyVoice) are unavailable.

## Glossary

- **Pipeline**: The orchestrated sequence of image generation, expression sheet creation, voice cloning, IPFS pinning, and identity registration that produces all avatar assets for a single agent.
- **ComfyUI_Service**: The ComfyUI HTTP API sidecar that executes Flux-based image generation workflows via IP-Adapter FaceID for character consistency.
- **TTS_Service**: The Fish Speech S2 or CosyVoice 2.0 HTTP API sidecar that produces zero-shot voice clones from seed utterances.
- **Canonical_Portrait**: A single archetype-styled reference face image that establishes the agent's visual identity.
- **Expression_Sheet**: A set of variant images (neutral, angry, playful, calm, intense, vulnerable, flinch) derived from the canonical portrait for use in runtime expression mapping.
- **Voice_Embedding**: A speaker embedding vector produced by the TTS_Service from a short archetype-specific seed utterance, enabling zero-shot voice cloning at runtime.
- **Prosody_Tags**: Emotional inflection markers (`[whisper]`, `[emphasis]`, `[laugh]`, `[cold]`, `[wounded]`) that the TTS_Service uses at runtime to modulate speech delivery based on the current dramatic state.
- **Agent_Seeder**: The `seed_one_agent()` async function in `seed_agents.py` that creates, pins, and registers a new agent.
- **AgentIdentity**: The dataclass in `owned_graph.py` holding mutable identity fields including `avatar_cid`, `avatar_style_prompt`, `voice_model_cid`, `voice_params`, `mood_mapping`, and `color_palette`.
- **IPFS_Store**: The IPFS daemon used for content-addressed asset storage, accessed via HTTP API.
- **Style_Prompt**: A text prompt encoding archetype visual characteristics (color palette, emblem motifs, facial features) AND current soul state (relationship scars, tension marks) used to drive image generation.
- **Seed_Utterance**: A short (5–15 second) archetype-specific audio sample used as the reference for zero-shot voice cloning.
- **Archetype**: One of eight agent personality types (trader, hoarder, explorer, parasite, cooperator, defender, philosopher, builder) that determines visual and voice style.
- **Visual_State**: A runtime-mutable record of the Elder's current expression, modifications (scars, marks), and presentation mode, updated by the banter engine after every delivered beat.
- **CRACK_Beat**: A specific Move type in the banter engine representing a moment of vulnerability or emotional breakthrough that demands visible avatar reaction.
- **Landed_Hit**: A banter beat with quality_score > 12 that the receiving Elder must visibly react to.
- **PairState**: The relationship state between two Elders including tension_level, reconciliation_arc status, recent_betrayal, and last_wound_summary.
- **Scene_Composition**: The spatial arrangement, relative positioning, and visual hierarchy of multiple Elders in a group scene.

## Requirements

### Requirement 1: Pipeline Trigger on Agent Seed

**User Story:** As the system operator, I want avatar genesis to trigger automatically when an agent is seeded, so that every new agent receives visual and voice identity without manual intervention.

#### Acceptance Criteria

1. WHEN `seed_one_agent()` completes graph creation and IPFS pinning, THE Agent_Seeder SHALL dispatch the Pipeline as an asynchronous task, passing the agent's soul_id, archetype, and the full AgentIdentity reference to the Pipeline.
2. THE Agent_Seeder SHALL return the agent registration result dictionary without waiting for the Pipeline to complete.
3. IF the attempt to create or schedule the Pipeline async task raises an exception, THEN THE Agent_Seeder SHALL log a warning containing the agent's soul_id and the exception message, and return the agent registration result unchanged.

### Requirement 2: Canonical Portrait Generation

**User Story:** As the system operator, I want each agent to have a consistent base portrait image derived from its archetype AND its nuclear soul prompt, so that the agent has a recognizable visual identity that reflects its inner nature.

#### Acceptance Criteria

1. WHEN the Pipeline begins for an agent, THE Pipeline SHALL construct a Style_Prompt of no more than 500 characters incorporating the agent's archetype color palette, symbolic emblem, archetype-specific facial characteristics, AND personality descriptors derived from the archetype's VoiceDNAProfile system_prompt field.
2. WHEN a Style_Prompt is constructed, THE Pipeline SHALL submit a Flux image generation workflow to the ComfyUI_Service using IP-Adapter FaceID for character consistency, with a per-request timeout of 60 seconds.
3. WHEN the ComfyUI_Service returns a generated image, THE Pipeline SHALL validate that the image is a PNG or JPEG file of at least 1 KB in size with minimum dimensions of 512×512 pixels.
4. IF image validation fails, THEN THE Pipeline SHALL discard the invalid image, log a warning including the agent's soul_id and the validation failure reason, and treat the portrait generation step as failed.
5. WHEN a valid Canonical_Portrait image is produced, THE Pipeline SHALL pin the image to the IPFS_Store and record the resulting CID.
6. THE Pipeline SHALL generate exactly one Canonical_Portrait per agent per pipeline execution.

### Requirement 3: Expression Sheet Generation

**User Story:** As the system operator, I want each agent to have multiple expression variants including vulnerability and flinch states, so that the AvatarSurface can display contextually appropriate expressions during dramatic moments.

#### Acceptance Criteria

1. WHEN a Canonical_Portrait is successfully generated, THE Pipeline SHALL generate an Expression_Sheet containing images for: neutral, angry, playful, calm, intense, vulnerable, and flinch expressions.
2. THE Pipeline SHALL use the Canonical_Portrait as the IP-Adapter reference input to maintain facial identity consistency across all expression variants.
3. WHEN expression variant generation is complete (whether all or partial), THE Pipeline SHALL validate each generated image is a non-zero-byte PNG or JPEG file, bundle all valid expression images as a single IPFS directory (DAG), and pin it to the IPFS_Store.
4. WHEN the Expression_Sheet directory is pinned to the IPFS_Store, THE Pipeline SHALL record the Expression_Sheet directory CID alongside the Canonical_Portrait CID.
5. IF generation of any individual expression variant fails, THEN THE Pipeline SHALL continue generating remaining variants and pin whatever was successfully produced, provided at least one variant image is valid.
6. IF all expression variant generations fail, THEN THE Pipeline SHALL skip Expression_Sheet pinning, log a warning including the agent's soul_id and failure reasons, and continue pipeline execution without recording an Expression_Sheet CID.
7. THE Expression_Sheet SHALL include a "vulnerable" variant specifically designed for CRACK beat reactions and a "flinch" variant for landed-hit reactions.

### Requirement 4: Voice Embedding with Prosody Generation

**User Story:** As the system operator, I want each agent to have a unique voice profile with emotional prosody capabilities, so that the VoiceSurface can modulate speech delivery based on the dramatic state of the conversation.

#### Acceptance Criteria

1. WHEN the Pipeline begins for an agent, THE Pipeline SHALL select a Seed_Utterance matching the agent's archetype from the configured utterance library.
2. IF no Seed_Utterance exists in the utterance library for the agent's archetype, THEN THE Pipeline SHALL skip voice embedding generation, log a warning including the agent's soul_id and archetype, and continue pipeline execution without modifying voice-related AgentIdentity fields.
3. WHEN a Seed_Utterance is selected, THE Pipeline SHALL submit a zero-shot voice cloning request to the TTS_Service to produce a Voice_Embedding.
4. WHEN the TTS_Service returns a Voice_Embedding, THE Pipeline SHALL validate that the embedding is a non-zero-byte payload before pinning it to the IPFS_Store and recording the resulting CID.
5. THE Pipeline SHALL derive voice parameters from the archetype and store them as a dictionary containing at minimum the keys `timbre`, `pitch`, `speed`, AND `prosody_map` (mapping Move types to Prosody_Tags), in the `voice_params` field of AgentIdentity.
6. THE `prosody_map` SHALL map at minimum: CRACK → `[wounded]`, ESCALATE → `[emphasis]`, CONCEDE → `[whisper]`, TAUNT → `[cold]`, SILENCE → `[pause]`.
7. WHEN voice generation completes, THE Pipeline SHALL produce a verification audio sample between 1 and 10 seconds in duration using the generated Voice_Embedding and stored voice parameters, and confirm the sample is a non-zero-byte audio file.
8. IF the verification audio sample is zero bytes or fails to generate, THEN THE Pipeline SHALL discard the Voice_Embedding CID, log a warning including the agent's soul_id, and skip voice identity registration for that agent.

### Requirement 5: AgentIdentity Registration

**User Story:** As the system operator, I want all generated assets to be registered in the agent's AgentIdentity, so that the AvatarSurface and VoiceSurface can resolve them at runtime.

#### Acceptance Criteria

1. WHEN the Canonical_Portrait CID is available, THE Pipeline SHALL write the CID to `AgentIdentity.avatar_cid` for the target agent.
2. WHEN the Style_Prompt is constructed, THE Pipeline SHALL write the prompt text to `AgentIdentity.avatar_style_prompt` for the target agent.
3. WHEN the Voice_Embedding CID is available, THE Pipeline SHALL write the CID to `AgentIdentity.voice_model_cid` for the target agent.
4. WHEN voice parameters are derived, THE Pipeline SHALL write the parameters (including `prosody_map`) to `AgentIdentity.voice_params` for the target agent.
5. WHEN expression variants are generated (including partial sets from incomplete generation), THE Pipeline SHALL write a mood-to-expression CID mapping to `AgentIdentity.mood_mapping` containing only the moods for which a variant image was successfully produced.
6. WHEN all successfully produced identity fields have been written to the AgentIdentity, THE Pipeline SHALL re-pin the updated OwnedGraph to the IPFS_Store and update the agent's `graph_cid` in PostgreSQL within a single operation such that the PostgreSQL update only commits if the IPFS pin succeeds.
7. IF the IPFS re-pin or PostgreSQL `graph_cid` update fails after 3 retry attempts, THEN THE Pipeline SHALL leave the agent's prior `graph_cid` unchanged, log a structured error entry including the agent's soul_id and the failure reason, and mark the pipeline execution as failed.
8. THE Pipeline SHALL not modify any AgentIdentity field that was not successfully produced during the current pipeline execution, preserving any pre-existing values.

### Requirement 6: Graceful Degradation

**User Story:** As the system operator, I want agent seeding to succeed even when generation services are unavailable, so that system availability does not depend on sidecar services.

#### Acceptance Criteria

1. IF the ComfyUI_Service is unreachable (connection not established within 5 seconds) or returns a non-2xx HTTP response, THEN THE Pipeline SHALL skip portrait and expression generation, log a warning, and continue with voice generation.
2. IF the TTS_Service is unreachable (connection not established within 5 seconds) or returns a non-2xx HTTP response, THEN THE Pipeline SHALL skip voice embedding generation, log a warning, and finalize with whatever assets were successfully produced.
3. IF both generation services are unavailable, THEN THE Pipeline SHALL complete without modifying any AgentIdentity visual or voice fields, leaving them at their default empty values.
4. IF the IPFS_Store is unreachable during asset pinning, THEN THE Pipeline SHALL retry pinning up to 3 times with exponential backoff (initial delay 2 seconds, doubling each retry, maximum delay 8 seconds) before marking the asset as failed.
5. WHEN any pipeline step fails, THE Pipeline SHALL record the failure reason in a structured log entry including the agent's soul_id, the failed step name, and the error message.
6. IF a pipeline step fails after previous steps have already written fields to AgentIdentity, THEN THE Pipeline SHALL retain all successfully produced asset references in AgentIdentity and SHALL NOT roll back previously written fields.

### Requirement 7: Archetype-Specific Styling

**User Story:** As the system operator, I want each of the eight archetypes to have distinct visual and voice characteristics rooted in their nuclear soul prompts, so that agents are visually and audibly distinguishable by personality type.

#### Acceptance Criteria

1. THE Pipeline SHALL maintain a style configuration mapping each of the eight archetypes (trader, hoarder, explorer, parasite, cooperator, defender, philosopher, builder) to a distinct Style_Prompt template incorporating personality traits from the archetype's VoiceDNAProfile, where no two archetypes share an identical Style_Prompt template value.
2. THE Pipeline SHALL maintain a voice configuration mapping each archetype to voice parameters including timbre descriptor, pitch range (defined as a minimum and maximum frequency in Hz), speech cadence (defined in words per minute), AND a prosody_map defining Move-to-Tag mappings specific to the archetype's emotional range, where no two archetypes share an identical combination of all parameter values.
3. THE Pipeline SHALL maintain a Seed_Utterance library containing at least one utterance per archetype, where each utterance is 5–15 seconds in duration, is uniquely assigned to a single archetype, and reflects the archetype's characteristic speech patterns and personality.
4. WHEN generating assets for an archetype, THE Pipeline SHALL use only the style configuration, voice configuration, and seed utterance assigned to that archetype.
5. WHEN two agents of different archetypes are generated with identical generation seeds, THE Pipeline SHALL produce portraits that differ in at least the archetype-specific color palette values embedded in the Style_Prompt.
6. IF the style configuration, voice configuration, or Seed_Utterance library is missing an entry for any of the eight archetypes, THEN THE Pipeline SHALL reject the pipeline execution for that agent and log an error indicating the missing archetype configuration.
7. WHEN the Pipeline loads its archetype configurations at startup, THE Pipeline SHALL validate that exactly eight archetype entries exist and that each entry contains a non-empty Style_Prompt template, a complete set of voice parameters (including prosody_map), and at least one Seed_Utterance reference.

### Requirement 8: Docker Sidecar Integration

**User Story:** As the system operator, I want ComfyUI and TTS services configured as Docker sidecar containers, so that the pipeline runs in the existing containerized infrastructure.

#### Acceptance Criteria

1. THE Pipeline SHALL communicate with the ComfyUI_Service exclusively via HTTP API at a configurable endpoint (environment variable `COMFYUI_ENDPOINT`).
2. THE Pipeline SHALL communicate with the TTS_Service exclusively via HTTP API at a configurable endpoint (environment variable `TTS_ENDPOINT`).
3. WHEN the Pipeline starts, THE Pipeline SHALL perform a health check against both service endpoints by issuing an HTTP GET request and expecting an HTTP 200 response within 10 seconds per endpoint before submitting generation requests.
4. IF the `COMFYUI_ENDPOINT` or `TTS_ENDPOINT` environment variable is not set, THEN THE Pipeline SHALL treat the corresponding service as unavailable and skip its generation steps without raising an error.
5. THE Pipeline SHALL respect a configurable timeout (environment variable `PIPELINE_TIMEOUT_SECONDS`, default 300) for the total pipeline execution per agent.
6. THE Pipeline SHALL resolve ComfyUI_Service and TTS_Service by their Docker Compose service hostnames when `COMFYUI_ENDPOINT` and `TTS_ENDPOINT` reference those hostnames, requiring no additional network configuration beyond the shared Compose network.

### Requirement 9: Asynchronous Execution and Concurrency

**User Story:** As the system operator, I want the pipeline to run asynchronously and handle concurrent agent seedings, so that batch genesis of multiple agents completes efficiently.

#### Acceptance Criteria

1. THE Pipeline SHALL execute as an asyncio task such that `seed_one_agent()` returns its agent registration result before the Pipeline task completes.
2. WHILE multiple agents are being seeded concurrently, THE Pipeline SHALL limit concurrent ComfyUI_Service requests to a configurable maximum (environment variable `COMFYUI_CONCURRENCY`, default 2, valid range 1–16).
3. WHILE multiple agents are being seeded concurrently, THE Pipeline SHALL limit concurrent TTS_Service requests to a configurable maximum (environment variable `TTS_CONCURRENCY`, default 4, valid range 1–16).
4. WHEN a pipeline task is awaiting a service response, THE Pipeline SHALL yield control to the event loop so other pipeline tasks can progress.
5. IF the pipeline execution exceeds `PIPELINE_TIMEOUT_SECONDS`, THEN THE Pipeline SHALL cancel remaining generation steps, abandon any in-flight service requests, write already-completed asset CIDs to AgentIdentity, and log a timeout warning identifying the agent's soul_id and which steps were skipped.
6. WHEN a pipeline task cannot acquire a service concurrency slot within 30 seconds, THE Pipeline SHALL treat the step as failed, log a concurrency-wait timeout, and continue to the next pipeline step.

### Requirement 10: Pipeline Observability

**User Story:** As the system operator, I want structured logging and status tracking for pipeline executions, so that I can monitor asset generation health and debug failures.

#### Acceptance Criteria

1. WHEN a pipeline execution begins, THE Pipeline SHALL log a JSON-formatted structured entry containing the agent's soul_id, archetype, pipeline start timestamp, and a correlation identifier unique to that execution.
2. WHEN each pipeline step completes (portrait, expression sheet, voice embedding, identity registration), THE Pipeline SHALL log a JSON-formatted structured entry with the agent's soul_id, execution correlation identifier, step name, duration in milliseconds, and success/failure status.
3. WHEN a pipeline execution finishes, THE Pipeline SHALL log a JSON-formatted structured summary containing the agent's soul_id, execution correlation identifier, total duration in milliseconds, number of assets produced (0 to 4), and final status (complete, partial, failed).
4. THE Pipeline SHALL expose a status query interface that accepts a soul_id and returns the current state (pending, running, complete, partial, failed) for that agent's pipeline execution.
5. IF a status query is made for a soul_id with no matching pipeline execution, THEN THE Pipeline SHALL return an indication that no execution record exists for the given soul_id.
6. WHEN a pipeline execution completes with partial results, THE Pipeline SHALL include in the summary log which specific assets were produced and which were skipped, identifying each by asset type (portrait, expression_sheet, voice_embedding).
7. THE Pipeline SHALL retain pipeline execution status for at least the duration of the current process lifetime, such that status queries return results for any execution started since the process was launched.

### Requirement 11: Runtime Visual Reactivity (Soul-Aware Visual State)

**User Story:** As a viewer, I want the avatar to visibly react to the emotional and dramatic state of the conversation, so the character feels alive on stream and not like a static image.

#### Acceptance Criteria

1. THE AgentIdentity SHALL include a `visual_state` field (dictionary) containing at minimum: `current_expression`, `expression_override`, `override_expiry_epoch`, `scar_layers`, and `presentation_mode`.
2. WHEN the BanterEngine delivers a beat, THE AvatarSurface SHALL update the speaking Elder's `visual_state.current_expression` based on the beat's Move type and the current PairState tension_level.
3. WHEN a CRACK beat is delivered, THE AvatarSurface SHALL force the speaking Elder's expression to "vulnerable" for a duration between 15 and 40 seconds (configurable via `CRACK_EXPRESSION_DURATION_SECONDS`, default 25), overriding the normal expression selection.
4. WHEN a Landed_Hit occurs (quality_score > 12), THE AvatarSurface SHALL force the receiving Elder's expression to "flinch" for a duration between 5 and 15 seconds (configurable via `FLINCH_EXPRESSION_DURATION_SECONDS`, default 8).
5. THE AvatarSurface SHALL map Move types to expressions as follows: ESCALATE → intense, TAUNT → angry, CONCEDE → calm, DEFLECT → playful, QUESTION → attentive, PIVOT → animated, SILENCE → calm, CALLBACK → playful, COUNTER → intense.
6. WHEN an expression_override is active (current epoch < override_expiry_epoch), THE AvatarSurface SHALL use the override expression instead of the Move-based mapping.
7. THE `visual_state` SHALL be persisted in the agent's runtime state (not IPFS — this is ephemeral per-session state with optional DB persistence for cross-session scar memory).

### Requirement 12: Consistent Multi-Agent Scene Composition

**User Story:** As a viewer, I want group scenes to show multiple Elders with consistent visual hierarchy reflecting who dominates the conversation, so the stream feels like watching a living theater.

#### Acceptance Criteria

1. WHEN multiple Elders are active in a scene (SceneContextData has 2+ speakers in recent_beats), THE AvatarSurface SHALL generate a scene composition layout specifying each Elder's relative position, scale, and z-order.
2. THE Elder who currently "has_the_room" (highest average quality score across recent beats) SHALL be positioned in the dominant frame position (center or foreground, largest scale).
3. WHEN has_the_room changes from one Elder to another, THE scene composition SHALL transition the layout over 2–4 seconds (not instantaneous) to avoid jarring visual jumps.
4. THE scene composition SHALL assign z-order based on the current speaking order: active speaker foreground, last speaker mid-ground, others background.
5. WHEN tension_level between two on-screen Elders exceeds 7, THE scene composition SHALL reduce the visual distance between them (closer framing implies confrontation).
6. THE scene composition SHALL output a layout specification containing per-Elder: position (x, y normalized 0-1), scale (0.5-1.0), z-order (integer), and active expression — suitable for consumption by the rendering layer (OBS scene switching, MuseTalk multi-feed, or compositing pipeline).
7. THE scene composition SHALL support 2, 3, and 4 Elder configurations with predefined base layouts that are dynamically adjusted by power dynamics.

### Requirement 13: Avatar Evolution Rules

**User Story:** As a viewer, I want Elders to visually evolve over time — gaining scars from betrayals, softening during reconciliation arcs, and showing prestige from survival — so they feel like beings with history written on their faces.

#### Acceptance Criteria

1. WHEN a betrayal event is recorded in RelationshipMemory (InteractionRecord.betrayal == True AND the agent is the target), THE Pipeline SHALL queue an evolution task that adds a scar/blemish layer to the agent's Canonical_Portrait via ControlNet inpainting on the ComfyUI_Service.
2. WHEN a reconciliation_arc becomes active in PairState for an agent, THE Pipeline SHALL queue an evolution task that generates a softened expression base (slightly relaxed features, warmer lighting) and stores it as an alternate Canonical_Portrait variant.
3. WHEN an agent has survived more than 7 consecutive rent cycles without entering "throttled" or "sleeping" execution_status, THE Pipeline SHALL queue an evolution task that adds subtle prestige markings (richer colors, sharper features, slight glow/aura) to the Canonical_Portrait.
4. ALL evolution modifications SHALL be layered on top of the original Canonical_Portrait using the same IP-Adapter reference to maintain identity consistency. The original portrait CID SHALL be preserved as `avatar_base_cid` for future evolution operations.
5. WHEN an evolution task completes, THE Pipeline SHALL update `AgentIdentity.avatar_cid` to the new evolved portrait CID, add the modification type and timestamp to `AgentIdentity.visual_state.scar_layers`, and re-pin the OwnedGraph.
6. EVOLUTION tasks SHALL execute asynchronously and SHALL NOT block the banter engine or runtime loop. They SHALL use the same concurrency controls as genesis pipeline tasks (respecting COMFYUI_CONCURRENCY).
7. THE Pipeline SHALL limit evolution tasks to a maximum of one per agent per hour to prevent rapid visual thrashing during high-tension sequences.
8. IF the ComfyUI_Service is unavailable when an evolution task is queued, THE Pipeline SHALL store the pending evolution event and retry when the service becomes available (checked on next health probe cycle).

### Requirement 14: Voice Performance Binding

**User Story:** As a viewer, I want Elders' voices to audibly shift in response to the dramatic state — whispering during vulnerability, sharpening during confrontation — so the audio feels emotionally intelligent, not just read aloud.

#### Acceptance Criteria

1. WHEN the VoiceSurface composes a VoicePlan for a beat, THE VoiceSurface SHALL consult the speaking Elder's `voice_params.prosody_map` to select the appropriate Prosody_Tag for the current Move type.
2. WHEN a Prosody_Tag is selected, THE VoiceSurface SHALL prepend or wrap the beat's text with the appropriate tag syntax before submitting to the TTS_Service (e.g., `[wounded]I always get what I want[/wounded]` for a CRACK beat by a parasite).
3. WHEN the PairState tension_level exceeds 7, THE VoiceSurface SHALL apply a global speed modifier of +8% and pitch modifier of +5% to convey heightened intensity, regardless of Move type.
4. WHEN a reconciliation_arc is active in PairState, THE VoiceSurface SHALL apply a global speed modifier of -5% (slower, more deliberate) for the reconciling Elder.
5. WHEN the current beat's quality_score exceeds 12 (Landed_Hit), THE VoiceSurface SHALL apply the `[emphasis]` Prosody_Tag to the delivering Elder's line, stacking with any Move-based tag.
6. THE VoiceSurface SHALL pass the emotional_texture score from the QualityScore to the TTS_Service as a control parameter, mapping scores 0-1 to baseline delivery, and scores 2-3 to progressively more emotionally inflected delivery.
7. IF the TTS_Service does not support Prosody_Tags (detected via missing capability in health check response), THE VoiceSurface SHALL fall back to speed/pitch modifiers only and log a degraded-mode warning.
