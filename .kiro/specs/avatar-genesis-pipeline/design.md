# Technical Design: Avatar Genesis Pipeline

## Overview

This design implements the Avatar Genesis Pipeline as a soul-aware, async asset generation system that produces visual and voice identity at agent seeding, then keeps those assets alive through runtime emotional reactivity and long-term evolution. The system integrates with the existing banter engine's emotional architecture (CRACK beats, PairState, QualityScore, Move types) to make Elders feel like living beings on stream.

#[[file:requirements.md]]

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SEED TIME (one-shot)                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  seed_one_agent()                                                    │
│       │                                                              │
│       ▼                                                              │
│  genesis_pipeline.dispatch(soul_id, archetype, identity_ref)         │
│       │                                                              │
│       ├──► PortraitGenerator (ComfyUI API)                           │
│       │         └── Flux + IP-Adapter FaceID                         │
│       │         └── Style_Prompt from archetype + soul DNA           │
│       │                                                              │
│       ├──► ExpressionSheetGenerator (ComfyUI API)                    │
│       │         └── 7 variants: neutral, angry, playful, calm,       │
│       │              intense, vulnerable, flinch                      │
│       │         └── IP-Adapter ref = canonical portrait              │
│       │                                                              │
│       ├──► VoiceCloner (Fish Speech S2 / CosyVoice API)             │
│       │         └── Zero-shot from Seed_Utterance                    │
│       │         └── Outputs: embedding + prosody_map                 │
│       │                                                              │
│       └──► IdentityRegistrar                                         │
│                 └── Write CIDs to AgentIdentity                      │
│                 └── Re-pin OwnedGraph to IPFS                        │
│                 └── Update graph_cid in PostgreSQL                    │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                      RUNTIME (per-beat, reactive)                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  BanterEngine.deliver_beat()                                         │
│       │                                                              │
│       ▼                                                              │
│  VisualReactor (new)                                                 │
│       ├── Maps Move type → expression via mood_mapping               │
│       ├── Detects CRACK → forces "vulnerable" (15-40s)               │
│       ├── Detects Landed_Hit → forces "flinch" on receiver (5-15s)   │
│       └── Updates visual_state in agent runtime record               │
│                                                                      │
│  VoiceSurface.compose() (enhanced)                                   │
│       ├── Reads prosody_map from voice_params                        │
│       ├── Wraps text in Prosody_Tags based on Move type              │
│       ├── Modulates speed/pitch based on tension_level               │
│       └── Passes emotional_texture score to TTS_Service              │
│                                                                      │
│  SceneComposer (new)                                                 │
│       ├── Reads SceneContextData (has_the_room, recent_beats)        │
│       ├── Computes layout: position, scale, z-order per Elder        │
│       ├── Adjusts for tension (closer = confrontation)               │
│       └── Outputs scene layout spec for rendering layer              │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                     EVOLUTION (async, event-driven)                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  EvolutionEngine (new)                                               │
│       ├── Listens for: betrayal events, reconciliation arcs,         │
│       │                 survival milestones                           │
│       ├── Queues ControlNet inpainting tasks to ComfyUI              │
│       ├── Rate-limited: max 1 evolution per agent per hour           │
│       └── Updates avatar_cid, preserves avatar_base_cid             │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. GenesisPipeline (`runtime/src/avatar/genesis_pipeline.py`)

The orchestrator. Dispatched as an asyncio task from `seed_one_agent()`.

```python
@dataclass
class PipelineResult:
    soul_id: str
    correlation_id: str
    status: Literal["complete", "partial", "failed"]
    portrait_cid: str | None
    expression_sheet_cid: str | None
    voice_embedding_cid: str | None
    assets_produced: int
    duration_ms: int
    errors: list[dict]

class GenesisPipeline:
    def __init__(self):
        self._comfyui_semaphore = asyncio.Semaphore(COMFYUI_CONCURRENCY)
        self._tts_semaphore = asyncio.Semaphore(TTS_CONCURRENCY)
        self._status_registry: dict[str, PipelineResult] = {}

    async def execute(self, soul_id: str, archetype: str, graph: OwnedGraph) -> PipelineResult:
        """Full pipeline execution with graceful degradation."""
        ...

    def get_status(self, soul_id: str) -> PipelineResult | None:
        """Query pipeline status for observability."""
        ...
```

