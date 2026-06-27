# Implementation Plan: Broadcast-Quality Banter Engine

## Overview

Replace the current deterministic banter pipeline (`_banter_quality_score`, `_pick_reactive_move`, `_compose_reactive_banter`, `_banter_loop` in `archetype_graphs.py`) with a modular, multi-layered dialogue system under `runtime/src/banter/`. Implementation proceeds bottom-up: shared data models and database schema first, then independent leaf modules, then the orchestrator that wires everything together.

## Tasks

- [x] 1. Set up project structure, shared data models, and database schema
  - [x] 1.1 Create banter module directory and shared types
    - Create `runtime/src/banter/__init__.py` with module exports
    - Create `runtime/src/banter/types.py` with all shared dataclasses: `QualityScore`, `MoveDistribution`, `MoveContext`, `FallbackTemplate`, `FallbackSelection`, `InteractionRecord`, `PairState`, `Beat`, `SceneContextData`, `RouteDecision`, `CircuitBreakerState`, `PacingDecision`, `RepetitionVerdict`, `BeatResult`, `BanterConfig`, `SessionState`
    - Define custom exceptions: `QualityJudgeError`, `RelationshipMemoryError`, `ModelRouterError`
    - _Requirements: 1.1, 1.2, 2.1, 3.1, 4.2, 5.1, 6.1, 7.6, 8.1_

  - [x] 1.2 Create database migration for relationship memory tables
    - Create migration file adding `relationship_pairs` table with columns: `pair_id` (TEXT PK), `elder_a`, `elder_b`, `tension_level` (INTEGER 0-10 CHECK), `last_interaction_ts`, `reconciliation_arc`, `reconciliation_remaining`, `peak_tension_summary`, `created_at`, `updated_at`
    - Create `interaction_records` table with columns: `id` (SERIAL PK), `pair_id` (FK), `timestamp`, `elder_acting`, `move_used`, `emotional_valence` (CHECK IN positive/negative/neutral), `betrayal`, `alliance`, `concession`, `summary`
    - Create indexes: `idx_interaction_pair_ts` and `idx_interaction_significant`
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 1.3 Create test infrastructure and shared Hypothesis strategies
    - Create `tests/banter/conftest.py` with shared fixtures and Hypothesis strategies: `st_candidate_line()`, `st_archetype()`, `st_move()`, `st_move_sequence()`, `st_tension_level()`, `st_quality_score()`, `st_beat_sequence()`, `st_request_outcomes()`, `st_pacing_inputs()`, `st_fallback_template()`, `st_context_fragments()`
    - Create `tests/banter/__init__.py`
    - _Requirements: all (testing infrastructure)_

- [x] 2. Implement Quality_Judge module
  - [x] 2.1 Implement quality_judge.py with 5-dimension scoring
    - Create `runtime/src/banter/quality_judge.py`
    - Implement `evaluate()` async function that scores candidates across sharpness, emotional_texture, rhythm, thematic_relevance, and shareability dimensions (each 0-3)
    - Implement structural heuristics (clause count for rhythm, word count for sharpness)
    - Implement archetype vocabulary proximity scoring
    - Implement 2-second timeout enforcement raising `QualityJudgeError`
    - Implement `weak_dimensions` property for refinement feedback
    - _Requirements: 1.1, 1.2, 1.5, 1.6_

  - [x] 2.2 Write property test for Quality_Judge output invariants
    - **Property 1: Quality_Judge Output Invariants**
    - Test that for any candidate string (empty, single char, up to 1000 words), evaluate returns exactly 5 dimension scores each in [0, 3] or raises QualityJudgeError
    - **Validates: Requirements 1.1, 1.2**

  - [x] 2.3 Write unit tests for Quality_Judge
    - Test known-good lines produce scores above threshold
    - Test known-bad lines produce low scores
    - Test timeout behavior raises QualityJudgeError
    - Test empty/whitespace-only inputs
    - _Requirements: 1.1, 1.2, 1.5, 1.6_

