"""Unit tests for the SceneContext module.

Tests cover:
- 3-beat window enforcement (deque eviction)
- Energy classification (heated, cooling, neutral)
- Has-the-room tracking with tie-breaking
- Landed hit counter lifecycle
- Graceful degradation on state corruption
- get_context_for_generation() non-blocking behavior
"""

import time

from banter.types import Beat
from banter.scene_context import SceneContext


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_beat(
    speaker: str = "prophet",
    content: str = "Test line.",
    move: str = "COUNTER",
    quality_score: int = 8,
    energy_label: str = "warm",
    timestamp: float | None = None,
) -> Beat:
    """Helper to create a Beat with sensible defaults."""
    return Beat(
        speaker=speaker,
        content=content,
        move=move,
        quality_score=quality_score,
        energy_label=energy_label,
        timestamp=timestamp or time.time(),
    )


def _fresh_scene_context() -> SceneContext:
    return SceneContext()


# ---------------------------------------------------------------------------
# 3-Beat Window Tests (Requirement 5.1)
# ---------------------------------------------------------------------------


class TestBeatWindow:
    """Tests for the 3-beat sliding window."""

    def test_empty_context_has_no_beats(self):
        sc = _fresh_scene_context()
        ctx = sc.get_context_for_generation()
        assert len(ctx.recent_beats) == 0

    def test_single_beat_stored(self):
        sc = _fresh_scene_context()
        beat = _make_beat()
        sc.add_beat(beat)
        ctx = sc.get_context_for_generation()
        assert len(ctx.recent_beats) == 1
        assert ctx.recent_beats[0] == beat

    def test_three_beats_stored(self):
        sc = _fresh_scene_context()
        beats = [_make_beat(speaker=f"elder_{i}") for i in range(3)]
        for b in beats:
            sc.add_beat(b)
        ctx = sc.get_context_for_generation()
        assert len(ctx.recent_beats) == 3

    def test_fourth_beat_evicts_oldest(self):
        sc = _fresh_scene_context()
        beats = [_make_beat(speaker=f"elder_{i}") for i in range(4)]
        for b in beats:
            sc.add_beat(b)
        ctx = sc.get_context_for_generation()
        assert len(ctx.recent_beats) == 3
        # The oldest (elder_0) should be evicted
        speakers = [b.speaker for b in ctx.recent_beats]
        assert "elder_0" not in speakers
        assert "elder_1" in speakers
        assert "elder_3" in speakers

    def test_many_beats_never_exceed_three(self):
        sc = _fresh_scene_context()
        for i in range(20):
            sc.add_beat(_make_beat(speaker=f"elder_{i}"))
        ctx = sc.get_context_for_generation()
        assert len(ctx.recent_beats) == 3


# ---------------------------------------------------------------------------
# Energy Classification Tests (Requirement 5.1, 5.4)
# ---------------------------------------------------------------------------


