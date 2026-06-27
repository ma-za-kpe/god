# Implementation Plan: Banter Legendary Contract Alignment

## Overview

Force the banter engine runtime to obey the hard contract defined in the requirements. This involves replacing ad hoc prompt assembly with a structured PromptBlock pipeline, introducing a BeatMode enum with deterministic mode resolution, enriching PairState for CRACK/snap-back triggers, aligning the Quality Judge to 6 dimensions, adding HardBanChecker as final delivery gate, promoting backchannels and silence to first-class beat events, replacing scattered random calls with deterministic sliding-window rate controllers, and building a 100-beat theater harness with metrics and CI gating.

## Tasks

- [x] 1. Core data models and enums
  - [x] 1.1 Create BeatMode enum, BeatModePolicy dataclass, and PromptBlock dataclass
    - Create `runtime/src/banter/mode_types.py` with the `BeatMode` enum (NORMAL, CHAOS, CRACK, SNAP_BACK, BACKCHANNEL, SILENCE)
    - Create `BeatModePolicy` frozen dataclass with fields: mode, quality_threshold, refinement_allowed, anti_repetition_enabled, hard_bans_enabled, word_count_min, word_count_max, move_override, pacing_min_s, pacing_max_s
    - Create `PromptBlock` frozen dataclass with fields: marker, text, max_tokens
    - Define the policy table as constants: NORMAL_POLICY, CHAOS_POLICY, CRACK_POLICY, SNAP_BACK_POLICY, BACKCHANNEL_POLICY, SILENCE_POLICY matching the contract table
    - _Requirements: 5.1, 12.1, 12.2_

  - [x] 1.2 Enrich PairState with CRACK/snap-back fields
    - Add `recent_betrayal: bool`, `last_wound_summary: str`, `trust_delta: float`, `consecutive_escalations: int`, `consecutive_counters: int` to the production `PairState` dataclass in `runtime/src/banter/types.py`
    - Ensure existing code handles new fields with defaults (no breaking changes)
    - Update any factory or builder methods to include new fields
    - _Requirements: 8.2, 12.3_

  - [x] 1.3 Create ContractQualityScore dataclass and HardBan models
    - Create `ContractQualityScore` frozen dataclass with 6 dimensions: sharpness, emotional_texture, rhythm, pressure_relevance, voice_authenticity, subtext_depth
    - Add `total` property and `clip_candidate` property per contract spec
    - Create `HardBan` and `HardBanVerdict` frozen dataclasses
    - Remove `shareability` from scored dimensions; add `clip_candidate` as output flag only
    - _Requirements: 7.2, 7.5, 7.6, 10.1_

  - [x] 1.4 Create SlidingWindowController
    - Create `runtime/src/banter/rate_controllers.py` with `SlidingWindowController` class
    - Implement `allow(key)`, `record(key)`, `reset(key)` methods using deque-based sliding window
    - Replace pattern of `random.random() < X` for contract-critical features
    - Support configurable `max_count` and `window_size`
    - _Requirements: 12.4_

  - [x] 1.5 Write property test for BeatModePolicy contract table (Property 6)
    - **Property 6: BeatModePolicy matches contract table for all modes**
    - **Validates: Requirements 5.4, 5.5, 7.4, 12.2**

- [ ] 2. Sacred Prompt Builder
  - [x] 2.1 Implement SacredPromptBuilder with canonical marker order and token validation
    - Create `runtime/src/banter/prompt_builder.py` with `SacredPromptBuilder` class
    - Define `CANONICAL_ORDER` list of markers: [MODE], [ARCHETYPE], [ARC], [REACT], [EMOTIONAL], [CALLBACK], [SCENE], [MOVE], [BANNED], [RHYTHM]
    - Implement `build()` method that assembles PromptBlock objects in canonical order
    - Implement `validate_order()` that raises `PromptContractError` on marker reorder
    - Implement `validate_budgets()` that truncates blocks exceeding token ceilings
    - Enforce that no unmarked content is appended
    - Skip [ARCHETYPE] for CRACK mode; include [REACT] only when opponent has prior line
    - _Requirements: 1.1, 1.3, 12.1_

  - [x] 2.2 Wire SacredPromptBuilder into BanterEngine replacing ad hoc `_build_prompt()`
    - Refactor `runtime/src/banter/engine.py` to use SacredPromptBuilder
    - Remove all legacy ad hoc string assembly from `_build_prompt()`
    - Ensure the engine calls `build()` with policy and context arguments
    - Remove any strings matching the banned patterns from Section 1.2
    - _Requirements: 1.1, 1.2, 1.3_

  - [-] 2.3 Write property test for canonical marker order (Property 1)
    - **Property 1: Canonical marker order preserved**
    - **Validates: Requirements 1.1, 1.3, 12.1**

  - [-] 2.4 Write property test for no banned content in prompts (Property 2)
    - **Property 2: No banned content in assembled prompts**
    - **Validates: Requirements 1.2, 1.3, 1.5, 3.4**

  - [-] 2.5 Write property test for token budgets respected (Property 3)
    - **Property 3: Token budgets respected per block**
    - **Validates: Requirements 1.1, 1.4, 2.9**