### 2. PortraitGenerator (`runtime/src/avatar/portrait_generator.py`)

Builds Style_Prompts from archetype configs + soul DNA, submits to ComfyUI.

```python
class PortraitGenerator:
    def __init__(self, comfyui_endpoint: str, semaphore: asyncio.Semaphore):
        ...

    async def generate_portrait(self, archetype: str, style_config: ArchetypeStyleConfig) -> bytes | None:
        """Submit Flux workflow to ComfyUI, return validated image bytes."""
        ...

    async def generate_expressions(self, portrait_ref: bytes, expressions: list[str]) -> dict[str, bytes]:
        """Generate expression variants using portrait as IP-Adapter ref."""
        ...
```

### 3. VoiceCloner (`runtime/src/avatar/voice_cloner.py`)

Handles Fish Speech S2 / CosyVoice zero-shot cloning + verification.

```python
class VoiceCloner:
    def __init__(self, tts_endpoint: str, semaphore: asyncio.Semaphore):
        ...

    async def clone_voice(self, seed_utterance_path: str, archetype: str) -> VoiceCloneResult | None:
        """Submit zero-shot clone request, validate embedding, produce verification sample."""
        ...

@dataclass
class VoiceCloneResult:
    embedding_bytes: bytes
    voice_params: dict  # includes prosody_map
    verification_sample: bytes
```

### 4. ArchetypeConfig (`runtime/src/avatar/archetype_config.py`)

Static configuration for all 8 archetypes — visual + voice + utterances.

```python
@dataclass(frozen=True)
class ArchetypeStyleConfig:
    archetype: str
    style_prompt_template: str  # max 500 chars
    color_palette: dict[str, str]
    emblem: str
    soul_trait_keywords: list[str]
    voice_timbre: str
    voice_pitch_range: tuple[int, int]  # Hz
    voice_cadence_wpm: int
    prosody_map: dict[str, str]  # Move type → Prosody_Tag
    seed_utterance_path: str

ARCHETYPE_CONFIGS: dict[str, ArchetypeStyleConfig] = { ... }  # all 8
```

### 5. VisualReactor (`runtime/src/avatar/visual_reactor.py`)

Runtime component that updates visual_state based on banter beats.

```python
class VisualReactor:
    MOVE_EXPRESSION_MAP: dict[str, str] = {
        "ESCALATE": "intense", "TAUNT": "angry", "CONCEDE": "calm",
        "DEFLECT": "playful", "QUESTION": "attentive", "PIVOT": "animated",
        "SILENCE": "calm", "CALLBACK": "playful", "COUNTER": "intense",
        "CRACK": "vulnerable",
    }

    def on_beat_delivered(self, beat: Beat, pair_state: PairState, agents: dict) -> None:
        """Update visual_state for speaker and potentially receiver."""
        ...

    def on_landed_hit(self, beat: Beat, receiver_soul_id: str) -> None:
        """Force flinch expression on receiver."""
        ...
```

### 6. SceneComposer (`runtime/src/avatar/scene_composer.py`)

Computes multi-Elder layout from SceneContextData.

```python
@dataclass
class ElderLayout:
    soul_id: str
    position: tuple[float, float]  # normalized x, y (0-1)
    scale: float  # 0.5 - 1.0
    z_order: int
    expression: str

@dataclass
class SceneLayout:
    elders: list[ElderLayout]
    transition_duration_s: float
    composition_type: Literal["duo", "trio", "quad"]

class SceneComposer:
    BASE_LAYOUTS: dict[int, list[tuple[float, float]]] = {
        2: [(0.3, 0.5), (0.7, 0.5)],
        3: [(0.2, 0.5), (0.5, 0.4), (0.8, 0.5)],
        4: [(0.2, 0.6), (0.4, 0.4), (0.6, 0.4), (0.8, 0.6)],
    }

    def compose_scene(self, scene_ctx: SceneContextData, pair_states: dict, visual_states: dict) -> SceneLayout:
        ...
```