- [x] 3. Implement Move_Selector module
  - [x] 3.1 Implement move_selector.py with probabilistic distributions
    - Create `runtime/src/banter/move_selector.py`
    - Implement `compute_distribution(ctx: MoveContext) -> MoveDistribution` with all invariants: sum to 1.0, signature move ≤ 0.40, non-signature ≥ 0.02
    - Implement consecutive-move penalty: after 2 consecutive same moves, reduce to 0.10
    - Implement counter-loop breaker: after 3+ consecutive COUNTERs, restrict to PIVOT/CONCEDE at 0.50 each
    - Implement tension > 7 adjustment: CONCEDE+PIVOT += 0.30
    - Implement fear keyword matching: ESCALATE+QUESTION += 0.20
    - Implement "losing the room" rule: PIVOT = 0.50 after 2 consecutive scores < 6
    - Implement `MoveDistribution.sample()` weighted random selection
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 3.4, 5.4_

  - [x] 3.2 Write property test for move distribution invariants
    - **Property 10: Move Distribution Invariants**
    - Test that for any archetype and input combination, distribution sums to 1.0 ±0.01, signature move ≤ 0.40, every non-signature move ≥ 0.02
    - **Validates: Requirements 4.2**

  - [x] 3.3 Write property test for consecutive move penalty
    - **Property 11: Consecutive Move Penalty**
    - Test that after 2 consecutive identical moves, that move's probability is exactly 0.10 with redistributed weight
    - **Validates: Requirements 4.3**

  - [x] 3.4 Write property test for counter-loop breaker
    - **Property 12: Counter-Loop Breaker**
    - Test that after 3+ consecutive COUNTERs, distribution is exactly {PIVOT: 0.50, CONCEDE: 0.50}
    - **Validates: Requirements 4.4**

  - [x] 3.5 Write property test for high-tension move adjustment
    - **Property 9: High-Tension Move Adjustment**
    - Test that when tension > 7, CONCEDE+PIVOT probability increases by at least 30pp while total remains 1.0
    - **Validates: Requirements 3.4**

- [x] 4. Implement Fallback_Pool module
  - [x] 4.1 Implement fallback_pool.py with weighted selection and substitution
    - Create `runtime/src/banter/fallback_pool.py`
    - Implement `FallbackPool` class with template loading and validation (≥12 per archetype, ≥2 per archetype×move)
    - Implement weighted random selection with 50% reduction for last-10-beats and 80% reduction for session-used
    - Implement context substitution with graceful placeholder omission (no raw `{tokens}` in output)
    - Implement `reset_session()` for new broadcast streams
    - Implement exclusion set support for anti-repetition forced fallback
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [x] 4.2 Create fallback template data file
    - Create `runtime/src/banter/templates/fallback_templates.json` (or YAML)
    - Populate with minimum 12 templates per archetype (8 archetypes × 12+ templates)
    - Ensure at least 2 templates per archetype×move type combination
    - Templates must use `{opponent}`, `{theme}`, `{callback}` placeholders where appropriate
    - _Requirements: 2.1, 2.5_

  - [x] 4.3 Write property test for fallback pool completeness
    - **Property 4: Fallback Pool Completeness**
    - Test that for any archetype, pool has ≥12 templates total and ≥2 per move type
    - **Validates: Requirements 2.1, 2.5**

  - [x] 4.4 Write property test for no raw template tokens
    - **Property 5: No Raw Template Tokens in Output**
    - Test that for any template and any combination of available/unavailable context, output never contains `{word}` patterns
    - **Validates: Requirements 2.3, 2.4**

  - [x] 4.5 Write property test for fallback weight decay
    - **Property 6: Fallback Weight Decay**
    - Test that templates used in last 10 beats get 50% reduction, session-used get 80% reduction
    - **Validates: Requirements 2.2, 2.6**

