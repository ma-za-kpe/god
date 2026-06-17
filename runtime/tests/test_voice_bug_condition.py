"""Bug condition exploration property test for voice pipeline audio drops.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**

This test encodes the EXPECTED (fixed) behavior for the five failure modes
that cause audio drops in the voice pipeline. On unfixed code, these tests
MUST FAIL — failure confirms the bug exists.

Property 1: Bug Condition - Voice Plan Production Under Failure Modes
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any
from unittest.mock import patch

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from voice.engine import VoiceSurface, build_voice_state


# ---------------------------------------------------------------------------
# Test fixtures / helpers
# ---------------------------------------------------------------------------

def _base_snapshot(epoch: int = 1000, dialogue_age: int = 5) -> dict[str, Any]:
    """Create a base snapshot with fresh dialogue turn."""
    sent_at = epoch - dialogue_age
    return {
        "epoch": epoch,
        "showrunner": {
            "scene": "ensemble-stage",
            "speaker": "Alpha",
            "headline": "Alpha takes the mic.",
            "audience_prompt": "Watch the exchange.",
        },
        "audience": {"patronage_index": 14.0},
        "broadcast": {
            "caption": {"headline": "Alpha takes the mic."},
            "scene": {"scene_name": "ensemble-stage", "speaker": "Alpha"},
        },
        "last_dialogue_turn": {
            "content": "Hello world, this is a test line.",
            "sender_name": "Elder-Hook-6A4A",
            "sent_at": sent_at,
        },
    }


def _stale_snapshot_no_headline() -> dict[str, Any]:
    """Snapshot with stale dialogue (age=25s) and NO showrunner headline."""
    return {
        "epoch": 1000,
        "showrunner": {
            "scene": "ensemble-stage",
            "speaker": "Alpha",
            # No headline, no audience_prompt
        },
        "audience": {"patronage_index": 14.0},
        "broadcast": {
            "caption": {},
            "scene": {"scene_name": "ensemble-stage", "speaker": "Alpha"},
        },
        "last_dialogue_turn": {
            "content": "Some old content that is stale now.",
            "sender_name": "Elder-Hook-6A4A",
            "sent_at": 975,  # epoch - sent_at = 25s > 20s threshold
        },
    }


# ---------------------------------------------------------------------------
# Test 1: Synchronous blocking — compose() must complete within 200ms
# even when probe_url() has high latency (1200ms)
# ---------------------------------------------------------------------------

class TestSynchronousBlocking:
    """Bug condition 1.1: Synchronous probe_url() blocks compose()."""

    def test_compose_does_not_block_on_slow_probe(self):
        """Assert compose() completes within 200ms even when probe_url takes 1200ms.
        
        On unfixed code, compose() calls probe_url() synchronously inline,
        so it will block for ~1200ms, failing the 200ms assertion.
        """
        def slow_probe(url, timeout=1.5):
            time.sleep(1.2)  # Simulate 1200ms network latency
            return {"ok": True, "probe": "http", "url": url, "status_code": 200}

        surface = VoiceSurface(enabled=True, dry_run=False)
        snapshot = _base_snapshot()

        with patch("voice.engine.probe_url", side_effect=slow_probe):
            start = time.perf_counter()
            result = surface.compose(snapshot)
            elapsed = time.perf_counter() - start

        # Expected behavior: compose() should NOT block on network I/O
        assert elapsed <= 0.2, (
            f"compose() blocked for {elapsed:.3f}s (max 200ms allowed). "
            f"Bug condition 1.1: synchronous probe_url() blocks voice plan production."
        )
        # Voice plan should still be produced
        assert result.plan is not None, "Voice plan must not be None under failure mode"

    @given(latency=st.floats(min_value=0.5, max_value=2.0))
    @settings(max_examples=5, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_compose_bounded_latency_property(self, latency):
        """Property: For any probe latency > 500ms, compose() still finishes within 200ms.
        
        **Validates: Requirements 1.1**
        """
        def slow_probe(url, timeout=1.5):
            time.sleep(latency)
            return {"ok": True, "probe": "http", "url": url, "status_code": 200}

        surface = VoiceSurface(enabled=True, dry_run=False)
        snapshot = _base_snapshot()

        with patch("voice.engine.probe_url", side_effect=slow_probe):
            start = time.perf_counter()
            result = surface.compose(snapshot)
            elapsed = time.perf_counter() - start

        assert elapsed <= 0.2, (
            f"compose() took {elapsed:.3f}s with probe latency {latency:.3f}s. "
            f"Must complete within 200ms regardless of probe latency."
        )
        assert result.plan is not None


# ---------------------------------------------------------------------------
# Test 2: Swallowed exception — WARNING log must be emitted on failure
# ---------------------------------------------------------------------------

class TestSwallowedException:
    """Bug condition 1.2: Exception in build_voice_state() is swallowed silently."""

    def test_build_voice_state_logs_warning_on_exception(self, caplog):
        """Assert WARNING-level log is emitted when build_voice_state() encounters an error.
        
        On unfixed code, exceptions are swallowed at DEBUG level with no warning,
        making failures invisible.
        """
        # Create a snapshot that will cause a KeyError inside compose()
        snapshot = _base_snapshot()

        def raise_key_error(url, timeout=1.5):
            raise KeyError("missing_voice_key")

        with caplog.at_level(logging.DEBUG):
            with patch("voice.engine.probe_url", side_effect=raise_key_error):
                try:
                    result = build_voice_state(snapshot)
                except Exception:
                    pass  # Exception may propagate on unfixed code

        # Expected behavior: A WARNING or ERROR level log should be emitted
        warning_or_error_logs = [
            record for record in caplog.records
            if record.levelno >= logging.WARNING
        ]
        assert len(warning_or_error_logs) > 0, (
            "No WARNING-level log emitted when build_voice_state() encounters an error. "
            "Bug condition 1.2: exceptions are swallowed silently."
        )

    @given(exc_type=st.sampled_from([KeyError, ValueError, TypeError, AttributeError, RuntimeError]))
    @settings(max_examples=5, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_any_exception_produces_warning_log(self, caplog, exc_type):
        """Property: For any exception type in build_voice_state, WARNING log is emitted.
        
        **Validates: Requirements 1.2**
        """
        snapshot = _base_snapshot()

        def raise_exc(url, timeout=1.5):
            raise exc_type("simulated failure")

        with caplog.at_level(logging.DEBUG):
            with patch("voice.engine.probe_url", side_effect=raise_exc):
                try:
                    result = build_voice_state(snapshot)
                except Exception:
                    pass

        warning_or_error_logs = [
            record for record in caplog.records
            if record.levelno >= logging.WARNING
        ]
        assert len(warning_or_error_logs) > 0, (
            f"No WARNING-level log for {exc_type.__name__} in build_voice_state(). "
            f"Bug condition 1.2: exception handling must log at WARNING+."
        )


# ---------------------------------------------------------------------------
# Test 3: Abrupt fallback — should NOT use static "The world keeps moving."
# ---------------------------------------------------------------------------

class TestAbruptFallback:
    """Bug condition 1.3: Hard-coded static fallback causes abrupt content switch."""

    def test_stale_dialogue_no_static_fallback(self):
        """Assert output is NOT the static string when dialogue is stale and no headline exists.
        
        On unfixed code, the pipeline falls back to "The world keeps moving."
        when dialogue is stale (>20s) and no showrunner headline is available.
        """
        def mock_probe(url, timeout=1.5):
            return {"ok": True, "probe": "http", "url": url, "status_code": 200}

        surface = VoiceSurface(enabled=True, dry_run=False)
        snapshot = _stale_snapshot_no_headline()

        with patch("voice.engine.probe_url", side_effect=mock_probe):
            result = surface.compose(snapshot)

        # Expected behavior: Should NOT fall back to static string
        assert result.plan.line != "The world keeps moving.", (
            f"Voice plan used static fallback 'The world keeps moving.' "
            f"Bug condition 1.3: abrupt fallback with no graceful transition."
        )
        # Voice plan should still exist
        assert result.plan is not None

    @given(dialogue_age=st.integers(min_value=21, max_value=120))
    @settings(max_examples=5, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_stale_dialogue_graceful_fallback_property(self, dialogue_age):
        """Property: For any stale dialogue with no headline, output is NOT the static fallback.
        
        **Validates: Requirements 1.3**
        """
        def mock_probe(url, timeout=1.5):
            return {"ok": True, "probe": "http", "url": url, "status_code": 200}

        snapshot = {
            "epoch": 1000,
            "showrunner": {
                "scene": "ensemble-stage",
                "speaker": "Alpha",
                # No headline, no audience_prompt
            },
            "audience": {"patronage_index": 14.0},
            "broadcast": {
                "caption": {},
                "scene": {"scene_name": "ensemble-stage", "speaker": "Alpha"},
            },
            "last_dialogue_turn": {
                "content": "Some old dialogue content.",
                "sender_name": "Elder-Hook-6A4A",
                "sent_at": 1000 - dialogue_age,  # Stale: age > 20s
            },
        }

        surface = VoiceSurface(enabled=True, dry_run=False)
        with patch("voice.engine.probe_url", side_effect=mock_probe):
            result = surface.compose(snapshot)

        assert result.plan.line != "The world keeps moving.", (
            f"Static fallback used with dialogue age={dialogue_age}s. "
            f"Expected graceful transition, not abrupt fallback."
        )


# ---------------------------------------------------------------------------
# Test 4: No retry — health probe should retry on failure
# ---------------------------------------------------------------------------

class TestNoRetry:
    """Bug condition 1.4: Single probe failure marks unhealthy with no retry."""

    def test_health_probe_retries_after_failure(self):
        """Assert health.ok=True after probe fails once then succeeds on retry.
        
        On unfixed code, a single probe failure sets health.ok=False with no retry,
        leaving voice marked unhealthy for the entire snapshot cycle.
        """
        call_count = {"n": 0}

        def fail_then_succeed(url, timeout=1.5):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return {"ok": False, "probe": "http", "url": url, "reason": "timeout"}
            return {"ok": True, "probe": "http", "url": url, "status_code": 200}

        surface = VoiceSurface(enabled=True, dry_run=False)
        snapshot = _base_snapshot()

        with patch("voice.engine.probe_url", side_effect=fail_then_succeed):
            result = surface.compose(snapshot)

        # Expected behavior: Should retry and recover
        assert result.health.get("ok") is True, (
            f"Health probe shows ok={result.health.get('ok')} after single failure. "
            f"Bug condition 1.4: no retry mechanism, health stays False."
        )

    @given(failures_before_success=st.integers(min_value=1, max_value=1))
    @settings(max_examples=3, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_probe_retry_recovers_property(self, failures_before_success):
        """Property: After N transient failures (N<=max_retries), health recovers.
        
        **Validates: Requirements 1.4**
        """
        call_count = {"n": 0}

        def transient_failure(url, timeout=1.5):
            call_count["n"] += 1
            if call_count["n"] <= failures_before_success:
                return {"ok": False, "probe": "http", "url": url, "reason": "timeout"}
            return {"ok": True, "probe": "http", "url": url, "status_code": 200}

        surface = VoiceSurface(enabled=True, dry_run=False)
        snapshot = _base_snapshot()

        with patch("voice.engine.probe_url", side_effect=transient_failure):
            call_count["n"] = 0
            result = surface.compose(snapshot)

        assert result.health.get("ok") is True, (
            f"Health did not recover after {failures_before_success} transient failure(s). "
            f"Expected retry to recover."
        )


# ---------------------------------------------------------------------------
# Test 5: Silent dry-run — WARNING must be logged when env var is unset
# ---------------------------------------------------------------------------

class TestSilentDryRun:
    """Bug condition 1.5: VOICE_DRY_RUN defaults to true with no warning."""

    def test_dry_run_warning_when_unset(self, caplog):
        """Assert WARNING log about dry-run mode when VOICE_DRY_RUN is not set.
        
        On unfixed code, when VOICE_DRY_RUN env var is unset, the system
        defaults to dry-run=true without any warning, silently disabling TTS.
        """
        env = os.environ.copy()
        env.pop("VOICE_DRY_RUN", None)

        with caplog.at_level(logging.DEBUG):
            with patch.dict(os.environ, env, clear=True):
                surface = VoiceSurface()

        # Expected behavior: WARNING log should be emitted about dry-run default
        warning_logs = [
            record for record in caplog.records
            if record.levelno >= logging.WARNING
            and ("dry" in record.message.lower() or "dry_run" in record.message.lower()
                 or "DRY_RUN" in record.message)
        ]
        assert len(warning_logs) > 0, (
            "No WARNING log about dry-run mode when VOICE_DRY_RUN is unset. "
            "Bug condition 1.5: silent dry-run default disables TTS without operator notice."
        )

    @given(st.just(None))  # Property: whenever env var is unset, WARNING is logged
    @settings(max_examples=3, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_unset_env_var_always_warns_property(self, _):
        """Property: Whenever VOICE_DRY_RUN is unset, a WARNING log is emitted.
        
        **Validates: Requirements 1.5**
        """
        import logging as _logging

        # Create a handler to capture logs
        log_records = []

        class CaptureHandler(_logging.Handler):
            def emit(self, record):
                log_records.append(record)

        handler = CaptureHandler()
        logger = _logging.getLogger()
        logger.addHandler(handler)
        logger.setLevel(_logging.DEBUG)

        try:
            env = os.environ.copy()
            env.pop("VOICE_DRY_RUN", None)

            with patch.dict(os.environ, env, clear=True):
                surface = VoiceSurface()

            warning_logs = [
                r for r in log_records
                if r.levelno >= _logging.WARNING
                and ("dry" in r.message.lower() or "DRY_RUN" in r.message)
            ]
            assert len(warning_logs) > 0, (
                "VOICE_DRY_RUN unset but no WARNING emitted about dry-run mode."
            )
        finally:
            logger.removeHandler(handler)