### 7. EvolutionEngine (`runtime/src/avatar/evolution_engine.py`)

Event-driven portrait evolution with rate limiting.

```python
@dataclass
class EvolutionEvent:
    soul_id: str
    event_type: Literal["betrayal_scar", "reconciliation_soften", "prestige_mark"]
    triggered_at: float
    metadata: dict

class EvolutionEngine:
    MAX_EVOLUTIONS_PER_HOUR = 1

    async def on_betrayal(self, soul_id: str, pair_state: PairState) -> None: ...
    async def on_reconciliation(self, soul_id: str, pair_state: PairState) -> None: ...
    async def on_survival_milestone(self, soul_id: str, rent_cycles: int) -> None: ...
    async def _process_queue(self) -> None: ...
```

## Data Models

### AgentIdentity additions (in `owned_graph.py`):

```python
@dataclass
class AgentIdentity:
    # ... existing fields ...

    # NEW: Evolution tracking
    avatar_base_cid: str = ""  # original genesis portrait (never overwritten)
    visual_state: dict = field(default_factory=lambda: {
        "current_expression": "neutral",
        "expression_override": "",
        "override_expiry_epoch": 0,
        "scar_layers": [],  # list of {"type": str, "timestamp": int, "source_soul_id": str}
        "presentation_mode": "standard",  # "standard" | "dominant" | "wounded" | "evolved"
    })
```

### VoicePlan enhancement (in `voice/state.py`):

```python
@dataclass(frozen=True)
class VoicePlan:
    # ... existing fields ...

    # NEW: Prosody binding
    prosody_tag: str = ""  # e.g. "[wounded]", "[emphasis]", "[cold]"
    emotional_texture_score: int = 0  # 0-3 from QualityScore
    tension_speed_modifier: float = 1.0
    tension_pitch_modifier: float = 1.0
```

### PipelineResult (new, in genesis_pipeline.py):

```python
@dataclass
class PipelineResult:
    soul_id: str
    correlation_id: str
    status: Literal["complete", "partial", "failed"]
    portrait_cid: str | None = None
    expression_sheet_cid: str | None = None
    voice_embedding_cid: str | None = None
    assets_produced: int = 0
    duration_ms: int = 0
    errors: list[dict] = field(default_factory=list)
```

## Error Handling

### Service Unavailability
- ComfyUI unreachable (5s connect timeout) or non-2xx: skip portrait + expressions, log, continue voice
- TTS unreachable (5s connect timeout) or non-2xx: skip voice embedding, log, finalize with visual assets
- Both unavailable: complete pipeline with no identity modifications

### IPFS Pin Failure
- Retry 3x with exponential backoff: 2s → 4s → 8s
- On final failure: mark asset as failed, log, continue remaining steps
- Re-pin + PostgreSQL update is atomic: PG commit only if pin succeeds

### Timeout
- Overall pipeline timeout (PIPELINE_TIMEOUT_SECONDS, default 300): cancel remaining, finalize with completed
- Concurrency slot wait timeout (30s): treat step as failed, continue
- Per-request timeout (60s for ComfyUI, 10s for health checks): treat as service failure

### Validation Failures
- Invalid image (wrong format, too small, wrong dimensions): discard, log, treat portrait step as failed
- Zero-byte voice embedding: discard, log, skip voice registration
- Failed verification audio: discard embedding, log, skip voice registration

### Rate Limiting (Evolution)
- Max 1 evolution per agent per hour: queue excess, process when cooldown expires
- If ComfyUI unavailable for evolution: store pending event, retry on next health cycle

## Correctness Properties

### Property 1: Non-blocking seeding
`seed_one_agent()` always returns its result before pipeline completes. No pipeline failure can prevent agent creation.
**Validates: Requirements 1.1, 1.2, 1.3**

### Property 2: Identity consistency
All expression variants use the canonical portrait as IP-Adapter reference, maintaining facial identity across moods.
**Validates: Requirements 3.2, 13.4**

### Property 3: Atomic registration
AgentIdentity updates + IPFS re-pin + PostgreSQL update succeed or fail together. No partial graph states are visible to the runtime.
**Validates: Requirements 5.6, 5.7**

