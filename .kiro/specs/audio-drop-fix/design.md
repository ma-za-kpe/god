# Audio Drop Fix — Bugfix Design

## Overview

Audio drops intermittently during live broadcast because multiple failure modes in the voice pipeline (`runtime/src/voice/engine.py`) silently suppress voice plan production. The fix targets five distinct code paths: synchronous health probes blocking composition, swallowed exceptions in `build_voice_state`, abrupt fallback content switching, no retry on probe failure, and silent dry-run defaulting. The strategy is to make each failure mode observable, recoverable, or non-blocking while preserving all existing behavior for the normal (non-buggy) path.

## Glossary

- **Bug_Condition (C)**: Any of the five failure modes that cause the voice pipeline to drop audio — synchronous probe blocking, swallowed exceptions, abrupt fallback, no probe retry, or silent dry-run default
- **Property (P)**: The desired behavior when a bug condition is triggered — voice plan production remains unblocked, errors are logged at WARNING+, and TTS output is never silently disabled
- **Preservation**: All existing voice pipeline behavior that must remain unchanged — normal health probe results, successful `build_voice_state` execution, fresh dialogue content selection, explicit dry-run=false operation, and text stripping
- **VoiceSurface**: The class in `runtime/src/voice/engine.py` that composes a `VoicePlan` from the world snapshot
- **VoicePlan**: The data structure describing speaker, line, emotion, and TTS parameters sent to Kokoro
- **VoiceState**: The composite state including plan, health, and configuration returned by `compose()`
- **probe_url()**: The synchronous health check function imported from `health_checks` module
- **build_voice_state()**: The module-level function that instantiates `VoiceSurface` and calls `compose()`
- **VOICE_DRY_RUN**: Environment variable controlling whether TTS output is actually rendered (defaults to `"true"`)

## Bug Details

### Bug Condition

The bug manifests when any of five failure modes is active in the voice pipeline. The `VoiceSurface.compose()` method and its supporting functions either block on synchronous I/O, swallow exceptions, fall back to static content abruptly, fail to retry health probes, or silently disable output via dry-run defaulting.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type VoiceComposeInput (snapshot + environment state)
  OUTPUT: boolean

  RETURN (input.tts_endpoint_latency > 500ms OR input.tts_endpoint_unreachable)
      OR (input.build_voice_state_raises_exception = true)
      OR (input.dialogue_turn_age > VOICE_DIALOGUE_MAX_AGE_SECONDS AND input.showrunner_headline = empty)
      OR (input.health_probe_failed = true AND input.retry_count = 0)
      OR (input.VOICE_DRY_RUN = unset)