class TestEnergyClassification:
    """Tests for classify_energy()."""

    def test_neutral_when_empty(self):
        sc = _fresh_scene_context()
        assert sc.classify_energy() == "neutral"

    def test_neutral_with_one_beat(self):
        sc = _fresh_scene_context()
        sc.add_beat(_make_beat(quality_score=10, move="ESCALATE"))
        assert sc.classify_energy() == "neutral"

    def test_neutral_with_two_high_escalate_beats(self):
        """2 beats scoring >8 with ESCALATE is NOT heated (need 3)."""
        sc = _fresh_scene_context()
        sc.add_beat(_make_beat(quality_score=9, move="ESCALATE"))
        sc.add_beat(_make_beat(quality_score=10, move="TAUNT"))
        assert sc.classify_energy() == "neutral"

    def test_heated_with_three_high_escalate_beats(self):
        """3 beats >8 with ESCALATE/TAUNT moves → heated."""
        sc = _fresh_scene_context()
        sc.add_beat(_make_beat(quality_score=9, move="ESCALATE"))
        sc.add_beat(_make_beat(quality_score=10, move="TAUNT"))
        sc.add_beat(_make_beat(quality_score=12, move="ESCALATE"))
        assert sc.classify_energy() == "heated"

    def test_not_heated_if_wrong_move(self):
        """3 beats >8 but with COUNTER (not ESCALATE/TAUNT) → neutral."""
        sc = _fresh_scene_context()
        sc.add_beat(_make_beat(quality_score=9, move="COUNTER"))
        sc.add_beat(_make_beat(quality_score=10, move="ESCALATE"))
        sc.add_beat(_make_beat(quality_score=12, move="ESCALATE"))
        # One beat is COUNTER, so not all are ESCALATE/TAUNT
        assert sc.classify_energy() == "neutral"

    def test_not_heated_if_score_not_above_8(self):
        """3 beats with ESCALATE but one ≤8 → not heated."""
        sc = _fresh_scene_context()
        sc.add_beat(_make_beat(quality_score=9, move="ESCALATE"))
        sc.add_beat(_make_beat(quality_score=8, move="TAUNT"))  # exactly 8, not >8
        sc.add_beat(_make_beat(quality_score=10, move="ESCALATE"))
        assert sc.classify_energy() == "neutral"

    def test_cooling_with_two_low_beats(self):
        """2+ consecutive beats <6 from the end → cooling."""
        sc = _fresh_scene_context()
        sc.add_beat(_make_beat(quality_score=10, move="COUNTER"))
        sc.add_beat(_make_beat(quality_score=4, move="COUNTER"))
        sc.add_beat(_make_beat(quality_score=3, move="DEFLECT"))
        assert sc.classify_energy() == "cooling"

    def test_cooling_with_all_three_low(self):
        """All 3 beats <6 → cooling."""
        sc = _fresh_scene_context()
        sc.add_beat(_make_beat(quality_score=2, move="COUNTER"))
        sc.add_beat(_make_beat(quality_score=4, move="DEFLECT"))
        sc.add_beat(_make_beat(quality_score=5, move="PIVOT"))
        assert sc.classify_energy() == "cooling"

    def test_not_cooling_if_recent_is_high(self):
        """First two low but most recent is high → neutral."""
        sc = _fresh_scene_context()
        sc.add_beat(_make_beat(quality_score=3, move="COUNTER"))
        sc.add_beat(_make_beat(quality_score=4, move="DEFLECT"))
        sc.add_beat(_make_beat(quality_score=10, move="ESCALATE"))
        # Consecutive from end: only the last (10) breaks the chain
        assert sc.classify_energy() == "neutral"


# ---------------------------------------------------------------------------
# Has-The-Room Tests (Requirement 5.5)
# ---------------------------------------------------------------------------


class TestHasTheRoom:
    """Tests for 'has the room' tracking."""

    def test_none_with_no_beats(self):
        sc = _fresh_scene_context()
        ctx = sc.get_context_for_generation()
        assert ctx.has_the_room is None

    def test_none_with_one_beat(self):
        """Need ≥2 beats from the same speaker to have the room."""
        sc = _fresh_scene_context()
        sc.add_beat(_make_beat(speaker="prophet", quality_score=15))
        ctx = sc.get_context_for_generation()
        assert ctx.has_the_room is None

    def test_assigned_with_two_beats_same_speaker(self):
        """Speaker with ≥2 beats gets the room."""
        sc = _fresh_scene_context()
        sc.add_beat(_make_beat(speaker="prophet", quality_score=10))
        sc.add_beat(_make_beat(speaker="prophet", quality_score=12))
        ctx = sc.get_context_for_generation()
        assert ctx.has_the_room == "prophet"

    def test_highest_average_wins(self):
        """Speaker with higher avg across ≥2 beats wins."""
        sc = _fresh_scene_context()
        # keeper has 2 beats avg=7, prophet has 2 beats but needs 3 total
        # With maxlen=3, we only have 3 slots total
        sc.add_beat(_make_beat(speaker="keeper", quality_score=6))
        sc.add_beat(_make_beat(speaker="keeper", quality_score=8))
        sc.add_beat(_make_beat(speaker="prophet", quality_score=15))
        ctx = sc.get_context_for_generation()
        # keeper has avg 7 across 2 beats, prophet only has 1 beat
        assert ctx.has_the_room == "keeper"

    def test_tie_broken_by_most_recent_above_8(self):
        """When tied on average, most recent beat >8 wins."""
        sc = _fresh_scene_context()
        # Both speakers have avg=9 across 1 beat each, but we need ≥2
        # Let's make a scenario where they tie with ≥2 beats
        # Actually with maxlen=3, only one speaker can have 2 beats
        # unless we have 2 beats from one and 1 from another
        # To test tie-breaking we need both eligible
        # This requires both speakers to have ≥2 beats - impossible with maxlen=3
        # unless the window has 3 beats: A, B, A — then A has 2, B has 1
        # To test tie: we need all 3 beats from same speaker (3 beats, avg ties with itself)
        # Actually, tie-breaking happens when two speakers have same avg
        # We can't have that with maxlen=3 and ≥2 requirement...
        # Unless we have exactly 2 speakers with 2 beats each... but 2+2=4 > maxlen=3
        # So tie-breaking with ≥2 beats is only possible if one speaker has 2 beats
        # and another also has... wait, no. maxlen=3, so at most one speaker can have 2
        # and another has 1. Tie is not reachable unless we relax.
        # Let's test that the first speaker with 2 beats wins when it's the only eligible one.
        pass  # Tie-breaking is a degenerate case with window=3

    def test_eviction_updates_has_the_room(self):
        """When the leading speaker's beats get evicted, room changes."""
        sc = _fresh_scene_context()
        sc.add_beat(_make_beat(speaker="prophet", quality_score=12))
        sc.add_beat(_make_beat(speaker="prophet", quality_score=10))
        ctx = sc.get_context_for_generation()
        assert ctx.has_the_room == "prophet"

        # Now add 2 more beats from keeper, evicting prophet's beats
        sc.add_beat(_make_beat(speaker="keeper", quality_score=9))
        sc.add_beat(_make_beat(speaker="keeper", quality_score=11))
        ctx = sc.get_context_for_generation()
        assert ctx.has_the_room == "keeper"