### Property 4: Idempotent execution
Running the pipeline twice for the same soul_id produces the same final state (new CIDs, but same identity fields populated).
**Validates: Requirements 5.8**

### Property 5: Override expiry
Expression overrides always expire. The system never permanently locks an expression. Expiry is checked on every compose() call.
**Validates: Requirements 11.6**

### Property 6: Evolution preservation
`avatar_base_cid` is set once at genesis and never modified. All evolution builds on the original reference.
**Validates: Requirements 13.4, 13.5**

### Property 7: Graceful partial
If only portrait succeeds, the agent gets avatar_cid but empty voice_model_cid. The runtime handles missing fields gracefully (existing behavior).
**Validates: Requirements 6.3, 6.6**

## Testing Strategy

All tests run via `docker exec` per workspace convention.

### Unit Tests
- `test_archetype_config.py`: Validate all 8 configs present, non-empty templates, valid prosody_maps, startup validation function
- `test_visual_reactor.py`: Test Move→expression mapping, CRACK override timing, flinch on landed_hit, override expiry
- `test_scene_composer.py`: Test 2/3/4 Elder layouts, has_the_room dominance, tension proximity adjustment
- `test_genesis_pipeline.py`: Test orchestration flow with mocked services, timeout behavior, partial results
- `test_voice_prosody.py`: Test prosody_map lookup, tag wrapping, tension modifiers, fallback when no support

### Integration Tests (require Docker services)
- `test_comfyui_integration.py`: Health check, workflow submission, image retrieval, validation
- `test_fish_speech_integration.py`: Health check, clone request, embedding retrieval, verification sample
- `test_pipeline_e2e.py`: Full pipeline with live services, verify all CIDs populated

### Property Tests
- Expression override always expires within configured duration
- SceneComposer always assigns exactly one Elder as dominant (scale=1.0)
- Pipeline result.assets_produced matches count of non-None CID fields

## File Structure

```
runtime/src/avatar/
├── __init__.py              (updated: export new components)
├── engine.py                (updated: integrate VisualReactor + SceneComposer)
├── state.py                 (updated: add visual_state types)
├── archetype_config.py      (NEW: 8 archetype configs)
├── genesis_pipeline.py      (NEW: orchestrator)
├── portrait_generator.py    (NEW: ComfyUI integration)
├── voice_cloner.py          (NEW: Fish Speech / CosyVoice integration)
├── visual_reactor.py        (NEW: runtime beat → expression)
├── scene_composer.py        (NEW: multi-Elder layout)
└── evolution_engine.py      (NEW: long-term portrait evolution)

runtime/src/voice/
├── engine.py                (updated: prosody tag injection)
└── state.py                 (updated: prosody fields)

runtime/workflows/
├── README.md
├── flux_portrait.json       (NEW: Flux + IP-Adapter workflow)
├── flux_expression.json     (NEW: expression variant workflow)
└── controlnet_evolution.json (NEW: ControlNet inpainting)

runtime/seed_utterances/
├── README.md
├── trader.wav               (placeholder)
├── hoarder.wav              (placeholder)
├── explorer.wav             (placeholder)
├── parasite.wav             (placeholder)
├── cooperator.wav           (placeholder)
├── defender.wav             (placeholder)
├── philosopher.wav          (placeholder)
└── builder.wav              (placeholder)
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COMFYUI_ENDPOINT` | (none) | ComfyUI HTTP API URL |
| `TTS_ENDPOINT` | (none) | Fish Speech / CosyVoice API URL |
| `PIPELINE_TIMEOUT_SECONDS` | 300 | Max total pipeline execution time |
| `COMFYUI_CONCURRENCY` | 2 | Max concurrent ComfyUI requests |
| `TTS_CONCURRENCY` | 4 | Max concurrent TTS requests |
| `CRACK_EXPRESSION_DURATION_SECONDS` | 25 | Vulnerable expression after CRACK |
| `FLINCH_EXPRESSION_DURATION_SECONDS` | 8 | Flinch expression after landed hit |
| `AVATAR_EVOLUTION_ENABLED` | true | Enable/disable portrait evolution |
| `AVATAR_GENESIS_ENABLED` | true | Enable/disable genesis pipeline |
