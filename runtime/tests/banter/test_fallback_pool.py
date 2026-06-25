"""Tests for Fallback_Pool module.

Property tests for Properties 4, 5, 6 (pool completeness, no raw tokens,
weight decay).
"""

import os
import sys

import pytest
from hypothesis import given, settings

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from banter.fallback_pool import FallbackPool, _PLACEHOLDER_RE
from banter.types import FallbackTemplate

from conftest import (
    st_context_fragments,
    ARCHETYPES,
    FALLBACK_MOVE_TYPES,
)


# ---------------------------------------------------------------------------
# Property 4: Fallback Pool Completeness
# ---------------------------------------------------------------------------


class TestProperty4Completeness:
    """For any archetype, pool has ≥12 templates total and ≥2 per move type."""

    def test_default_pool_meets_minimums(self):
        """The shipped fallback_templates.json meets all minimum requirements.

        Construction itself validates, so if it doesn't raise, it's valid.
        """
        pool = FallbackPool.from_json_file()
        # If we get here without ValueError, validation passed
        assert pool is not None

    def test_all_archetypes_present(self):
        """All 8 archetypes have templates in the pool."""
        pool = FallbackPool.from_json_file()
        for archetype in ARCHETYPES:
            assert archetype in pool._by_archetype, f"Missing archetype: {archetype}"
            assert len(pool._by_archetype[archetype]) >= 12

    def test_all_move_types_per_archetype(self):
        """Each archetype has at least 2 templates per move type."""
        pool = FallbackPool.from_json_file()
        for archetype in ARCHETYPES:
            for move in FALLBACK_MOVE_TYPES:
                templates = pool._by_archetype_move.get(archetype, {}).get(move, [])
                assert len(templates) >= 2, (
                    f"{archetype}/{move} has only {len(templates)} templates, need 2"
                )

    def test_insufficient_pool_raises_error(self):
        """Pool with too few templates should fail validation on construction."""
        templates = [
            FallbackTemplate(
                template_id="test_01",
                archetype="prophet",
                move_type="COUNTER",
                template="A test line.",
                base_weight=1.0,
            )
        ]
        with pytest.raises(ValueError, match="need at least"):
            FallbackPool(templates)


# ---------------------------------------------------------------------------
# Property 5: No Raw Template Tokens in Output
# ---------------------------------------------------------------------------


@settings(max_examples=200, deadline=2000)
@given(context=st_context_fragments())
def test_property_5_no_raw_tokens(context):
    """For any combination of available/unavailable context, output never
    contains raw {word} patterns."""
    pool = FallbackPool.from_json_file()

    # Try selecting for each archetype and move
    for archetype in ARCHETYPES[:3]:  # sample 3 archetypes for speed
        for move in FALLBACK_MOVE_TYPES[:3]:  # sample 3 moves
            selection = pool.select(
                archetype,
                move,
                opponent_name=context["opponent_name"],
                arc_theme=context["arc_theme"],
                callback_phrase=context["callback_phrase"],
            )
            # Must not contain any {word} patterns
            assert not _PLACEHOLDER_RE.search(selection.text), (
                f"Raw placeholder found in output: '{selection.text}'"
            )
            # Must be non-empty
            assert len(selection.text.strip()) > 0


class TestNoRawTokensUnit:
    """Unit tests for placeholder substitution edge cases."""

    def test_all_placeholders_provided(self):
        """With all context available, placeholders are substituted."""
        templates = [
            FallbackTemplate(
                template_id="t01",
                archetype="prophet",
                move_type="COUNTER",
                template="{opponent} knows the {theme} changes nothing. Remember {callback}.",
                base_weight=1.0,
            ),
        ]
        pool = FallbackPool(templates, min_per_archetype=0, min_per_move=0)
        result = pool.select(
            "prophet",
            "COUNTER",
            opponent_name="Alpha",
            arc_theme="truth",
            callback_phrase="what you said",
        )
        assert "{opponent}" not in result.text
        assert "{theme}" not in result.text
        assert "{callback}" not in result.text
        assert "Alpha" in result.text
        assert "truth" in result.text

    def test_no_placeholders_provided(self):
        """With no context, placeholders are removed gracefully."""
        templates = [
            FallbackTemplate(
                template_id="t01",
                archetype="prophet",
                move_type="COUNTER",
                template="{opponent} knows the {theme} changes nothing.",
                base_weight=1.0,
            ),
        ]
        pool = FallbackPool(templates, min_per_archetype=0, min_per_move=0)
        result = pool.select(
            "prophet",
            "COUNTER",
            opponent_name=None,
            arc_theme=None,
            callback_phrase=None,
        )
        assert "{" not in result.text
        assert "}" not in result.text

    def test_partial_context(self):
        """With partial context, available placeholders are filled, others removed."""
        templates = [
            FallbackTemplate(
                template_id="t01",
                archetype="prophet",
                move_type="COUNTER",
                template="{opponent} dodges the {theme} again.",
                base_weight=1.0,
            ),
        ]
        pool = FallbackPool(templates, min_per_archetype=0, min_per_move=0)
        result = pool.select(
            "prophet",
            "COUNTER",
            opponent_name="Beta",
            arc_theme=None,
        )
        assert "Beta" in result.text
        assert "{theme}" not in result.text