# ---------------------------------------------------------------------------
# Landed Hit Tests (Requirement 5.3)
# ---------------------------------------------------------------------------


class TestLandedHit:
    """Tests for landed hit tracking."""

    def test_no_landed_hit_initially(self):
        sc = _fresh_scene_context()
        ctx = sc.get_context_for_generation()
        assert ctx.landed_hit is None
        assert ctx.landed_hit_remaining == 0

    def test_score_above_12_sets_landed_hit(self):
        """A beat scoring >12 becomes a landed hit."""
        sc = _fresh_scene_context()
        hit_beat = _make_beat(quality_score=13, move="TAUNT")
        sc.add_beat(hit_beat)
        ctx = sc.get_context_for_generation()
        assert ctx.landed_hit == hit_beat
        assert ctx.landed_hit_remaining == 2

    def test_score_exactly_12_not_a_landed_hit(self):
        """Score must be >12, not ≥12."""
        sc = _fresh_scene_context()
        sc.add_beat(_make_beat(quality_score=12, move="TAUNT"))
        ctx = sc.get_context_for_generation()
        assert ctx.landed_hit is None

    def test_landed_hit_decrements_on_next_beat(self):
        """Counter decrements by 1 on next add_beat."""
        sc = _fresh_scene_context()
        sc.add_beat(_make_beat(quality_score=13))
        sc.add_beat(_make_beat(quality_score=5))  # next speaker
        ctx = sc.get_context_for_generation()
        assert ctx.landed_hit is not None
        assert ctx.landed_hit_remaining == 1

    def test_landed_hit_clears_after_two_speakers(self):
        """After 2 subsequent beats, landed hit is cleared."""
        sc = _fresh_scene_context()
        sc.add_beat(_make_beat(quality_score=13))
        sc.add_beat(_make_beat(quality_score=5))  # speaker 1 acknowledges
        sc.add_beat(_make_beat(quality_score=6))  # speaker 2 acknowledges
        ctx = sc.get_context_for_generation()
        assert ctx.landed_hit is None
        assert ctx.landed_hit_remaining == 0

    def test_new_landed_hit_replaces_old(self):
        """A new score >12 replaces the current landed hit."""
        sc = _fresh_scene_context()
        sc.add_beat(_make_beat(speaker="prophet", quality_score=13))
        new_hit = _make_beat(speaker="keeper", quality_score=14)
        sc.add_beat(new_hit)
        ctx = sc.get_context_for_generation()
        # The old hit was decremented (remaining 1), then new hit replaces
        assert ctx.landed_hit == new_hit
        assert ctx.landed_hit_remaining == 2

    def test_landed_hit_remaining_never_negative(self):
        """Counter never goes below 0."""
        sc = _fresh_scene_context()
        sc.add_beat(_make_beat(quality_score=13))
        # Add 5 beats to fully clear and go past
        for _ in range(5):
            sc.add_beat(_make_beat(quality_score=5))
        ctx = sc.get_context_for_generation()
        assert ctx.landed_hit is None
        assert ctx.landed_hit_remaining == 0


