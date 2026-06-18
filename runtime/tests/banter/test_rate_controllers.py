"""Unit tests for the SlidingWindowController.

Tests the deque-based sliding window rate controller used to replace
scattered random.random() < X patterns with deterministic rate limiting.
"""

from __future__ import annotations

import pytest

import os
import sys

# Path setup: add src/ to sys.path so `from banter.<module>` resolves correctly.
_src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
for _p in (_src_path, "/app/src"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from banter.rate_controllers import SlidingWindowController


class TestSlidingWindowControllerInit:
    """Initialization and validation."""

    def test_basic_init(self):
        ctrl = SlidingWindowController(max_count=1, window_size=30)
        assert ctrl.max_count == 1
        assert ctrl.window_size == 30
        assert ctrl.beat == 0

    def test_negative_max_count_raises(self):
        with pytest.raises(ValueError, match="max_count must be >= 0"):
            SlidingWindowController(max_count=-1, window_size=10)

    def test_zero_window_size_raises(self):
        with pytest.raises(ValueError, match="window_size must be >= 1"):
            SlidingWindowController(max_count=1, window_size=0)

    def test_zero_max_count_is_valid(self):
        """max_count=0 means nothing is ever allowed."""
        ctrl = SlidingWindowController(max_count=0, window_size=10)
        assert ctrl.allow("any_key") is False


class TestAllow:
    """Tests for the allow() method."""

    def test_unknown_key_auto_initializes_and_allows(self):
        """Key not found: auto-initialize empty window, allow first request."""
        ctrl = SlidingWindowController(max_count=1, window_size=30)
        assert ctrl.allow("new_key") is True

    def test_allow_after_recording_within_limit(self):
        ctrl = SlidingWindowController(max_count=2, window_size=10)
        ctrl.record("k")
        assert ctrl.allow("k") is True

    def test_deny_when_at_max(self):
        ctrl = SlidingWindowController(max_count=1, window_size=30)
        ctrl.record("pair:A:B")
        assert ctrl.allow("pair:A:B") is False

    def test_allow_after_window_expires(self):
        """Window overflow: oldest entry evicted, new entry allowed."""
        ctrl = SlidingWindowController(max_count=1, window_size=5)
        ctrl.record("k")  # recorded at beat 0
        # Advance past the window
        for _ in range(6):
            ctrl.tick()
        # Now beat=6, window covers beats (1..6], beat 0 is stale
        assert ctrl.allow("k") is True

    def test_independent_keys(self):
        ctrl = SlidingWindowController(max_count=1, window_size=30)
        ctrl.record("pair:A:B")
        assert ctrl.allow("pair:A:B") is False
        assert ctrl.allow("pair:C:D") is True


class TestRecord:
    """Tests for the record() method."""

    def test_record_uses_internal_beat_by_default(self):
        ctrl = SlidingWindowController(max_count=2, window_size=10)
        ctrl.tick()  # beat=1
        ctrl.record("k")
        assert ctrl.count("k") == 1

    def test_record_with_explicit_beat(self):
        ctrl = SlidingWindowController(max_count=2, window_size=10)
        ctrl.record("k", beat=5)
        # Advance past window so beat 5 is stale
        ctrl._beat = 16
        assert ctrl.count("k") == 0

    def test_multiple_records_fill_window(self):
        ctrl = SlidingWindowController(max_count=3, window_size=10)
        ctrl.record("k")
        ctrl.tick()
        ctrl.record("k")
        ctrl.tick()
        ctrl.record("k")
        assert ctrl.allow("k") is False
        assert ctrl.count("k") == 3


class TestReset:
    """Tests for the reset() method."""

    def test_reset_clears_activations(self):
        ctrl = SlidingWindowController(max_count=1, window_size=30)
        ctrl.record("k")
        assert ctrl.allow("k") is False
        ctrl.reset("k")
        assert ctrl.allow("k") is True

    def test_reset_nonexistent_key_is_safe(self):
        ctrl = SlidingWindowController(max_count=1, window_size=30)
        ctrl.reset("does_not_exist")  # should not raise


class TestTick:
    """Tests for the tick() method."""

    def test_tick_advances_beat(self):
        ctrl = SlidingWindowController(max_count=1, window_size=10)
        assert ctrl.beat == 0
        new_beat = ctrl.tick()
        assert new_beat == 1
        assert ctrl.beat == 1

    def test_tick_monotonic(self):
        ctrl = SlidingWindowController(max_count=1, window_size=10)
        beats = [ctrl.tick() for _ in range(5)]
        assert beats == [1, 2, 3, 4, 5]


class TestSlidingWindowBehavior:
    """Integration-level tests for the sliding window contract."""

    def test_crack_rate_limit_1_per_30_beats(self):
        """CRACK: max 1 per 30 eligible beats per pair (Requirement 12.4)."""
        ctrl = SlidingWindowController(max_count=1, window_size=30)
        pair_id = "Elder_A:Elder_B"

        # First CRACK allowed
        assert ctrl.allow(pair_id) is True
        ctrl.record(pair_id)

        # Subsequent attempts within window denied
        for _ in range(29):
            ctrl.tick()
            assert ctrl.allow(pair_id) is False

        # After 30 beats the window slides past
        ctrl.tick()
        assert ctrl.allow(pair_id) is True

    def test_veil_layer_every_8th_beat(self):
        """VeilLayer: every 8th eligible beat (Requirement 12.4)."""
        ctrl = SlidingWindowController(max_count=1, window_size=8)
        key = "veil"
        firings = []

        for i in range(32):
            ctrl.tick()
            if ctrl.allow(key):
                ctrl.record(key)
                firings.append(ctrl.beat)

        # Should fire roughly every 8 beats
        gaps = [firings[i + 1] - firings[i] for i in range(len(firings) - 1)]
        assert all(g == 8 for g in gaps)

    def test_subtext_max_2_in_10_beats(self):
        """Subtext high tension: max 2 in any 10 eligible beats."""
        ctrl = SlidingWindowController(max_count=2, window_size=10)
        key = "subtext"

        # Record two activations
        ctrl.record(key)
        ctrl.tick()
        ctrl.record(key)

        # Third should be denied
        assert ctrl.allow(key) is False

        # Advance past window for first entry
        for _ in range(10):
            ctrl.tick()

        # Now one slot freed
        assert ctrl.allow(key) is True

    def test_window_evicts_oldest_entries(self):
        """Oldest entry evicted when window slides."""
        ctrl = SlidingWindowController(max_count=2, window_size=5)
        key = "test"

        # Beat 0: record
        ctrl.record(key)
        # Beat 2: record (advance one tick first)
        ctrl.tick()
        ctrl.tick()
        ctrl.record(key)  # recorded at beat 2
        # Both in window, at max
        assert ctrl.allow(key) is False

        # Advance to beat 5 — cutoff = 5-5 = 0, beat 0 evicted (0 <= 0)
        # beat 2 remains (2 > 0)
        for _ in range(3):
            ctrl.tick()
        assert ctrl.count(key) == 1
        assert ctrl.allow(key) is True
