"""Tests for cross-pair eavesdropping (T3.2)."""

import os
import sys

_src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
for _p in (_src_path, "/app/src"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from banter.scene_context import SceneContext


class TestRecordPairLine:
    def test_records_and_retrieves(self):
        sc = SceneContext()
        sc.record_pair_line("forge", "weave", "I built what you destroyed.")
        result = sc.get_other_pair_line("ash", "echo")
        assert result == ("forge", "weave", "I built what you destroyed.")

    def test_overwrites_same_pair(self):
        sc = SceneContext()
        sc.record_pair_line("forge", "weave", "line one")
        sc.record_pair_line("forge", "weave", "line two")
        result = sc.get_other_pair_line("ash", "echo")
        assert result is not None
        assert result[2] == "line two"

    def test_pair_order_is_normalized(self):
        sc = SceneContext()
        sc.record_pair_line("weave", "forge", "weave speaks")
        result = sc.get_other_pair_line("ash", "echo")
        assert result is not None
        assert result[2] == "weave speaks"

    def test_stores_multiple_different_pairs(self):
        sc = SceneContext()
        sc.record_pair_line("forge", "weave", "line A")
        sc.record_pair_line("ash", "echo", "line B")
        # From forge+weave's perspective, get other pair
        result = sc.get_other_pair_line("forge", "weave")
        assert result is not None
        assert result[2] == "line B"


class TestGetOtherPairLine:
    def test_returns_none_when_no_other_pairs(self):
        sc = SceneContext()
        sc.record_pair_line("forge", "weave", "hello")
        result = sc.get_other_pair_line("forge", "weave")
        assert result is None

    def test_returns_none_on_empty_buffer(self):
        sc = SceneContext()
        result = sc.get_other_pair_line("forge", "weave")
        assert result is None

    def test_excludes_current_pair(self):
        sc = SceneContext()
        sc.record_pair_line("forge", "weave", "current pair line")
        result = sc.get_other_pair_line("forge", "weave")
        assert result is None

    def test_returns_correct_speaker_names(self):
        sc = SceneContext()
        sc.record_pair_line("elder_x", "elder_y", "overheard line")
        result = sc.get_other_pair_line("other_a", "other_b")
        assert result is not None
        elder_x, elder_y, line = result
        assert "elder_x" in (elder_x, elder_y)
        assert "elder_y" in (elder_x, elder_y)
        assert line == "overheard line"

    def test_symmetric_current_pair_exclusion(self):
        """Both (A,B) and (B,A) as current pair should exclude the same stored entry."""
        sc = SceneContext()
        sc.record_pair_line("forge", "weave", "a line")
        assert sc.get_other_pair_line("forge", "weave") is None
        assert sc.get_other_pair_line("weave", "forge") is None

    def test_three_pairs_cross_visibility(self):
        sc = SceneContext()
        sc.record_pair_line("forge", "weave", "fw line")
        sc.record_pair_line("ash", "echo", "ae line")
        sc.record_pair_line("ruin", "veil", "rv line")
        # forge+weave should see a line from one of the other two pairs
        result = sc.get_other_pair_line("forge", "weave")
        assert result is not None
        assert result[2] in ("ae line", "rv line")