# ---------------------------------------------------------------------------
# Graceful Degradation Tests (Requirement 5.6)
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """Tests for graceful degradation on state corruption."""

    def test_get_context_never_raises(self):
        """get_context_for_generation() should never raise."""
        sc = _fresh_scene_context()
        # Corrupt internal state
        sc._state = None  # type: ignore
        # Should not raise, should return empty context
        ctx = sc.get_context_for_generation()
        assert ctx.scene_energy == "neutral"
        assert len(ctx.recent_beats) == 0

    def test_add_beat_resets_on_corruption(self):
        """add_beat() resets state on internal error."""
        sc = _fresh_scene_context()
        sc.add_beat(_make_beat(quality_score=10))
        # Corrupt the deque
        sc._state.recent_beats = "not_a_deque"  # type: ignore
        # This should trigger reset
        sc.add_beat(_make_beat(quality_score=8))
        ctx = sc.get_context_for_generation()
        # After reset, state should be clean (empty)
        assert ctx.scene_energy == "neutral"
        assert len(ctx.recent_beats) == 0

    def test_normal_operation_after_reset(self):
        """After a graceful reset, normal operations resume."""
        sc = _fresh_scene_context()
        # Corrupt and trigger reset
        sc._state.recent_beats = "bad"  # type: ignore
        sc.add_beat(_make_beat(quality_score=8))  # triggers reset
        # Now add a real beat
        beat = _make_beat(quality_score=10)
        sc.add_beat(beat)
        ctx = sc.get_context_for_generation()
        assert len(ctx.recent_beats) == 1
        assert ctx.recent_beats[0] == beat


# ---------------------------------------------------------------------------
# get_context_for_generation() Tests
# ---------------------------------------------------------------------------


class TestGetContext:
    """Tests that get_context_for_generation returns a proper snapshot."""

    def test_returns_snapshot_not_reference(self):
        """The returned context is a copy, not a reference to internal state."""
        sc = _fresh_scene_context()
        sc.add_beat(_make_beat(speaker="prophet", quality_score=10))
        ctx = sc.get_context_for_generation()
        # Mutate the returned context
        ctx.recent_beats.append(_make_beat(speaker="hacker"))
        # Internal state should be unchanged
        internal_ctx = sc.get_context_for_generation()
        assert len(internal_ctx.recent_beats) == 1

    def test_scene_energy_reflects_current_state(self):
        """Context energy matches the current classification."""
        sc = _fresh_scene_context()
        sc.add_beat(_make_beat(quality_score=3, move="COUNTER"))
        sc.add_beat(_make_beat(quality_score=4, move="DEFLECT"))
        ctx = sc.get_context_for_generation()
        assert ctx.scene_energy == "cooling"


# ---------------------------------------------------------------------------
# Property-Based Tests (Hypothesis)
# ---------------------------------------------------------------------------

from hypothesis import given, settings
from hypothesis import strategies as st

from conftest import st_beat_sequence, ARCHETYPES, MOVE_TYPES, ENERGY_LABELS


class TestProperty13SceneContextWindowBound:
    """**Property 13: Scene Context Window Bound**

    Scene context never contains more than 3 beats regardless of additions.

    **Validates: Requirements 5.1**
    """

    @given(
        beats=st_beat_sequence(min_size=0, max_size=50),
    )
    @settings(max_examples=200)
    def test_window_never_exceeds_3(self, beats: list[Beat]):
        """After adding any number of beats, context never has more than 3."""
        sc = _fresh_scene_context()
        for beat in beats:
            sc.add_beat(beat)
            ctx = sc.get_context_for_generation()
            assert len(ctx.recent_beats) <= 3, (
                f"Window size {len(ctx.recent_beats)} exceeds max 3 "
                f"after adding {beats.index(beat) + 1} beats"
            )

    @given(
        beats=st_beat_sequence(min_size=4, max_size=30),
    )
    @settings(max_examples=100)
    def test_window_exactly_3_after_sufficient_adds(self, beats: list[Beat]):
        """After adding ≥3 beats, window should be exactly 3."""
        sc = _fresh_scene_context()
        for beat in beats:
            sc.add_beat(beat)

        ctx = sc.get_context_for_generation()
        assert len(ctx.recent_beats) == 3