END FUNCTION
```

### Examples

- **Synchronous probe blocking**: TTS endpoint responds in 1200ms → `compose()` blocks for 1.2s on the inline `probe_url()` call, causing a 1.2s audio gap in the OBS stream
- **Swallowed exception**: `build_voice_state(snapshot)` raises `KeyError` inside `_finalize_snapshot()` → exception is caught at DEBUG level, `voice` key is omitted from snapshot, no voice plan reaches TTS
- **Abrupt fallback**: Dialogue turn is 25s old, no showrunner headline exists → pipeline emits "The world keeps moving." causing a jarring content switch and TTS re-queue silence
- **No probe retry**: Single DNS timeout on health probe → `health.ok=False` persists for entire snapshot cycle (up to 30s), blocking voice plan delivery
- **Silent dry-run**: Operator deploys without setting `VOICE_DRY_RUN` → defaults to `"true"`, all TTS output is suppressed with no log entry indicating why

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- When TTS endpoint responds within normal latency (<500ms), voice plans continue to be produced with accurate health status on every snapshot cycle
- When `build_voice_state(snapshot)` succeeds without error, the complete `voice` key is included in the world snapshot with the full VoiceState payload
- When dialogue turn is fresh (age < max threshold) and contains content, the dialogue turn's content and sender are used as voice plan speaker and line
- When `VOICE_DRY_RUN` is explicitly set to `"false"`, live TTS output is produced without behavioral change
- UUID stripping, emoji removal, and narrative prefix cleaning continue to work identically on all dialogue lines

**Scope:**
All inputs where none of the five bug conditions hold should be completely unaffected by this fix. This includes:
- Normal-latency health probes (<500ms response)
- Successful `build_voice_state` calls (no exceptions)
- Fresh dialogue turns with valid content
- Successful health probes (no failure, no retry needed)
- Explicitly configured `VOICE_DRY_RUN=false` deployments

## Hypothesized Root Cause

Based on the bug description and source code analysis, the root causes are:

1. **Synchronous probe_url() in compose()**: `VoiceSurface.compose()` calls `probe_url()` inline at line ~150 with a 1.5s timeout. This is a blocking network call inside the hot path of voice plan composition. When the TTS endpoint is slow or unreachable, the entire composition loop stalls.

2. **Missing exception handling in build_voice_state()**: The module-level `build_voice_state(snapshot)` function at line ~193 calls `VoiceSurface().compose(snapshot)` without any try/except. If it's called from `world_snapshot._finalize_snapshot()` where exceptions are caught at DEBUG level, failures become invisible.

3. **Hard-coded static fallback string**: When dialogue age exceeds the max threshold and no showrunner headline is available, the code falls back to the literal string `"The world keeps moving."` (line ~133). There is no graceful transition — the pipeline immediately switches content, causing TTS to re-queue.

4. **Single-shot health probe with no retry**: `probe_url()` is called once per composition cycle. If it fails, `health.ok=False` is set immediately with no retry logic. The pipeline stays in an unhealthy state until the next full snapshot cycle.

5. **Default dry-run=true with no warning**: `_env_bool("VOICE_DRY_RUN", "true")` at line ~30 defaults to dry-run enabled. When the environment variable is unset, TTS output is silently disabled. No log message alerts operators to this state.

## Correctness Properties

Property 1: Bug Condition - Voice Plan Production Under Failure

_For any_ input where the bug condition holds (isBugCondition returns true), the fixed `VoiceSurface.compose()` SHALL produce a valid VoicePlan without blocking for more than 200ms, SHALL log any errors or degraded states at WARNING level or higher, and SHALL not silently suppress TTS output.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**

Property 2: Preservation - Normal Voice Pipeline Behavior

_For any_ input where the bug condition does NOT hold (isBugCondition returns false), the fixed `VoiceSurface.compose()` SHALL produce exactly the same VoiceState (plan, health, configuration) as the original function, preserving all text stripping, emotion selection, speed calculation, and health reporting behavior.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `runtime/src/voice/engine.py`

**Function**: `VoiceSurface.compose()` and supporting functions

**Specific Changes**:

1. **Async/Cached Health Probes**: Replace the inline `probe_url()` call in `compose()` with a cached health status. Introduce a background task or time-based cache (TTL ~5s) so that `compose()` never blocks on network I/O. The `build_voice_status()` function can continue using synchronous probes since it's not in the hot path.
   - Add a `_CachedHealthProbe` class with TTL-based caching
   - Replace `health = probe_url(...)` in `compose()` with `health = self._cached_health.get()`
   - Probe runs asynchronously or on a background thread

2. **Exception Handling in build_voice_state()**: Wrap the `VoiceSurface().compose(snapshot)` call in a try/except that logs at WARNING level with structured context (exception type, snapshot keys, timestamp).
   - Add try/except around `compose()` call
   - Log at `logging.WARNING` with exception info
   - Return a degraded VoiceState rather than propagating the exception

3. **Graceful Fallback Content**: When dialogue age exceeds the threshold and no showrunner content is available, continue the previous voice plan (stash last successful plan) or emit a brief silence marker rather than switching to a static string.
   - Add `_last_plan` instance variable to `VoiceSurface`
   - When fallback would trigger, reuse `_last_plan` if available
   - If no previous plan exists, use the static string but log at INFO level

4. **Health Probe Retry with Backoff**: Add retry logic (1 retry with ~500ms backoff) to the health probe before marking the endpoint unhealthy. Auto-recover when endpoint responds.
   - Create `_probe_with_retry(url, timeout, max_retries=1)` helper
   - On first failure, wait 500ms and retry once
   - On recovery, immediately set `health.ok=True`

5. **Dry-Run Warning at Startup**: Log a WARNING when `VOICE_DRY_RUN` defaults to `"true"` because the environment variable is unset. Distinguish between explicit `VOICE_DRY_RUN=true` (intentional) and unset (possibly accidental).
   - In `VoiceSurface.__init__()`, check if `os.getenv("VOICE_DRY_RUN")` is None
   - If None and dry_run resolves to True, log WARNING: "VOICE_DRY_RUN is not set; defaulting to dry-run mode (no TTS output)"
   - If explicitly set to "true", log at DEBUG level only

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write tests that invoke `VoiceSurface.compose()` and `build_voice_state()` under each failure condition, measuring latency, log output, and return values. Run these tests on the UNFIXED code to observe failures.

**Test Cases**:
1. **Synchronous Blocking Test**: Mock `probe_url()` to sleep 1.2s, call `compose()`, assert wall-clock time exceeds 1s (will demonstrate blocking on unfixed code)
2. **Swallowed Exception Test**: Pass a snapshot that causes `build_voice_state()` to raise inside `_finalize_snapshot()`, assert no WARNING log is emitted (will confirm silent failure on unfixed code)
3. **Abrupt Fallback Test**: Set dialogue turn age to 25s with no showrunner headline, assert output is the static string "The world keeps moving." (will demonstrate abrupt switch on unfixed code)
4. **No Retry Test**: Mock `probe_url()` to fail once then succeed, call `compose()`, assert `health.ok=False` without retry (will demonstrate single-shot failure on unfixed code)
5. **Silent Dry-Run Test**: Unset `VOICE_DRY_RUN`, instantiate `VoiceSurface`, assert no WARNING log about dry-run mode (will demonstrate silent default on unfixed code)

**Expected Counterexamples**:
- `compose()` blocks for >1s when TTS endpoint is slow
- No WARNING-level log when `build_voice_state` fails
- Static fallback string emitted without transition
- `health.ok=False` after single probe failure with no retry attempt
- No log output when dry-run defaults to enabled

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := VoiceSurface_fixed.compose(input.snapshot)
  ASSERT result.plan IS NOT NULL
  ASSERT compose_duration <= 200ms
  ASSERT (result.health.ok = true OR result.health.degraded = true)
  ASSERT warning_or_error_logged(input)
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT VoiceSurface(input.snapshot).compose() = VoiceSurface_fixed(input.snapshot).compose()
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many snapshot configurations automatically across the input domain
- It catches edge cases in text stripping, emotion selection, and speed calculation that manual tests might miss
- It provides strong guarantees that normal voice pipeline behavior is unchanged

**Test Plan**: Observe behavior on UNFIXED code first for normal snapshots (healthy endpoint, successful build, fresh dialogue), then write property-based tests capturing that behavior.

**Test Cases**:
1. **Normal Health Probe Preservation**: Verify that when TTS responds in <500ms, voice plans are produced identically to unfixed code
2. **Successful Build Preservation**: Verify that `build_voice_state()` returns the same VoiceState payload when no exception occurs
3. **Fresh Dialogue Preservation**: Verify that fresh dialogue turns produce the same speaker/line/emotion in fixed vs unfixed code
4. **Explicit Dry-Run False Preservation**: Verify that `VOICE_DRY_RUN=false` produces live TTS output identically
5. **Text Stripping Preservation**: Verify UUID, emoji, and narrative prefix stripping produces identical results

### Unit Tests

- Test cached health probe returns stale-but-valid result when endpoint is slow
- Test `build_voice_state()` logs WARNING and returns degraded state on exception
- Test graceful fallback reuses previous plan when dialogue is stale and no headline exists
- Test health probe retries once before marking unhealthy
- Test dry-run WARNING is logged when env var is unset
- Test dry-run WARNING is NOT logged when env var is explicitly "true"

### Property-Based Tests

- Generate random snapshots with valid dialogue turns and verify `compose()` output is identical between fixed and unfixed code (preservation)
- Generate random probe latencies and failure patterns, verify `compose()` never blocks >200ms (fix condition)
- Generate random exception types in `build_voice_state()`, verify all produce WARNING logs with structured context (fix condition)
- Generate random dialogue ages and showrunner states, verify graceful fallback behavior (fix condition)

### Integration Tests

- Test full voice pipeline cycle: snapshot → compose → VoicePlan delivered to TTS mock within 200ms
- Test recovery after health probe failure: probe fails → retries → succeeds → voice plan delivered
- Test operator visibility: deploy without VOICE_DRY_RUN → verify WARNING appears in structured logs
- Test content continuity: stale dialogue with no headline → previous plan reused → no audible gap