- [x] 5. Checkpoint - Ensure all tests pass
  - Copy tests into container: `docker cp runtime/tests god-runtime:/app/tests`
  - Clear stale pycache: `docker exec god-runtime find /app -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null`
  - Run all banter tests: `docker exec -w /app god-runtime python -m pytest tests/banter/ -v --tb=short`
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement Relationship_Memory module
  - [x] 6.1 Implement relationship_memory.py with PostgreSQL persistence
    - Create `runtime/src/banter/relationship_memory.py`
    - Implement `RelationshipMemory` class using existing `db_pool.py` connection
    - Implement `record_interaction()` to persist and update tension
    - Implement `get_significant_history()` with significance filter (non-neutral OR betrayal/alliance/concession)
    - Implement `get_tension()` with lazy 24h decay on read
    - Implement `update_tension()`: +1 for ESCALATE/TAUNT, -1 for CONCEDE/DEFLECT/PIVOT, clamp [0, 10]
    - Implement reconciliation arc detection: flag when tension drops below 3 after exceeding 7
    - Implement graceful degradation on DB unavailability
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [x] 6.2 Write property test for tension level clamping
    - **Property 7: Tension Level Clamping**
    - Test that for any sequence of moves and decay intervals, tension stays in [0, 10]
    - **Validates: Requirements 3.3**

  - [x] 6.3 Write property test for tension update correctness
    - **Property 8: Tension Update Correctness**
    - Test that ESCALATE/TAUNT → +1, CONCEDE/DEFLECT/PIVOT → -1, others unchanged, decay never negative
    - **Validates: Requirements 3.3**

  - [x] 6.4 Write property test for reconciliation arc detection
    - **Property 23: Reconciliation Arc Detection**
    - Test that tension dropping below 3 after exceeding 7 triggers reconciliation arc for next 5 interactions
    - **Validates: Requirements 3.5**

- [x] 7. Implement Scene_Context module
  - [x] 7.1 Implement scene_context.py with 3-beat window
    - Create `runtime/src/banter/scene_context.py`
    - Implement `SceneContext` class with deque-based beat storage (max 3)
    - Implement `add_beat()` with eviction and energy/has_the_room/landed_hit updates
    - Implement `get_context_for_generation()` that never blocks
    - Implement `classify_energy()`: heated (3+ beats >8 with ESCALATE/TAUNT), cooling (2+ beats <6), neutral otherwise
    - Implement "has the room" tracking with tie-breaking (most recent beat >8)
    - Implement "landed hit" counter (score >12, acknowledged by next 2 speakers)
    - Implement graceful degradation on state corruption (reset to empty)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x] 7.2 Write property test for scene context window bound
    - **Property 13: Scene Context Window Bound**
    - Test that scene context never contains more than 3 beats regardless of additions
    - **Validates: Requirements 5.1**

  - [x] 7.3 Write property test for landed hit acknowledgment counter
    - **Property 14: Landed Hit Acknowledgment Counter**
    - Test that landed hit instruction appears for exactly next 2 speakers then disappears, counter never negative
    - **Validates: Requirements 5.3**

  - [x] 7.4 Write property test for has-the-room assignment
    - **Property 15: Has-The-Room Assignment**
    - Test that assignment goes to elder with highest avg score across ≥2 beats, ties broken by most recent >8
    - **Validates: Requirements 5.5**

- [x] 8. Implement Model_Router module
  - [x] 8.1 Implement model_router.py with circuit-breaking dual routing
    - Create `runtime/src/banter/model_router.py`
    - Implement `ModelRouter` class extending existing circuit_breaker.py pattern
    - Implement `route()`: broadcast → remote (4s timeout, threshold 8), others → local (30s timeout)
    - Implement `call_remote()` with LangChain integration (Groq/Together endpoints)
    - Implement `validate_response()`: ≥1 non-whitespace, no control sequences, single line
    - Implement circuit breaker: 5-min window, 20% error threshold, min 5 requests
    - Implement `should_probe()` and `probe_remote()` for 60s cooldown recovery
    - Implement fallback to local with stricter threshold (10) on circuit break
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [x] 8.2 Write property test for circuit breaker activation conditions
    - **Property 16: Circuit Breaker Activation Conditions**
    - Test that circuit breaker activates iff ≥5 requests AND >20% error rate in 5-min window
    - **Validates: Requirements 6.6**

  - [x] 8.3 Write property test for response validation
    - **Property 17: Response Validation**
    - Test that validator accepts strings with ≥1 non-whitespace, no control sequences, no multi-turn markers; rejects all others
    - **Validates: Requirements 6.4**

