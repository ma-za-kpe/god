# Implementation Plan: Elder Voice Soul Engine

## Overview

Add four soul engine modules (Voice_DNA, Emotional_Primer, Callback_Registry, Subtlety_Director) to the existing `runtime/src/banter/` pipeline, plus enhanced Quality_Judge scoring with two new dimensions. Each module integrates via dependency injection into the prompt-building phase with fault isolation, matching the existing architecture patterns.

## Tasks

- [x] 1. Define shared types and configuration
  - [x] 1.1 Create soul engine types module
    - Create `runtime/src/banter/soul_types.py` with all dataclasses: `VoiceDNAProfile`, `RhythmPattern`, `CallbackSurface`, `SoreSpot`, `SubtextInstruction`, `MemorableMoment`, `CallbackUsageTracker`, `WriteBuffer`
    - Include schema validation constants (`VOICE_DNA_SCHEMA`) and `validate_voice_dna_profile()` function
    - _Requirements: 1.1, 1.4, 4.4, 8.4_

  - [x] 1.2 Create soul engine configuration
    - Add `SoulEngineConfig` frozen dataclass to `runtime/src/banter/soul_types.py` with all feature flags and token budget fields
    - Ensure defaults: `enabled=True`, individual module flags, `max_total_tokens=800`, individual budgets (250, 200, 200, 150)
    - _Requirements: 7.2, 7.5_

  - [x] 1.3 Write property test for VoiceDNA schema validation
    - **Property 1: VoiceDNA Schema Validation**
    - **Validates: Requirements 1.1, 8.4**
    - Test in `runtime/tests/banter/test_soul_engine_properties.py`

  - [x] 1.4 Write property test for VoiceDNA serialization round-trip
    - **Property 15: VoiceDNA Serialization Round-Trip**
    - **Validates: Requirements 8.6**
    - Test in `runtime/tests/banter/test_soul_engine_properties.py`

- [ ] 2. Implement Voice_DNA module
  - [x] 2.1 Create Voice_DNA module with profile loading and injection
    - Create `runtime/src/banter/voice_dna.py` with `VoiceDNA` class
    - Implement `load_profiles()`: load and validate all 8 JSON profiles from `runtime/src/banter/voice_profiles/`
    - Implement `get_prompt_injection(archetype)`: return structured linguistic instructions within 250-token budget
    - Implement `check_for_reload()`: 30-second polling for file changes, retain previous valid profile on validation failure
    - _Requirements: 1.1, 1.2, 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 2.2 Implement voice conformance scoring
    - Add `score_voice_conformance(candidate, archetype)` method returning 0–3 integer
    - Score based on structural pattern matching: sentence structures, verbal tics, rhythm patterns, micro-phrases
    - _Requirements: 1.3, 10.1_

  - [x] 2.3 Create VoiceDNA profile JSON files for all 8 archetypes
    - Create `runtime/src/banter/voice_profiles/` directory
    - Create `{archetype}.json` for each: parasite, prophet, trickster, sovereign, martyr, shadow, herald, keeper
    - Each profile must contain all 7 required fields with minimum counts and archetype-specific content per Requirement 2
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 8.1_

  - [x] 2.4 Write property test for voice conformance score bounds
    - **Property 2: Voice Conformance Score Bounds**
    - **Validates: Requirements 1.3**
    - Test in `runtime/tests/banter/test_soul_engine_properties.py`

  - [x] 2.5 Write property test for archetype linguistic differentiation
    - **Property 3: Archetype Linguistic Differentiation**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8**
    - Test in `runtime/tests/banter/test_soul_engine_properties.py`

  - [x] 2.6 Write property test for failed validation profile retention
    - **Property 23: Failed Validation Profile Retention**
    - **Validates: Requirements 8.5**
    - Test in `runtime/tests/banter/test_soul_engine_properties.py`

  - [x] 2.7 Write unit tests for Voice_DNA module
    - Create `runtime/tests/banter/test_voice_dna.py`
    - Test profile loading, injection output, hot-reload behavior, fallback on invalid profiles
    - _Requirements: 1.1, 1.2, 1.6, 8.3, 8.5_