- [ ] 3. Arc Pressure and Forced Response
  - [x] 3.1 Refactor ArcContextBuilder to never leak arc theme titles
    - Update `runtime/src/banter/arc_context.py` so `get_pressure(theme)` returns paraphrased pressure, never the raw title
    - Implement the fallback pressure format for unknown themes
    - Ensure the [ARC] block uses the injection format from Section 3.2
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 3.2 Implement forced response ([REACT] block) with pair-filtered context
    - Add [REACT] block assembly to SacredPromptBuilder, conditional on opponent having a prior line
    - Implement pair-filtered context extraction (last 4 relevant thread entries)
    - Use the injection format from Section 4.3
    - Ensure "Recent exchange:" string is never used
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [~] 3.3 Write property test for arc pressure never contains theme title (Property 4)
    - **Property 4: Arc pressure never contains theme title**
    - **Validates: Requirements 3.1, 3.4**

  - [~] 3.4 Write property test for REACT block biconditional (Property 5)
    - **Property 5: REACT block biconditional on opponent prior line**
    - **Validates: Requirements 4.4**

- [~] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Mode Resolution
  - [x] 5.1 Implement ModeResolver with strict precedence chain
    - Create `runtime/src/banter/mode_resolver.py` with `ModeResolver` class
    - Implement `resolve()` with precedence: SILENCE → BACKCHANNEL → SNAP_BACK → CRACK → CHAOS → NORMAL
    - Wire in SilenceController, BackchannelController, and CRACKRateController dependencies
    - Ensure mode is resolved before prompt construction in the engine
    - _Requirements: 5.2, 12.2_

  - [x] 5.2 Implement SilenceController as first-class beat producer
    - Create `runtime/src/banter/silence_controller.py` with `SilenceController` class
    - Produce `BeatResult` with `line_type="silence"`, no quality score, 3-5 second pacing
    - Trigger on landed hit aftermath or falling tension
    - _Requirements: 5.2, 12.8_

  - [x] 5.3 Upgrade BackchannelController to produce first-class BeatResult
    - Refactor `runtime/src/banter/backchannel.py` to produce `BeatResult` with `line_type="backchannel"`
    - Enforce 2-6 word output, short delay policy
    - Apply hard bans but skip normal quality scoring and refinement
    - _Requirements: 5.2, 12.7_

  - [x] 5.4 Implement CRACK trigger from production PairState
    - Add `_should_crack()` method to ModeResolver checking: `recent_betrayal AND tension_level > 8 AND consecutive_counters >= 3 AND rate_controller.allow()`
    - Use SlidingWindowController with max_count=1, window_size=30 per pair
    - Ensure CRACK never fires without all production conditions met
    - _Requirements: 8.2, 8.3, 12.3_

  - [x] 5.5 Implement snap-back and chaos mode logic
    - SNAP_BACK fires when same Elder's previous beat was CRACK (unless higher-priority mode intervenes)
    - CHAOS fires for exactly one beat when `tension >= 8 or consecutive_escalations >= 4`
    - Chaos uses move override ESCALATE(75%)/TAUNT(25%) via deterministic rate controller
    - _Requirements: 5.3, 5.4, 5.5, 8.4_

  - [x] 5.6 Wire ModeResolver into BanterEngine main loop
    - Ensure `generate_beat()` calls `mode_resolver.resolve()` before prompt construction
    - Route SILENCE and BACKCHANNEL modes to skip model generation
    - Pass `BeatModePolicy` to SacredPromptBuilder, QualityJudgeV2, and HardBanChecker
    - _Requirements: 5.2, 12.2_

  - [~] 5.7 Write property test for chaos lasts exactly one beat (Property 7)
    - **Property 7: Chaos lasts exactly one beat**
    - **Validates: Requirements 5.3, 5.5**

  - [~] 5.8 Write property test for VeilLayer deterministic scheduling (Property 8)
    - **Property 8: VeilLayer deterministic scheduling with no consecutive beats**
    - **Validates: Requirements 6.2, 6.4, 12.4**

  - [~] 5.9 Write property test for CRACK fires only when all conditions met (Property 10)
    - **Property 10: CRACK fires only when all production trigger conditions are met**
    - **Validates: Requirements 8.2, 8.3, 8.5**

  - [~] 5.10 Write property test for CRACK rate limiting (Property 15)
    - **Property 15: CRACK rate limited to max 1 per 30 eligible beats per pair**
    - **Validates: Requirements 8.2, 12.4**

