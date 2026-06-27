# Bugfix Requirements Document

## Introduction

Audio drops intermittently during live broadcast. The voice pipeline (`runtime/src/voice/engine.py`) composes a `VoicePlan` from the world snapshot and delegates TTS to the external Kokoro service, with rendered audio piped to OBS. Multiple code-level failure modes can silently suppress voice plan production, causing the audio stream to go silent without any user-visible error.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the `probe_url()` health check is called synchronously during `VoiceSurface.compose()` and the TTS endpoint is slow or unreachable THEN the system blocks voice plan production for up to 1.5 seconds per snapshot cycle, causing audible gaps or complete audio stalls

1.2 WHEN `build_voice_state(snapshot)` raises any exception inside `world_snapshot._finalize_snapshot()` THEN the system swallows the exception with only a DEBUG log message and omits the `voice` key from the snapshot entirely, resulting in no voice plan reaching the TTS pipeline

1.3 WHEN the dialogue turn age exceeds `VOICE_DIALOGUE_MAX_AGE_SECONDS` (20s default) and no showrunner headline is available THEN the system falls back to the static string "The world keeps moving." causing an abrupt content switch that may produce a silence gap during TTS re-queue

1.4 WHEN a single `probe_url()` call fails THEN the system sets `health.ok=False` with no retry or recovery mechanism, leaving voice marked unhealthy until the next full snapshot cycle

1.5 WHEN `VOICE_DRY_RUN` environment variable is reset or unset THEN the system defaults to `"true"` (dry-run mode enabled), silently disabling actual TTS output with no warning logged

### Expected Behavior (Correct)

2.1 WHEN the TTS health endpoint is slow or unreachable THEN the system SHALL perform health probes asynchronously or use a cached health status so that voice plan composition is never blocked by network latency

2.2 WHEN `build_voice_state(snapshot)` raises an exception THEN the system SHALL log the error at WARNING or ERROR level with full context (exception type, message, relevant snapshot keys) and SHALL emit a metric/structured log event indicating voice plan generation failed

2.3 WHEN the dialogue turn age exceeds the max age threshold and no showrunner content is available THEN the system SHALL gracefully continue the previous voice plan or emit a brief transitional pause rather than abruptly switching to a static fallback line

2.4 WHEN a health probe fails THEN the system SHALL retry at least once with exponential backoff before marking the TTS endpoint as unhealthy, and SHALL automatically recover when the endpoint responds successfully on subsequent probes

2.5 WHEN `VOICE_DRY_RUN` defaults to enabled (true) THEN the system SHALL log a WARNING at startup indicating that voice output is in dry-run mode, making the silent-output state visible to operators

### Unchanged Behavior (Regression Prevention)

3.1 WHEN the TTS endpoint responds within normal latency (<500ms) THEN the system SHALL CONTINUE TO produce voice plans with accurate health status on every snapshot cycle

3.2 WHEN `build_voice_state(snapshot)` succeeds without error THEN the system SHALL CONTINUE TO include the complete `voice` key in the world snapshot with the full VoiceState payload

3.3 WHEN the dialogue turn is fresh (age < max threshold) and contains content THEN the system SHALL CONTINUE TO use the dialogue turn's content and sender as the voice plan speaker and line

3.4 WHEN `VOICE_DRY_RUN` is explicitly set to `"false"` THEN the system SHALL CONTINUE TO produce live TTS output without any behavioral change

3.5 WHEN the voice pipeline is operating normally with a healthy TTS endpoint THEN the system SHALL CONTINUE TO strip UUIDs, emojis, and narrative prefixes from dialogue lines before sending to TTS

---

## Bug Condition (Formal)

```pascal
FUNCTION isBugCondition(X)
  INPUT: X of type VoiceComposeInput (snapshot + environment state)
  OUTPUT: boolean

  // Returns true when any audio-drop failure mode is triggered
  RETURN (X.tts_endpoint_latency > 500ms OR X.tts_endpoint_unreachable)
      OR (X.build_voice_state_raises_exception = true)
      OR (X.dialogue_turn_age > VOICE_DIALOGUE_MAX_AGE_SECONDS AND X.showrunner_headline = empty)
      OR (X.health_probe_failed = true AND X.retry_count = 0)
      OR (X.VOICE_DRY_RUN = unset)
END FUNCTION
```

```pascal
// Property: Fix Checking — Voice pipeline resilience
FOR ALL X WHERE isBugCondition(X) DO
  result ← VoiceSurface'.compose(X.snapshot)
  ASSERT result.plan IS NOT NULL
      AND (result.health.ok = true OR result.health.degraded = true)
      AND voice_plan_produced_within(X, 200ms)
      AND error_is_logged_at_warning_or_higher(X)
END FOR
```

```pascal
// Property: Preservation Checking — Normal voice operation unchanged
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT VoiceSurface(X.snapshot) = VoiceSurface'(X.snapshot)
END FOR
```
