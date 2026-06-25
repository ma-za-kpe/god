"""Unit tests for CallbackRegistry — Requirements 4.1-4.6, 5.1-5.6, 9.1-9.6.

Tests cover the pure-Python behaviours that do not require a real database:
- compute_pair_id determinism and commutativity
- _score_moment_match: tension mismatch reject, theme/valence scoring
- _infer_tension_from_moment: score+valence → tension mapping
- _themes_overlap: exact, containment, commutativity
- _valence_matches_tension: documented rules
- _select_framing: framing selection logic
- _moment_callback_id: stability for same data
- WriteBuffer: buffering when DB unavailable (pool=None → store_memorable_moment)
- Session limit enforcement (CallbackUsageTracker)
- Score threshold (score <= 12 skips storage)
- surface_callback with pool=None returns None (no moments available)
- get_sore_spots with pool=None returns []
"""

import asyncio
import os
import sys

_src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
for _p in (_src_path, "/app/src"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest

from banter.callback_registry import (
    CallbackRegistry,
    _MAX_CALLBACKS_PER_PAIR_PER_SESSION,
    _MAX_GAGS_PER_PAIR,
    _MAX_MOMENTS_PER_PAIR,
    _MIN_BEAT_GAP,
    _TENSION_MISMATCH_REJECT,
)
from banter.soul_types import (
    CallbackUsageTracker,
    MemorableMoment,
    SoulEngineConfig,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config() -> SoulEngineConfig:
    return SoulEngineConfig()


@pytest.fixture
def registry(config: SoulEngineConfig) -> CallbackRegistry:
    return CallbackRegistry(pool=None, config=config)


def _moment(
    speaker: str = "alpha",
    target: str = "beta",
    score: int = 14,
    valence: str = "negative",
    arc_theme: str = "power",
    beat_number: int = 10,
    line: str = "A memorable line.",
) -> MemorableMoment:
    return MemorableMoment(
        speaker=speaker,
        target=target,
        line=line,
        move="TAUNT",
        arc_theme=arc_theme,
        valence=valence,
        summary=f"Summary for {speaker}",
        score=score,
        beat_number=beat_number,
        created_at=1_000_000.0 + beat_number,
    )


# ---------------------------------------------------------------------------
# compute_pair_id
# ---------------------------------------------------------------------------


class TestComputePairId:
    """Requirements 9.4: pair_id is commutative, stable, 16 hex chars."""

    def test_commutativity(self, registry: CallbackRegistry) -> None:
        assert registry.compute_pair_id("alpha", "beta") == registry.compute_pair_id(
            "beta", "alpha"
        )

    def test_same_input_same_output(self, registry: CallbackRegistry) -> None:
        r1 = registry.compute_pair_id("prophet", "keeper")
        r2 = registry.compute_pair_id("prophet", "keeper")
        assert r1 == r2

    def test_output_is_16_hex_chars(self, registry: CallbackRegistry) -> None:
        pid = registry.compute_pair_id("alpha", "beta")
        assert len(pid) == 16
        assert all(c in "0123456789abcdef" for c in pid)

    def test_distinct_pairs_produce_distinct_ids(self, registry: CallbackRegistry) -> None:
        ids = {
            registry.compute_pair_id("a", "b"),
            registry.compute_pair_id("a", "c"),
            registry.compute_pair_id("b", "c"),
        }
        assert len(ids) == 3

    def test_self_pair_is_stable(self, registry: CallbackRegistry) -> None:
        pid = registry.compute_pair_id("solo", "solo")
        assert len(pid) == 16


# ---------------------------------------------------------------------------
# _infer_tension_from_moment
# ---------------------------------------------------------------------------


class TestInferTensionFromMoment:
    """_infer_tension_from_moment maps score+valence to tension [2, 8]."""

    def test_high_score_negative_valence_returns_high_tension(
        self, registry: CallbackRegistry
    ) -> None:
        m = _moment(score=15, valence="negative")
        assert registry._infer_tension_from_moment(m) == 8

    def test_medium_score_negative_valence(self, registry: CallbackRegistry) -> None:
        m = _moment(score=13, valence="negative")
        assert registry._infer_tension_from_moment(m) == 6

    def test_low_score_negative_valence(self, registry: CallbackRegistry) -> None:
        m = _moment(score=12, valence="negative")
        assert registry._infer_tension_from_moment(m) == 5

    def test_high_score_positive_valence(self, registry: CallbackRegistry) -> None:
        m = _moment(score=15, valence="positive")
        assert registry._infer_tension_from_moment(m) == 4

    def test_medium_score_positive_valence(self, registry: CallbackRegistry) -> None:
        m = _moment(score=13, valence="positive")
        assert registry._infer_tension_from_moment(m) == 3

    def test_low_score_positive_valence(self, registry: CallbackRegistry) -> None:
        m = _moment(score=12, valence="positive")
        assert registry._infer_tension_from_moment(m) == 2

    def test_neutral_valence_returns_5(self, registry: CallbackRegistry) -> None:
        for score in [12, 13, 15, 18]:
            m = _moment(score=score, valence="neutral")
            assert registry._infer_tension_from_moment(m) == 5

    def test_result_always_in_2_to_8(self, registry: CallbackRegistry) -> None:
        for valence in ["positive", "negative", "neutral"]:
            for score in range(10, 20):
                m = _moment(score=score, valence=valence)
                inferred = registry._infer_tension_from_moment(m)
                assert 2 <= inferred <= 8, (
                    f"Out of range: {inferred} for score={score}, valence={valence}"
                )


# ---------------------------------------------------------------------------
# _themes_overlap
# ---------------------------------------------------------------------------


class TestThemesOverlap:
    """_themes_overlap: exact match, containment, commutativity, empty handling."""

    def test_exact_match(self, registry: CallbackRegistry) -> None:
        assert registry._themes_overlap("power", "power") is True

    def test_substring_a_in_b(self, registry: CallbackRegistry) -> None:
        assert registry._themes_overlap("power", "power struggle") is True

    def test_substring_b_in_a(self, registry: CallbackRegistry) -> None:
        assert registry._themes_overlap("power struggle", "power") is True

    def test_no_overlap(self, registry: CallbackRegistry) -> None:
        assert registry._themes_overlap("betrayal", "redemption") is False

    def test_commutativity(self, registry: CallbackRegistry) -> None:
        pairs = [("power", "power struggle"), ("x", "y"), ("abc", "abc def")]
        for a, b in pairs:
            assert registry._themes_overlap(a, b) == registry._themes_overlap(b, a)

    def test_empty_string_returns_false(self, registry: CallbackRegistry) -> None:
        assert registry._themes_overlap("", "power") is False
        assert registry._themes_overlap("power", "") is False
        assert registry._themes_overlap("", "") is False

    def test_case_insensitive(self, registry: CallbackRegistry) -> None:
        assert registry._themes_overlap("Power", "power") is True
        assert registry._themes_overlap("BETRAYAL", "betrayal and redemption") is True


# ---------------------------------------------------------------------------
# _valence_matches_tension
# ---------------------------------------------------------------------------


class TestValenceMatchesTension:
    """_valence_matches_tension: documented rules for all valences."""

    def test_negative_matches_high_tension(self, registry: CallbackRegistry) -> None:
        for t in [6, 7, 8, 9, 10]:
            assert registry._valence_matches_tension("negative", t) is True

    def test_negative_does_not_match_low_tension(self, registry: CallbackRegistry) -> None:
        for t in [0, 1, 2, 3, 4, 5]:
            assert registry._valence_matches_tension("negative", t) is False

    def test_positive_matches_low_tension(self, registry: CallbackRegistry) -> None:
        for t in [0, 1, 2, 3, 4]:
            assert registry._valence_matches_tension("positive", t) is True

    def test_positive_does_not_match_high_tension(self, registry: CallbackRegistry) -> None:
        for t in [5, 6, 7, 8, 9, 10]:
            assert registry._valence_matches_tension("positive", t) is False

    def test_neutral_matches_medium_tension(self, registry: CallbackRegistry) -> None:
        for t in [3, 4, 5, 6, 7]:
            assert registry._valence_matches_tension("neutral", t) is True

    def test_neutral_does_not_match_extremes(self, registry: CallbackRegistry) -> None:
        for t in [0, 1, 2, 8, 9, 10]:
            assert registry._valence_matches_tension("neutral", t) is False


# ---------------------------------------------------------------------------
# _score_moment_match
# ---------------------------------------------------------------------------


class TestScoreMomentMatch:
    """_score_moment_match: 0-3 range, hard reject on large tension mismatch."""

    def test_exact_tension_and_theme_scores_high(self, registry: CallbackRegistry) -> None:
        m = _moment(score=15, valence="negative", arc_theme="power")
        # inferred tension = 8; current=8; diff=0 → tension +1; same theme +1; negative at 8 → +1
        score = registry._score_moment_match(m, 8, "power")
        assert score == 3

    def test_hard_reject_on_large_tension_mismatch(self, registry: CallbackRegistry) -> None:
        m = _moment(score=15, valence="negative", arc_theme="power")  # inferred = 8
        # tension mismatch > 3: current=0, diff=8 → hard reject
        score = registry._score_moment_match(m, 0, "power")
        assert score == 0

    def test_hard_reject_boundary_above_threshold(self, registry: CallbackRegistry) -> None:
        m = _moment(score=13, valence="negative", arc_theme="power")  # inferred = 6
        # mismatch = 4 > 3 → reject
        score = registry._score_moment_match(m, 10, "power")
        assert score == 0

    def test_within_threshold_scores_positively(self, registry: CallbackRegistry) -> None:
        m = _moment(score=13, valence="negative", arc_theme="betrayal")  # inferred = 6
        # tension=7, diff=1 → tension +1
        score = registry._score_moment_match(m, 7, "betrayal")
        assert score >= 1

    def test_theme_mismatch_reduces_score(self, registry: CallbackRegistry) -> None:
        m = _moment(score=13, valence="negative", arc_theme="power")  # inferred = 6
        with_theme = registry._score_moment_match(m, 6, "power")
        without_theme = registry._score_moment_match(m, 6, "zzz_no_overlap")
        assert with_theme >= without_theme

    def test_score_always_in_0_to_3(self, registry: CallbackRegistry) -> None:
        cases = [
            (14, "negative", "power", 6),
            (15, "positive", "redemption", 3),
            (12, "neutral", "sacrifice", 5),
            (18, "negative", "betrayal", 9),
            (13, "positive", "loyalty", 0),
        ]
        for score, valence, theme, tension in cases:
            m = _moment(score=score, valence=valence, arc_theme=theme)
            result = registry._score_moment_match(m, tension, theme)
            assert 0 <= result <= 3, f"Score {result} out of range for {cases}"


# ---------------------------------------------------------------------------
# _select_framing
# ---------------------------------------------------------------------------


class TestSelectFraming:
    """_select_framing produces one of the four documented framing types."""

    VALID_FRAMINGS = {"direct_quote", "paraphrase", "inversion", "escalation"}

    def test_high_tension_returns_direct_quote(self, registry: CallbackRegistry) -> None:
        m = _moment(score=14, valence="negative")  # inferred tension = 6
        # current=7, not inversion (negative at 7 is not 'positive at high'), not escalation
        framing = registry._select_framing(7, m)
        assert framing == "direct_quote"

    def test_medium_tension_returns_paraphrase(self, registry: CallbackRegistry) -> None:
        m = _moment(score=14, valence="negative")  # inferred = 6
        # current=5, no inversion, current <= original+1 → paraphrase
        framing = registry._select_framing(5, m)
        assert framing == "paraphrase"

    def test_inversion_for_positive_moment_at_high_tension(
        self, registry: CallbackRegistry
    ) -> None:
        m = _moment(score=15, valence="positive")  # inferred = 4
        # positive moment at tension 7 → inversion
        framing = registry._select_framing(7, m)
        assert framing == "inversion"

    def test_inversion_for_negative_moment_at_low_tension(self, registry: CallbackRegistry) -> None:
        m = _moment(score=15, valence="negative")  # inferred = 8
        # negative moment at tension 3 → inversion
        framing = registry._select_framing(3, m)
        assert framing == "inversion"

    def test_escalation_when_tension_exceeds_original(self, registry: CallbackRegistry) -> None:
        m = _moment(score=13, valence="neutral")  # inferred = 5
        # current=8 > 5+1=6 → escalation (no inversion for neutral)
        framing = registry._select_framing(8, m)
        assert framing == "escalation"

    def test_result_always_in_valid_framings(self, registry: CallbackRegistry) -> None:
        for valence in ["positive", "negative", "neutral"]:
            for score in [13, 14, 15]:
                for tension in [0, 3, 5, 7, 9]:
                    m = _moment(score=score, valence=valence)
                    framing = registry._select_framing(tension, m)
                    assert framing in self.VALID_FRAMINGS


# ---------------------------------------------------------------------------
# _moment_callback_id
# ---------------------------------------------------------------------------


class TestMomentCallbackId:
    """_moment_callback_id produces a stable 12-char hex ID for a moment."""

    def test_stable_for_same_data(self, registry: CallbackRegistry) -> None:
        m = _moment(line="Test line")
        id1 = registry._moment_callback_id(m)
        id2 = registry._moment_callback_id(m)
        assert id1 == id2

    def test_different_content_different_id(self, registry: CallbackRegistry) -> None:
        m1 = _moment(line="Line A")
        m2 = _moment(line="Line B")
        assert registry._moment_callback_id(m1) != registry._moment_callback_id(m2)

    def test_id_is_12_hex_chars(self, registry: CallbackRegistry) -> None:
        cb_id = registry._moment_callback_id(_moment())
        assert len(cb_id) == 12
        assert all(c in "0123456789abcdef" for c in cb_id)


# ---------------------------------------------------------------------------
# WriteBuffer / DB unavailability
# ---------------------------------------------------------------------------


def _make_no_pool_registry() -> CallbackRegistry:
    """Create a CallbackRegistry where _get_pool always returns None (DB forced offline)."""
    config = SoulEngineConfig()
    reg = CallbackRegistry(pool=None, config=config)

    async def _always_none():
        return None

    reg._get_pool = _always_none  # type: ignore[method-assign]
    return reg


class TestWriteBufferBehavior:
    """Requirements 9.6: DB unavailability routes to WriteBuffer."""

    def test_store_below_threshold_does_not_buffer(self) -> None:
        reg = _make_no_pool_registry()
        asyncio.run(
            reg.store_memorable_moment(
                speaker="alpha",
                target="beta",
                line="Low score line.",
                move="COUNTER",
                arc_theme="power",
                valence="negative",
                summary="Low score",
                score=12,  # <= 12 threshold → not stored
            )
        )
        assert len(reg._write_buffer.entries) == 0

    def test_store_above_threshold_buffers_when_no_pool(self) -> None:
        reg = _make_no_pool_registry()
        asyncio.run(
            reg.store_memorable_moment(
                speaker="alpha",
                target="beta",
                line="High score line.",
                move="COUNTER",
                arc_theme="power",
                valence="negative",
                summary="High score",
                score=13,  # > 12 → buffers
            )
        )
        assert len(reg._write_buffer.entries) == 1

    def test_buffer_accumulates_multiple_stores(self) -> None:
        reg = _make_no_pool_registry()
        for i in range(5):
            asyncio.run(
                reg.store_memorable_moment(
                    speaker="alpha",
                    target="beta",
                    line=f"Line {i}",
                    move="TAUNT",
                    arc_theme="survival",
                    valence="negative",
                    summary=f"Summary {i}",
                    score=14,
                )
            )
        assert len(reg._write_buffer.entries) == 5

    def test_buffer_caps_at_20_entries(self) -> None:
        reg = _make_no_pool_registry()
        for i in range(30):
            asyncio.run(
                reg.store_memorable_moment(
                    speaker="alpha",
                    target="beta",
                    line=f"Line {i}",
                    move="COUNTER",
                    arc_theme="power",
                    valence="negative",
                    summary=f"Summary {i}",
                    score=14,
                )
            )
        assert len(reg._write_buffer.entries) <= 20

    def test_buffer_retains_most_recent_on_overflow(self) -> None:
        reg = _make_no_pool_registry()
        lines = [f"Line number {i}" for i in range(25)]
        for i, line in enumerate(lines):
            asyncio.run(
                reg.store_memorable_moment(
                    speaker="alpha",
                    target="beta",
                    line=line,
                    move="TAUNT",
                    arc_theme="power",
                    valence="negative",
                    summary="S",
                    score=14,
                )
            )
        stored_lines = [m.line for m in list(reg._write_buffer.entries)]
        assert stored_lines == lines[-20:]

    def test_score_12_exact_not_stored(self) -> None:
        reg = _make_no_pool_registry()
        asyncio.run(
            reg.store_memorable_moment(
                speaker="alpha",
                target="beta",
                line="Exact threshold.",
                move="COUNTER",
                arc_theme="power",
                valence="negative",
                summary="Boundary",
                score=12,
            )
        )
        assert len(reg._write_buffer.entries) == 0

    def test_score_13_stored(self) -> None:
        reg = _make_no_pool_registry()
        asyncio.run(
            reg.store_memorable_moment(
                speaker="alpha",
                target="beta",
                line="Just above threshold.",
                move="COUNTER",
                arc_theme="power",
                valence="negative",
                summary="Above",
                score=13,
            )
        )
        assert len(reg._write_buffer.entries) == 1


# ---------------------------------------------------------------------------
# surface_callback with no pool
# ---------------------------------------------------------------------------


class TestSurfaceCallbackNoPool:
    """surface_callback returns None when no DB pool is available."""

    def test_no_pool_returns_none(self) -> None:
        reg = _make_no_pool_registry()
        result = asyncio.run(
            reg.surface_callback(
                speaker="alpha",
                target="beta",
                current_tension=6,
                current_arc_theme="power",
                current_beat_number=20,
                session_callback_count=0,
            )
        )
        assert result is None

    def test_session_limit_returns_none_immediately(self, registry: CallbackRegistry) -> None:
        """Session limit is checked before DB query — pool doesn't matter."""
        result = asyncio.run(
            registry.surface_callback(
                speaker="alpha",
                target="beta",
                current_tension=6,
                current_arc_theme="power",
                current_beat_number=20,
                session_callback_count=_MAX_CALLBACKS_PER_PAIR_PER_SESSION,
            )
        )
        assert result is None

    def test_get_sore_spots_returns_empty_without_pool(self) -> None:
        reg = _make_no_pool_registry()
        result = asyncio.run(reg.get_sore_spots("keeper", "legacy"))
        assert result == []


# ---------------------------------------------------------------------------
# Session limit enforcement
# ---------------------------------------------------------------------------


class TestSessionLimitEnforcement:
    """Requirements 5.3: Max 2 callbacks per pair per session."""

    def test_session_limit_constant_is_2(self) -> None:
        assert _MAX_CALLBACKS_PER_PAIR_PER_SESSION == 2

    def test_tracker_blocks_at_2(self, registry: CallbackRegistry) -> None:
        pair_id = registry.compute_pair_id("alpha", "beta")
        tracker = CallbackUsageTracker()
        tracker.pair_session_count[pair_id] = 2
        blocked = tracker.pair_session_count.get(pair_id, 0) >= _MAX_CALLBACKS_PER_PAIR_PER_SESSION
        assert blocked is True

    def test_tracker_allows_at_1(self, registry: CallbackRegistry) -> None:
        pair_id = registry.compute_pair_id("alpha", "beta")
        tracker = CallbackUsageTracker()
        tracker.pair_session_count[pair_id] = 1
        blocked = tracker.pair_session_count.get(pair_id, 0) >= _MAX_CALLBACKS_PER_PAIR_PER_SESSION
        assert blocked is False

    def test_tracker_allows_at_0(self, registry: CallbackRegistry) -> None:
        pair_id = registry.compute_pair_id("alpha", "beta")
        tracker = CallbackUsageTracker()
        blocked = tracker.pair_session_count.get(pair_id, 0) >= _MAX_CALLBACKS_PER_PAIR_PER_SESSION
        assert blocked is False

    def test_internal_tracker_blocks_surface_callback(self, registry: CallbackRegistry) -> None:
        pair_id = registry.compute_pair_id("alpha", "beta")
        registry._usage_tracker.pair_session_count[pair_id] = _MAX_CALLBACKS_PER_PAIR_PER_SESSION
        result = asyncio.run(
            registry.surface_callback(
                speaker="alpha",
                target="beta",
                current_tension=6,
                current_arc_theme="power",
                current_beat_number=20,
                session_callback_count=0,
            )
        )
        assert result is None


# ---------------------------------------------------------------------------
# Timing constraint constants
# ---------------------------------------------------------------------------


class TestTimingConstants:
    """Verify the timing constraint constants match the spec."""

    def test_min_beat_gap_is_15(self) -> None:
        assert _MIN_BEAT_GAP == 15

    def test_tension_mismatch_reject_is_3(self) -> None:
        assert _TENSION_MISMATCH_REJECT == 3

    def test_max_moments_per_pair_is_50(self) -> None:
        assert _MAX_MOMENTS_PER_PAIR == 50

    def test_max_gags_per_pair_is_10(self) -> None:
        assert _MAX_GAGS_PER_PAIR == 10

    def test_registry_initialises_with_empty_buffer(self, registry: CallbackRegistry) -> None:
        assert len(registry._write_buffer.entries) == 0

    def test_registry_initialises_with_empty_tracker(self, registry: CallbackRegistry) -> None:
        assert len(registry._usage_tracker.last_used_beat) == 0
        assert len(registry._usage_tracker.pair_session_count) == 0