- [ ] 6. Quality Judge V2
  - [x] 6.1 Refactor QualityJudge to score 6 dimensions with emotional texture hard block
    - Refactor `runtime/src/banter/quality_judge.py` to `QualityJudgeV2`
    - Score on: sharpness, emotional_texture, rhythm, pressure_relevance, voice_authenticity, subtext_depth
    - Remove `shareability` as scored dimension; replace with `clip_candidate` output flag
    - Rename `thematic_relevance` → `pressure_relevance`
    - Enforce emotional_texture == 0 hard block for NORMAL mode (reject regardless of total)
    - Apply mode-specific thresholds from the policy table
    - Return `ContractQualityScore` dataclass
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [~] 6.2 Write property test for emotional texture hard block (Property 9)
    - **Property 9: Emotional texture hard block in NORMAL mode**
    - **Validates: Requirements 7.3**

  - [~] 6.3 Write property test for arc title leak scoring (Property 16)
    - **Property 16: Arc title leak scores 0 on pressure_relevance and fails hard ban**
    - **Validates: Requirements 3.4, 7.6**

- [~] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Hard Bans and Repetition
  - [x] 8.1 Implement HardBanChecker as final delivery gate
    - Create `runtime/src/banter/hard_bans.py` with `HardBanChecker` class
    - Implement all 7 hard bans: no_sentence_boundaries, discord_register, generic_debater, arc_theme_title_leak, subjectless_opening, too_long, too_short
    - Apply archetype exceptions (shadow/trickster exempt from subjectless_opening; backchannel exempt from too_short)
    - Position as final gate before delivery for all modes except SILENCE
    - Return `HardBanVerdict` with pass/fail and violation details
    - _Requirements: 10.1, 10.2, 10.3_

  - [x] 8.2 Implement WorldRepetitionBuffer as shared singleton
    - Update `runtime/src/banter/anti_repetition.py` with `WorldRepetitionBuffer` class
    - Use module-level singleton shared across all BanterEngine instances
    - Implement trigram overlap calculation with 0.60 threshold against last 20 delivered lines
    - Reject exact duplicates unconditionally
    - _Requirements: 9.1, 9.2, 9.3_

  - [x] 8.3 Wire HardBanChecker and WorldRepetitionBuffer into BanterEngine pipeline
    - Insert HardBanChecker after QualityJudge, before delivery
    - Insert WorldRepetitionBuffer check before HardBanChecker
    - Ensure fallback lines also pass both gates
    - After max_rejection_rounds (3), fall through to fallback pool
    - Ultimate fallback: emit silence beat if fallback also violates
    - _Requirements: 10.2, 10.3, 12.9_

  - [~] 8.4 Write property test for world repetition buffer (Property 11)
    - **Property 11: World repetition buffer rejects overlapping lines**
    - **Validates: Requirements 9.1, 9.2, 9.3**

  - [~] 8.5 Write property test for hard ban enforcement (Property 12)
    - **Property 12: Hard ban checker rejects all banned content**
    - **Validates: Requirements 10.1, 10.2, 10.3**

  - [~] 8.6 Write property test for backchannel ban exemptions (Property 13)
    - **Property 13: Backchannel exemptions from length bans**
    - **Validates: Requirements 10.1, 10.3, 12.7**

  - [~] 8.7 Write property test for fallback lines pass delivery gate (Property 14)
    - **Property 14: Fallback lines pass full delivery gate**
    - **Validates: Requirements 10.3, 12.9**

- [ ] 9. VeilLayer and Archetype Prompts
  - [x] 9.1 Refactor VeilLayer to use deterministic sliding-window scheduling
    - Update `runtime/src/banter/veil_layer.py` to fire every 8th eligible beat
    - Fire on Twitch/audience event beats
    - Suppress for CONCEDE at tension < 4
    - Replace any `random.random() < X` with SlidingWindowController
    - Ensure no two VeilLayer beats consecutive unless caused by separate audience events
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 12.4_

  - [x] 9.2 Tighten all eight archetype prompts under 220 tokens
    - Update `runtime/src/banter/voice_profiles/` JSON files for all 8 archetypes
    - Ensure each prompt includes: identity, core beliefs, core fear, method, under-pressure behavior, anti-pattern
    - Apply canonical alias mapping (martyr→Vow, shadow→Noct)
    - Deprecate legacy aliases (Merch, Shade variant)
    - Ensure no two archetypes share the same display alias
    - Verify `VoiceDNA.get_prompt_injection()` returns only the system prompt
    - _Requirements: 2.1-2.9_