- [x] 9. Implement Pacing_Controller module
  - [x] 9.1 Implement pacing_controller.py with priority-based delays
    - Create `runtime/src/banter/pacing_controller.py`
    - Implement `PacingController.compute_delay()` with priority rule resolution
    - Implement landed-hit rule (3.0-5.0s), heated-scene rule (1.5-2.5s), cooling-scene rule (5.0-8.0s), default rule (3.0-5.0s with adjustments)
    - Implement CONCEDE pre-delivery pause (+2.0s additive)
    - Implement final clamping to [1.0, 10.0]
    - Implement conflict resolution: longest delay wins
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

  - [x] 9.2 Write property test for pacing delay bounds
    - **Property 18: Pacing Delay Bounds**
    - Test that for any input combination, final delay is always in [1.0, 10.0]
    - **Validates: Requirements 7.6**

  - [x] 9.3 Write property test for pacing rule resolution
    - **Property 19: Pacing Rule Resolution**
    - Test that longest delay wins when multiple rules apply, and CONCEDE pause is always additive
    - **Validates: Requirements 7.2, 7.7**

- [x] 10. Checkpoint - Ensure all tests pass
  - Copy tests into container: `docker cp runtime/tests god-runtime:/app/tests`
  - Clear stale pycache: `docker exec god-runtime find /app -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null`
  - Run all banter tests: `docker exec -w /app god-runtime python -m pytest tests/banter/ -v --tb=short`
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Implement Anti-Repetition Gate module
  - [x] 11.1 Implement anti_repetition.py with trigram overlap and opener tracking
    - Create `runtime/src/banter/anti_repetition.py`
    - Implement `AntiRepetitionGate` class with per-elder history (last 20 lines), opener window (last 8), and register tracking
    - Implement `compute_trigram_overlap()`: ratio of shared 3-grams to total in shorter string
    - Implement `check()`: skip 3-gram if history <5, reject if overlap >0.60 or opener reused in last 8
    - Implement `record_delivery()` to update history, openers, and registers
    - Implement `should_shift_register()`: True if last 3 registers identical
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [x] 11.2 Write property test for trigram overlap rejection
    - **Property 20: Trigram Overlap Rejection**
    - Test that candidates with >60% 3-gram overlap to any history line (when history ≥5) are rejected; skip when history <5
    - **Validates: Requirements 8.1, 8.2, 8.6**

  - [x] 11.3 Write property test for opener uniqueness
    - **Property 21: Opener Uniqueness**
    - Test that candidates whose first 3 words match any opener in last 8 are rejected regardless of history size
    - **Validates: Requirements 8.3**

  - [x] 11.4 Write property test for anti-repetition fallback guarantee
    - **Property 22: Anti-Repetition Fallback Guarantee**
    - Test that after 3 consecutive rejections, system selects from Fallback_Pool on next cycle
    - **Validates: Requirements 8.5**

- [x] 12. Implement Pipeline Orchestrator (engine.py)
  - [x] 12.1 Implement engine.py wiring all components together
    - Create `runtime/src/banter/engine.py`
    - Implement `BanterEngine` class with dependency injection for all 8 components
    - Implement `generate_beat()` full pipeline: move selection → prompt building (scene context + relationship memory) → model routing → quality scoring → refinement loop → anti-repetition check → fallback after max rejections → pacing computation → BeatResult
    - Implement word-count acceptance rule on Quality_Judge error (4-30 words = accept, else fallback)
    - Implement session boundary detection (5-min gap → reset session state)
    - Implement relationship memory injection (last 5 significant interactions)
    - Wire "losing the room" signal from Scene_Context to Move_Selector
    - _Requirements: 1.3, 1.4, 1.5, 1.6, 3.2, 3.6, 5.2, 5.3, 8.4, 8.5_

  - [x] 12.2 Write property test for refinement pipeline guarantee
    - **Property 2: Refinement Pipeline Guarantee**
    - Test that sub-threshold lines get exactly max_refinement_rounds attempts before fallback, no infinite loops
    - **Validates: Requirements 1.3, 1.4**

  - [x] 12.3 Write property test for word-count acceptance on error
    - **Property 3: Word-Count Acceptance on Error**
    - Test that on Quality_Judge error, lines with 4-30 words are accepted, others go to fallback
    - **Validates: Requirements 1.5, 1.6**