- [ ] 3. Checkpoint - Verify Voice_DNA module
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement Emotional_Primer module
  - [x] 4.1 Create Emotional_Primer module
    - Create `runtime/src/banter/emotional_primer.py` with `EmotionalPrimer` class
    - Implement `generate_emotional_context()` that transforms InteractionRecord history into present-tense emotional framing
    - Apply archetype-specific emotion mappings for each of the 8 archetypes
    - Implement tension-aware language selection: visceral (>5) vs observational (≤5)
    - Implement reconciliation mixed-feeling framing
    - Implement neutral curiosity fallback for no-history pairs
    - Enforce output bounds: ≤3 sentences per event, ≤15 sentences total, ≤200 tokens
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [x] 4.2 Write property test for present-tense invariant
    - **Property 4: Emotional_Primer Present-Tense Invariant**
    - **Validates: Requirements 3.1**
    - Test in `runtime/tests/banter/test_soul_engine_properties.py`

  - [x] 4.3 Write property test for output size bounds
    - **Property 5: Emotional_Primer Output Size Bounds**
    - **Validates: Requirements 3.5**
    - Test in `runtime/tests/banter/test_soul_engine_properties.py`

  - [x] 4.4 Write property test for archetype-specific output
    - **Property 6: Emotional_Primer Archetype-Specific Output**
    - **Validates: Requirements 3.2**
    - Test in `runtime/tests/banter/test_soul_engine_properties.py`

  - [x] 4.5 Write unit tests for Emotional_Primer module
    - Create `runtime/tests/banter/test_emotional_primer.py`
    - Test high-tension visceral markers, low-tension observational markers, reconciliation language, no-history fallback
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [ ] 5. Implement Callback_Registry module
  - [x] 5.1 Create database migration for callback tables
    - Create SQL migration adding `callback_moments`, `callback_running_gags`, `callback_sore_spots` tables
    - Use same schema/pool as Relationship_Memory
    - _Requirements: 9.1_

  - [x] 5.2 Implement Callback_Registry storage and tracking
    - Create `runtime/src/banter/callback_registry.py` with `CallbackRegistry` class
    - Implement `store_memorable_moment()`: store lines scoring >12, enforce 50-entry cap per pair with oldest eviction
    - Implement `compute_pair_id()`: identical to `RelationshipMemory._compute_pair_id`
    - Implement running gag detection: flag after 3+ high-scoring interactions on same topic
    - Implement sore spot tracking: topics with tension increase ≥2
    - Implement `WriteBuffer` for DB unavailability (max 20 entries)
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [x] 5.3 Implement callback surfacing logic
    - Implement `surface_callback()`: match callbacks to current dramatic conditions (tension within 2, theme overlap, emotional register)
    - Enforce 15-beat minimum gap between same callback uses
    - Enforce 2 callbacks per pair per session limit
    - Return `None` when no suitable callback exists (tension mismatch >3, no theme overlap)
    - Implement `get_sore_spots()` for Subtlety_Director integration
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.6_

  - [x] 5.4 Write property test for callback registry capacity invariant
    - **Property 7: Callback Registry Capacity Invariant**
    - **Validates: Requirements 4.5, 9.5**
    - Test in `runtime/tests/banter/test_soul_engine_properties.py`

  - [x] 5.5 Write property test for callback timing constraints
    - **Property 8: Callback Timing Constraints**
    - **Validates: Requirements 5.3**
    - Test in `runtime/tests/banter/test_soul_engine_properties.py`

  - [x] 5.6 Write property test for callback surfacing match quality
    - **Property 9: Callback Surfacing Match Quality**
    - **Validates: Requirements 5.1, 5.6**
    - Test in `runtime/tests/banter/test_soul_engine_properties.py`

  - [x] 5.7 Write property test for pair ID computation equivalence
    - **Property 16: Pair ID Computation Equivalence**
    - **Validates: Requirements 9.4**
    - Test in `runtime/tests/banter/test_soul_engine_properties.py`

  - [x] 5.8 Write property test for write buffer capacity
    - **Property 17: Write Buffer Capacity**
    - **Validates: Requirements 9.6**
    - Test in `runtime/tests/banter/test_soul_engine_properties.py`

  - [x] 5.9 Write unit tests for Callback_Registry
    - Create `runtime/tests/banter/test_callback_registry.py`
    - Test storage, eviction, surfacing logic, timing enforcement, DB unavailability buffering
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 4.6, 5.1, 5.3, 5.6, 9.5, 9.6_