# ---------------------------------------------------------------------------
# Property 6: Fallback Weight Decay
# ---------------------------------------------------------------------------


class TestProperty6WeightDecay:
    """Templates used in last 10 beats get 50% reduction,
    session-used get 80% reduction."""

    def test_recent_beat_reduces_weight(self):
        """A template used in the last 10 beats should be selected less often."""
        templates = [
            FallbackTemplate("t01", "prophet", "COUNTER", "Line one.", 1.0),
            FallbackTemplate("t02", "prophet", "COUNTER", "Line two.", 1.0),
        ]
        pool = FallbackPool(templates, min_per_archetype=0, min_per_move=0)

        # Run many selections with t01 always in recent beats (override)
        counts = {"t01": 0, "t02": 0}
        for _ in range(1000):
            sel = pool.select(
                "prophet",
                "COUNTER",
                recent_beat_ids=["t01"],
                session_used_ids=set(),
            )
            counts[sel.template_id] += 1

        # t02 should be selected significantly more often (it has full weight)
        # t01 has 50% reduction so t02:t01 should be roughly 2:1
        assert counts["t02"] > counts["t01"], (
            f"t02={counts['t02']}, t01={counts['t01']} — weight decay not working"
        )

    def test_session_used_reduces_weight_more(self):
        """A template used in this session should be selected much less often."""
        templates = [
            FallbackTemplate("t01", "prophet", "COUNTER", "Line one.", 1.0),
            FallbackTemplate("t02", "prophet", "COUNTER", "Line two.", 1.0),
        ]
        pool = FallbackPool(templates, min_per_archetype=0, min_per_move=0)

        # Run many selections with t01 always in session used (override)
        counts = {"t01": 0, "t02": 0}
        for _ in range(1000):
            sel = pool.select(
                "prophet",
                "COUNTER",
                recent_beat_ids=[],
                session_used_ids={"t01"},
            )
            counts[sel.template_id] += 1

        # t02 should dominate (roughly 5:1 ratio)
        assert counts["t02"] > counts["t01"] * 2, (
            f"t02={counts['t02']}, t01={counts['t01']} — session decay not working"
        )

    def test_reset_session_clears_state(self):
        """After reset_session(), weights should be back to normal."""
        templates = [
            FallbackTemplate("t01", "prophet", "COUNTER", "Line one.", 1.0),
            FallbackTemplate("t02", "prophet", "COUNTER", "Line two.", 1.0),
        ]
        pool = FallbackPool(templates, min_per_archetype=0, min_per_move=0)

        pool._session_used_ids.add("t01")
        pool._recent_beat_ids.append("t01")

        pool.reset_session()

        assert len(pool._session_used_ids) == 0
        assert len(pool._recent_beat_ids) == 0

    def test_excluded_ids_never_selected(self):
        """Templates in excluded_ids should never be selected."""
        templates = [
            FallbackTemplate("t01", "prophet", "COUNTER", "Line one.", 1.0),
            FallbackTemplate("t02", "prophet", "COUNTER", "Line two.", 1.0),
        ]
        pool = FallbackPool(templates, min_per_archetype=0, min_per_move=0)

        for _ in range(100):
            sel = pool.select("prophet", "COUNTER", excluded_ids={"t01"})
            assert sel.template_id == "t02"
