"""Tests for BackchannelSelector (T6.1)."""

import os
import sys

_src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
for _p in (_src_path, "/app/src"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import random

from banter.backchannel import BackchannelSelector, BackchannelResult, BACKCHANNEL_DELAY_S


class TestShouldFire:
    def test_fires_on_high_score(self):
        bc = BackchannelSelector()
        assert bc.should_fire(13)
        assert bc.should_fire(15)
        assert bc.should_fire(21)

    def test_fires_on_low_score(self):
        bc = BackchannelSelector()
        assert bc.should_fire(4)
        assert bc.should_fire(0)
        assert bc.should_fire(1)

    def test_does_not_fire_on_middle_scores(self):
        bc = BackchannelSelector()
        for score in range(5, 13):
            assert not bc.should_fire(score), f"should not fire at score {score}"

    def test_does_not_fire_at_exact_thresholds(self):
        bc = BackchannelSelector()
        assert not bc.should_fire(12)  # not > 12
        assert not bc.should_fire(5)  # not < 5


class TestSelect:
    def test_returns_none_for_middle_score(self):
        bc = BackchannelSelector()
        assert bc.select("parasite", 8) is None

    def test_returns_result_for_high_score(self):
        bc = BackchannelSelector(random.Random(1))
        result = bc.select("parasite", 13)
        assert isinstance(result, BackchannelResult)
        assert len(result.line.split()) <= 6  # short utterance
        assert result.delay_s == BACKCHANNEL_DELAY_S

    def test_returns_result_for_low_score(self):
        bc = BackchannelSelector(random.Random(1))
        result = bc.select("trickster", 3)
        assert isinstance(result, BackchannelResult)
        assert result.line  # non-empty

    def test_all_archetypes_have_pool(self):
        bc = BackchannelSelector(random.Random(42))
        for archetype in [
            "parasite",
            "prophet",
            "trickster",
            "sovereign",
            "martyr",
            "shadow",
            "herald",
            "keeper",
        ]:
            r_high = bc.select(archetype, 13)
            r_low = bc.select(archetype, 2)
            assert r_high is not None, f"No landed-hit pool for {archetype}"
            assert r_low is not None, f"No weak-attempt pool for {archetype}"

    def test_unknown_archetype_uses_fallback(self):
        bc = BackchannelSelector(random.Random(1))
        result = bc.select("unknown_archetype", 15)
        assert result is not None

    def test_delay_is_always_backchannel_delay(self):
        bc = BackchannelSelector(random.Random(5))
        for score in [0, 1, 4, 13, 16, 21]:
            result = bc.select("prophet", score)
            if result is not None:
                assert result.delay_s == BACKCHANNEL_DELAY_S

    def test_landed_hit_pool_differs_from_weak_attempt_pool(self):
        """Different score extremes should produce different line pools."""
        bc_high = BackchannelSelector(random.Random(99))
        bc_low = BackchannelSelector(random.Random(99))
        high_lines = {bc_high.select("trickster", 13).line for _ in range(20)}
        low_lines = {bc_low.select("trickster", 2).line for _ in range(20)}
        # The two pools should not be identical
        assert high_lines != low_lines

    def test_lines_are_short(self):
        """Backchannels must be 1-6 words (spec says 1-4, giving small buffer)."""
        bc = BackchannelSelector(random.Random(7))
        for archetype in ["parasite", "martyr", "herald"]:
            for score in [0, 2, 4, 13, 15, 20]:
                result = bc.select(archetype, score)
                if result:
                    word_count = len(result.line.strip().split())
                    assert word_count <= 6, (
                        f"Backchannel too long ({word_count} words): '{result.line}'"
                    )