- [ ] 6. Checkpoint - Verify Callback_Registry module
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Implement Subtlety_Director module
  - [x] 7.1 Create Subtlety_Director module
    - Create `runtime/src/banter/subtlety_director.py` with `SubtletyDirector` class
    - Implement `should_inject_subtext()`: activation logic (tension 4–8, DEFLECT/QUESTION moves, matching sore spot) with overrides (tension <2, no history, CONCEDE)
    - Implement 20% rate reduction at tension >8
    - Implement `generate_subtext_instruction()`: build SubtextInstruction with surface/implied meaning and technique
    - Enforce technique variety: same technique ≤2 in 5 consecutive uses per Elder
    - Implement `score_subtext_depth()` returning 0–3 integer for Quality_Judge
    - Token budget: ≤150 tokens output
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x] 7.2 Write property test for subtlety activation logic
    - **Property 10: Subtlety Director Activation Logic**
    - **Validates: Requirements 6.2, 6.6**
    - Test in `runtime/tests/banter/test_soul_engine_properties.py`

  - [x] 7.3 Write property test for high-tension rate reduction
    - **Property 11: Subtlety High-Tension Rate Reduction**
    - **Validates: Requirements 6.3**
    - Test in `runtime/tests/banter/test_soul_engine_properties.py`

  - [x] 7.4 Write property test for technique variety constraint
    - **Property 12: Technique Variety Constraint**
    - **Validates: Requirements 6.5**
    - Test in `runtime/tests/banter/test_soul_engine_properties.py`

  - [x] 7.5 Write unit tests for Subtlety_Director
    - Create `runtime/tests/banter/test_subtlety_director.py`
    - Test activation/deactivation conditions, technique variety, scoring, edge cases
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [ ] 8. Checkpoint - Verify Subtlety_Director module
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Enhance Quality_Judge with soul dimensions
  - [x] 9.1 Extend Quality_Judge with soul engine scoring
    - Modify `runtime/src/banter/quality_judge.py` to add `EnhancedQualityScore` dataclass with `voice_authenticity` and `subtext_depth` dimensions
    - Integrate `VoiceDNA.score_voice_conformance()` for voice_authenticity scoring
    - Integrate `SubtletyDirector.score_subtext_depth()` for subtext scoring (only when subtext was injected)
    - Add subtext_depth to shareability as bonus (capped at 3)
    - Raise thresholds to 10/12 when soul engine active; keep 8/10 when disabled
    - Include VoiceDNA violations in refinement feedback
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [x] 9.2 Write property test for quality judge dimension count
    - **Property 18: Quality_Judge Dimension Count**
    - **Validates: Requirements 10.1, 10.2**
    - Test in `runtime/tests/banter/test_soul_engine_properties.py`

  - [x] 9.3 Write property test for subtext depth conditional scoring
    - **Property 19: Subtext Depth Conditional Scoring**
    - **Validates: Requirements 10.3, 10.5**
    - Test in `runtime/tests/banter/test_soul_engine_properties.py`

  - [x] 9.4 Write property test for quality threshold configuration
    - **Property 20: Quality Threshold Configuration**
    - **Validates: Requirements 10.4**
    - Test in `runtime/tests/banter/test_soul_engine_properties.py`

  - [x] 9.5 Write property test for shareability bonus conditional
    - **Property 22: Shareability Bonus Conditional**
    - **Validates: Requirements 5.5**
    - Test in `runtime/tests/banter/test_soul_engine_properties.py`

  - [x] 9.6 Write unit tests for enhanced Quality_Judge
    - Create `runtime/tests/banter/test_quality_judge_enhanced.py`
    - Test dimension scoring, thresholds, disabled behavior, refinement feedback
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

- [x] 10. Integrate soul engine into BanterEngine
  - [x] 10.1 Extend BanterEngine with soul module injection
    - Modify `runtime/src/banter/engine.py` to accept four optional soul module parameters and `SoulEngineConfig`
    - Extend `_build_prompt()` to compose soul modules in defined order: Voice_DNA → Emotional_Primer → Callback_Registry → Subtlety_Director → existing components
    - Wrap each module call in try/except with DEBUG logging; continue on failure
    - Enforce 800-token combined cap across all soul module outputs
    - Add `asyncio.wait_for` with 200ms total budget for soul prompt-building phase
    - Record module success/failure in `BeatResult.metadata`
    - Skip all soul modules when `SoulEngineConfig.enabled = False`
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 1.6, 3.7, 4.6_

  - [x] 10.2 Write property test for soul engine token budget
    - **Property 13: Soul Engine Token Budget**
    - **Validates: Requirements 7.2**
    - Test in `runtime/tests/banter/test_soul_engine_properties.py`

  - [x] 10.3 Write property test for module fault isolation
    - **Property 14: Module Fault Isolation**
    - **Validates: Requirements 1.6, 3.7, 4.6, 7.3**
    - Test in `runtime/tests/banter/test_soul_engine_properties.py`

  - [x] 10.4 Write property test for prompt composition order
    - **Property 21: Prompt Composition Order**
    - **Validates: Requirements 7.1**
    - Test in `runtime/tests/banter/test_soul_engine_properties.py`

  - [x] 10.5 Write integration tests for soul engine pipeline
    - Create `runtime/tests/banter/test_soul_engine_integration.py`
    - Test full `generate_beat()` with all soul modules active
    - Test `generate_beat()` with individual modules failing
    - Test disabled soul engine produces identical output to pre-soul-engine behavior
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 11. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (23 total)
- Unit tests validate specific examples and edge cases
- The existing banter pipeline tests in `runtime/tests/banter/` must continue passing throughout implementation
- All new modules follow the dependency injection pattern already used by QualityJudge, ModelRouter, and RelationshipMemory
- Python with async/await, dataclasses, and type hints matches the existing codebase style

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "1.4", "2.1", "2.3"] },
    { "id": 2, "tasks": ["2.2", "2.4", "2.5", "2.6", "2.7", "4.1"] },
    { "id": 3, "tasks": ["4.2", "4.3", "4.4", "4.5", "5.1"] },
    { "id": 4, "tasks": ["5.2", "7.1"] },
    { "id": 5, "tasks": ["5.3", "5.4", "5.7", "5.8", "7.2", "7.3", "7.4"] },
    { "id": 6, "tasks": ["5.5", "5.6", "5.9", "7.5"] },
    { "id": 7, "tasks": ["9.1"] },
    { "id": 8, "tasks": ["9.2", "9.3", "9.4", "9.5", "9.6"] },
    { "id": 9, "tasks": ["10.1"] },
    { "id": 10, "tasks": ["10.2", "10.3", "10.4", "10.5"] }
  ]
}
```