- [~] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Theater Harness and Metrics
  - [x] 11.1 Build 100-beat theater harness
    - Create `runtime/src/banter/theater_harness.py` with `TheaterHarness` class
    - Accept: fixed seed, archetype roster, arc theme, starting pair states, optional model stub
    - Output: transcript list, metrics JSON, prompt snapshots, delivered line events
    - Implement `HarnessResult` and `SessionMetrics` dataclasses
    - Support deterministic model stub for CI and optional live model for manual review
    - _Requirements: 0.1, 11.1, 11.4, 12.5_

  - [x] 11.2 Implement SessionMetrics calculation with V1 minimum assertions
    - Calculate all Section 11 metrics: direct_response_rate, arc_title_leaks, hard_ban_violations, cross_elder_duplicates, grammar_failures, emotional_texture_coverage, clip_candidate_rate, crack_count, veil_beats, backchannel_rate, voice_similarity_max
    - Implement direct response detector with n-gram overlap + heuristic markers
    - Assert V1 minimums in test assertions
    - _Requirements: 11.1, 11.2, 11.3_

  - [~] 11.3 Create theater contract integration test
    - Create `runtime/tests/banter/test_theater_contract.py`
    - Run 100-beat session with deterministic model stub
    - Assert all V1 minimum metrics pass
    - Verify prompt snapshots show Section 1 marker order
    - Verify 0 cross-Elder duplicate deliveries
    - Verify CRACK fires at least once in high-tension scenarios
    - _Requirements: 0.1, 11.1, 11.4, 12.5_

  - [~] 11.4 Create 5 golden transcript fixtures
    - Create `runtime/tests/banter/golden_transcripts/` directory
    - Generate 5 fixed-seed sessions: scarcity_medium, betrayal_high_crack, reconciliation_low, cross_pair_eavesdrop, audience_veil_heavy
    - Store as markdown reference transcripts for CI drift detection
    - _Requirements: 0.1, 12.6_

- [ ] 12. Final integration and wiring
  - [~] 12.1 Wire full pipeline end-to-end: generate_beat() → BeatResult
    - Ensure `generate_beat()` follows: ModeResolver → PromptBuilder → Generation → QualityJudge → Refinement → AntiRepetition → WorldRepetition → HardBanChecker → PacingController → BeatResult
    - Verify all BeatResult metadata includes: line_type, mode, clip_candidate flag, quality score
    - Ensure backchannels and silence produce proper BeatResult events
    - Test that fallback path obeys same delivery contract
    - _Requirements: 12.1-12.9_

  - [~] 12.2 Add prompt snapshot tests for exact marker order
    - Create `runtime/tests/banter/test_prompt_snapshots.py`
    - Snapshot tests assert exact marker order for multiple scenarios
    - Assert removed legacy text (Section 1.2) does not appear
    - Test across all 8 archetypes and multiple arc themes
    - _Requirements: 0.1, 1.3_

  - [~] 12.3 Ensure test truthfulness - use production dataclasses, not mocks
    - Audit existing tests for `MagicMock` patterns on PairState and replace with real dataclass instances
    - Ensure all new tests use production `PairState` with real field values
    - Verify that if a test condition cannot be expressed with production state, the feature is flagged as unimplemented
    - _Requirements: 12.10_

- [~] 13. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design's Correctness Properties section
- Unit tests validate specific examples and edge cases
- The implementation language is Python (matching existing codebase and design document)
- All modules live under `runtime/src/banter/` and tests under `runtime/tests/banter/`
- The theater harness is the ultimate acceptance gate, not unit tests alone
- Existing modules (engine.py, quality_judge.py, backchannel.py, veil_layer.py, anti_repetition.py) are refactored rather than replaced from scratch

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3", "1.4"] },
    { "id": 1, "tasks": ["1.5", "2.1", "3.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4", "2.5", "3.2"] },
    { "id": 3, "tasks": ["3.3", "3.4", "5.1", "5.2", "5.3"] },
    { "id": 4, "tasks": ["5.4", "5.5", "6.1"] },
    { "id": 5, "tasks": ["5.6", "5.7", "5.8", "5.9", "5.10", "6.2", "6.3"] },
    { "id": 6, "tasks": ["8.1", "8.2"] },
    { "id": 7, "tasks": ["8.3", "8.4", "8.5", "8.6", "8.7"] },
    { "id": 8, "tasks": ["9.1", "9.2"] },
    { "id": 9, "tasks": ["11.1", "11.2"] },
    { "id": 10, "tasks": ["11.3", "11.4"] },
    { "id": 11, "tasks": ["12.1", "12.2", "12.3"] }
  ]
}
```