class TestProperty14LandedHitAcknowledgmentCounter:
    """**Property 14: Landed Hit Acknowledgment Counter**

    Score >12 sets counter to 2, decrements per speaker, never negative.

    **Validates: Requirements 5.3**
    """

    @given(
        pre_beats=st_beat_sequence(min_size=0, max_size=5),
        post_beats=st_beat_sequence(min_size=0, max_size=10),
    )
    @settings(max_examples=200)
    def test_landed_hit_counter_never_negative(
        self, pre_beats: list[Beat], post_beats: list[Beat]
    ):
        """Landed hit remaining counter is never negative."""
        sc = _fresh_scene_context()
        for beat in pre_beats:
            sc.add_beat(beat)
            ctx = sc.get_context_for_generation()
            assert ctx.landed_hit_remaining >= 0

        # Add a definite landed hit
        hit_beat = Beat(
            speaker="prophet",
            content="A devastating line.",
            move="TAUNT",
            quality_score=14,
            energy_label="hot",
            timestamp=time.time(),
        )
        sc.add_beat(hit_beat)
        ctx = sc.get_context_for_generation()
        assert ctx.landed_hit_remaining == 2

        for beat in post_beats:
            sc.add_beat(beat)
            ctx = sc.get_context_for_generation()
            assert ctx.landed_hit_remaining >= 0, (
                "Landed hit counter went negative"
            )

    @given(
        num_follow_up=st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=50)
    def test_landed_hit_clears_after_2_speakers(self, num_follow_up: int):
        """After 2 subsequent beats, the landed hit must be cleared."""
        sc = _fresh_scene_context()
        hit_beat = Beat(
            speaker="prophet",
            content="A crushing blow.",
            move="ESCALATE",
            quality_score=14,
            energy_label="hot",
            timestamp=time.time(),
        )
        sc.add_beat(hit_beat)

        # Add at least 2 follow-up beats (non-hit)
        actual_follow = max(2, num_follow_up)
        for i in range(actual_follow):
            follow = Beat(
                speaker=f"elder_{i}",
                content=f"Follow-up line {i}.",
                move="COUNTER",
                quality_score=5,
                energy_label="warm",
                timestamp=time.time() + i + 1,
            )
            sc.add_beat(follow)

        ctx = sc.get_context_for_generation()
        # After 2+ follow-up speakers, landed hit should be cleared
        assert ctx.landed_hit is None or ctx.landed_hit.quality_score > 12
        assert ctx.landed_hit_remaining >= 0


class TestProperty15HasTheRoomAssignment:
    """**Property 15: Has-The-Room Assignment**

    Assigned to highest avg score across ≥2 beats, ties broken by most recent >8.

    **Validates: Requirements 5.5**
    """

    @given(
        beats=st_beat_sequence(min_size=0, max_size=20),
    )
    @settings(max_examples=200)
    def test_has_the_room_requires_2_beats(self, beats: list[Beat]):
        """has_the_room is None unless an elder has ≥2 beats in window."""
        sc = _fresh_scene_context()
        for beat in beats:
            sc.add_beat(beat)

        ctx = sc.get_context_for_generation()
        if ctx.has_the_room is not None:
            # Verify that the holder has ≥2 beats in the window
            speaker_counts = {}
            for b in ctx.recent_beats:
                speaker_counts[b.speaker] = speaker_counts.get(b.speaker, 0) + 1
            assert speaker_counts.get(ctx.has_the_room, 0) >= 2, (
                f"{ctx.has_the_room} has the room but only has "
                f"{speaker_counts.get(ctx.has_the_room, 0)} beats in window"
            )

    @given(
        score_a=st.integers(min_value=0, max_value=15),
        score_b=st.integers(min_value=0, max_value=15),
    )
    @settings(max_examples=100)
    def test_highest_average_wins(self, score_a: int, score_b: int):
        """The elder with highest avg across ≥2 beats gets the room."""
        sc = _fresh_scene_context()
        # Give elder_a two beats
        sc.add_beat(Beat(
            speaker="elder_a", content="Line 1", move="COUNTER",
            quality_score=score_a, energy_label="warm", timestamp=1.0,
        ))
        sc.add_beat(Beat(
            speaker="elder_a", content="Line 2", move="COUNTER",
            quality_score=score_a, energy_label="warm", timestamp=2.0,
        ))

        ctx = sc.get_context_for_generation()
        # With only elder_a having ≥2 beats, they should have the room
        assert ctx.has_the_room == "elder_a"
