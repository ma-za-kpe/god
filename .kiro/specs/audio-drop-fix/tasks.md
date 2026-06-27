# Implementation Plan

## Overview

This task list follows the exploratory bugfix workflow to fix audio dropping intermittently during live broadcast. The voice pipeline (`runtime/src/voice/engine.py`) has five failure modes that silently suppress voice plan production. We explore the bug first with tests, then implement the fix, then validate.

## Tasks

- [x] 1. Write bug condition exploration test
  - [x] 1.1 Write and run bug condition exploration property test
    - **Property 1: Bug Condition** - Voice Plan Production Under Failure Modes
    - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
    - **DO NOT attempt to fix the test or the code when it fails**
    - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
    - **GOAL**: Surface counterexamples that demonstrate the five failure modes cause audio drops
    - **Scoped PBT Approach**: Scope the property to concrete failing cases for each failure mode:
      - Synchronous blocking: Mock `probe_url()` with 1200ms latency, assert `compose()` completes within 200ms
      - Swallowed exception: Inject `KeyError` in `build_voice_state()`, assert WARNING-level log is emitted
      - Abrupt fallback: Set dialogue age=25s with empty showrunner headline, assert output is NOT the static string "The world keeps moving."
      - No retry: Mock `probe_url()` to fail once then succeed, assert `health.ok=True` after retry
      - Silent dry-run: Unset `VOICE_DRY_RUN`, instantiate `VoiceSurface`, assert WARNING log about dry-run mode
    - Test assertions match Expected Behavior Properties from design:
      - `result.plan IS NOT NULL`
      - `compose_duration <= 200ms`
      - `warning_or_error_logged(input) = true`
      - `result.health.ok = true OR result.health.degraded = true`
    - Run test on UNFIXED code
    - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
    - Document counterexamples found
    - Mark task complete when test is written, run, and failure is documented
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - [x] 2.1 Write and run preservation property tests on unfixed code
    - **Property 2: Preservation** - Normal Voice Pipeline Behavior Unchanged
    - **IMPORTANT**: Follow observation-first methodology
    - Observe behavior on UNFIXED code for non-buggy inputs (all cases where isBugCondition returns false)
    - Write property-based tests capturing observed behavior patterns from Preservation Requirements:
      - For all snapshots with healthy TTS endpoint: `compose()` produces same VoiceState as original
      - For all valid snapshots: `build_voice_state()` returns same payload as original
      - For all fresh dialogue turns: speaker/line/emotion selection is identical to original
      - For all explicit dry-run=false configs: TTS output behavior is identical
      - For all dialogue lines: text stripping (UUIDs, emojis, prefixes) produces identical results
    - Run tests on UNFIXED code
    - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
    - Mark task complete when tests are written, run, and passing on unfixed code
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 3. Fix for audio dropping intermittently during live broadcast
  - [x] 3.1 Implement async/cached health probes
    - Add `_CachedHealthProbe` class with TTL-based caching (~5s) to `runtime/src/voice/engine.py`
    - Replace inline `probe_url()` call in `VoiceSurface.compose()` with `self._cached_health.get()`
    - Ensure `compose()` never blocks on network I/O (max 200ms wall-clock)
    - _Requirements: 1.1, 2.1, 3.1_

  - [x] 3.2 Implement exception handling in build_voice_state
    - Wrap `VoiceSurface().compose(snapshot)` call in try/except block
    - Log at `logging.WARNING` with structured context: exception type, message, relevant snapshot keys, timestamp
    - Return a degraded VoiceState rather than propagating the exception silently
    - _Requirements: 1.2, 2.2, 3.2_

  - [x] 3.3 Implement graceful fallback content
    - Add `_last_plan` instance variable to `VoiceSurface` to stash the last successful voice plan
    - When dialogue age exceeds threshold and no showrunner headline exists, reuse `_last_plan` if available
    - If no previous plan exists, use the static string but log at INFO level
    - Remove abrupt content switch to "The world keeps moving." as sole fallback path
    - _Requirements: 1.3, 2.3, 3.3_

  - [x] 3.4 Implement health probe retry with backoff
    - Create `_probe_with_retry(url, timeout, max_retries=1)` helper function
    - On first probe failure, wait ~500ms and retry once before marking unhealthy
    - Implement auto-recovery: set `health.ok=True` immediately when endpoint responds successfully
    - _Requirements: 1.4, 2.4, 3.1_

  - [x] 3.5 Implement dry-run warning at startup
    - In `VoiceSurface.__init__()`, check if `os.getenv("VOICE_DRY_RUN")` is None
    - If None and dry_run resolves to True, log WARNING: "VOICE_DRY_RUN is not set; defaulting to dry-run mode (no TTS output)"
    - If explicitly set to "true", log at DEBUG level only (intentional configuration)
    - _Requirements: 1.5, 2.5, 3.4_

  - [x] 3.6 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Voice Plan Production Under Failure Modes
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms all five failure modes are fixed)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 3.7 Verify preservation tests still pass
    - **Property 2: Preservation** - Normal Voice Pipeline Behavior Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 4. Checkpoint - Ensure all tests pass
  - [x] 4.1 Run full test suite and verify
    - Run the full test suite for `runtime/src/voice/engine.py`
    - Verify Property 1 (Bug Condition) exploration test passes on fixed code
    - Verify Property 2 (Preservation) property tests pass on fixed code
    - Verify no other existing tests have been broken
    - Ensure all tests pass, ask the user if questions arise
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4, 3.5_

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1"] },
    { "id": 1, "tasks": ["3.1", "3.2", "3.3", "3.4", "3.5"] },
    { "id": 2, "tasks": ["3.6", "3.7"] },
    { "id": 3, "tasks": ["4.1"] }
  ]
}
```

## Notes

- Tasks 1 and 2 are independent and can be done in parallel, but both must be completed BEFORE implementation (task 3)
- The exploration test (task 1) is expected to FAIL on unfixed code — this confirms the bug exists
- The preservation tests (task 2) are expected to PASS on unfixed code — this captures baseline behavior
- After implementation, re-running both test suites validates the fix (task 3.6) and ensures no regressions (task 3.7)
- The five implementation sub-tasks (3.1–3.5) can be done in any order but all must be complete before verification