- [x] 13. Integration wiring and archetype_graphs.py migration
  - [x] 13.1 Integrate BanterEngine into existing archetype_graphs.py
    - Replace `_banter_quality_score` calls with `Quality_Judge.evaluate()`
    - Replace `_pick_reactive_move` calls with `Move_Selector.compute_distribution().sample()`
    - Replace `_compose_reactive_banter` and `_banter_loop` with `BanterEngine.generate_beat()`
    - Wire BanterEngine initialization with existing db_pool, agent_runner, and circuit_breaker dependencies
    - Maintain backward-compatible function signatures where called externally
    - _Requirements: 1.1, 1.3, 2.1, 3.2, 4.1, 5.2, 6.1, 7.1, 8.1_

  - [x] 13.2 Write integration tests for full pipeline
    - Create `tests/banter/test_engine_integration.py`
    - Test end-to-end `generate_beat()` with mocked models produces valid BeatResult
    - Test fallback path when remote model is unavailable
    - Test session boundary detection and state reset
    - Test relationship memory injection with mocked DB
    - _Requirements: 1.3, 1.4, 2.1, 3.2, 6.2, 6.6_

- [x] 14. Final checkpoint - Ensure all tests pass
  - Copy tests into container: `docker cp runtime/tests god-runtime:/app/tests`
  - Clear stale pycache: `docker exec god-runtime find /app -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null`
  - Run all banter tests: `docker exec -w /app god-runtime python -m pytest tests/banter/ -v --tb=short`
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate the 23 universal correctness properties from the design
- Unit tests validate specific examples and edge cases
- The implementation uses Python throughout, with Hypothesis for property-based testing and pytest as the test runner
- LangChain is used for model integration (Ollama local, Groq/Together remote)
- PostgreSQL is accessed via the existing `db_pool.py` pattern

## Test Execution

All tests MUST run inside the `god-runtime` container via `docker exec`. The `runtime/tests/` directory is NOT volume-mounted, so tests must be copied in before each run.

**Standard test workflow:**
```bash
# 1. Copy tests into container (local tests/ dir is not volume-mounted)
docker cp runtime/tests god-runtime:/app/tests

# 2. Clear stale __pycache__ (host pyc has wrong path metadata)
docker exec god-runtime find /app -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null

# 3. Run tests
docker exec -w /app god-runtime python -m pytest tests/banter/ -v --tb=short
```

**Key constraints:**
- The container working dir is `/app`, source is at `/app/src/`
- `runtime/src` is volume-mounted at `/app/src` (changes reflect immediately)
- `runtime/agents` is volume-mounted at `/app/agents`
- `runtime/tests` is NOT mounted — must `docker cp` before each pytest run
- Imports inside tests use `from banter.<module> import ...` (conftest adds `/app/src` to sys.path)
- Imports inside source modules use relative imports: `from .types import ...`

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["2.1", "3.1", "4.1", "4.2"] },
    { "id": 2, "tasks": ["2.2", "2.3", "3.2", "3.3", "3.4", "3.5", "4.3", "4.4", "4.5"] },
    { "id": 3, "tasks": ["6.1", "7.1", "8.1", "9.1", "11.1"] },
    { "id": 4, "tasks": ["6.2", "6.3", "6.4", "7.2", "7.3", "7.4", "8.2", "8.3", "9.2", "9.3", "11.2", "11.3", "11.4"] },
    { "id": 5, "tasks": ["12.1"] },
    { "id": 6, "tasks": ["12.2", "12.3", "13.1"] },
    { "id": 7, "tasks": ["13.2"] }
  ]
}
```
