"""Unit tests for the Pacing Controller module.

Tests the priority-based delay computation, rule resolution,
CONCEDE pre-delivery pause, and final clamping.
"""

import pytest

from banter.pacing_controller import PacingController
from banter.types import PacingDecision


@pytest.fixture
def controller() -> PacingController:
    """Return a fresh PacingController instance."""
    return PacingController()


# ---------------------------------------------------------------------------
# Basic rule tests
# ---------------------------------------------------------------------------


class TestLandedHitRule:
    """Tests for the landed-hit pacing rule (3.0-5.0s)."""

    def test_landed_hit_applies_fixed_delay(self, controller: PacingController):
        """Landed hit produces a delay within [3.0, 5.0]."""
        result = controller.compute_delay(
            previous_score=13,
            upcoming_move="COUNTER",
            scene_energy="neutral",
            landed_hit=True,
        )
        assert 3.0 <= result.inter_beat_delay_s <= 5.0
        assert result.rule_applied == "landed_hit"

    def test_landed_hit_overrides_heated(self, controller: PacingController):
        """Landed hit takes precedence over heated (4.0 > 2.0)."""
        result = controller.compute_delay(
            previous_score=13,
            upcoming_move="ESCALATE",
            scene_energy="heated",
            landed_hit=True,
        )
        # Landed hit delay (4.0) > heated delay (2.0), so landed_hit wins
        assert result.rule_applied == "landed_hit"
        assert result.inter_beat_delay_s == 4.0


class TestHeatedSceneRule:
    """Tests for the heated-scene pacing rule (1.5-2.5s)."""

    def test_heated_scene_produces_short_delay(self, controller: PacingController):
        """Heated scene reduces delay to [1.5, 2.5]."""
        result = controller.compute_delay(
            previous_score=9,
            upcoming_move="ESCALATE",
            scene_energy="heated",
            landed_hit=False,
        )
        assert 1.5 <= result.inter_beat_delay_s <= 2.5
        assert result.rule_applied == "heated"

    def test_heated_scene_fixed_at_2_0(self, controller: PacingController):
        """Heated scene uses 2.0s fixed delay."""
        result = controller.compute_delay(
            previous_score=8,
            upcoming_move="TAUNT",
            scene_energy="heated",
            landed_hit=False,
        )
        assert result.inter_beat_delay_s == 2.0


class TestCoolingSceneRule:
    """Tests for the cooling-scene pacing rule (5.0-8.0s)."""

    def test_cooling_scene_produces_long_delay(self, controller: PacingController):
        """Cooling scene increases delay to [5.0, 8.0]."""
        result = controller.compute_delay(
            previous_score=4,
            upcoming_move="PIVOT",
            scene_energy="cooling",
            landed_hit=False,
        )
        assert 5.0 <= result.inter_beat_delay_s <= 8.0
        assert result.rule_applied == "cooling"

    def test_cooling_scene_fixed_at_6_5(self, controller: PacingController):
        """Cooling scene uses 6.5s fixed delay."""
        result = controller.compute_delay(
            previous_score=3,
            upcoming_move="DEFLECT",
            scene_energy="cooling",
            landed_hit=False,
        )
        assert result.inter_beat_delay_s == 6.5


class TestDefaultRule:
    """Tests for the default pacing rule (3.0-5.0s with adjustments)."""

    def test_default_rule_when_neutral_no_landed_hit(self, controller: PacingController):
        """Default rule applies when scene is neutral and no landed hit."""
        result = controller.compute_delay(
            previous_score=8,
            upcoming_move="COUNTER",
            scene_energy="neutral",
            landed_hit=False,
        )
        assert result.rule_applied == "default"
        assert 3.0 <= result.inter_beat_delay_s <= 5.0

    def test_default_scales_with_score_low(self, controller: PacingController):
        """Score 0 produces delay near 3.0."""
        result = controller.compute_delay(
            previous_score=0,
            upcoming_move="COUNTER",
            scene_energy="neutral",
            landed_hit=False,
        )
        assert result.inter_beat_delay_s == pytest.approx(3.0, abs=0.01)

    def test_default_scales_with_score_high(self, controller: PacingController):
        """Score 15 produces delay near 5.0."""
        result = controller.compute_delay(
            previous_score=15,
            upcoming_move="COUNTER",
            scene_energy="neutral",
            landed_hit=False,
        )
        assert result.inter_beat_delay_s == pytest.approx(5.0, abs=0.01)

    def test_escalate_adjustment_reduces_delay(self, controller: PacingController):
        """ESCALATE upcoming move reduces delay by 0.5s."""
        base = controller.compute_delay(
            previous_score=8,
            upcoming_move="COUNTER",
            scene_energy="neutral",
            landed_hit=False,
        )
        adjusted = controller.compute_delay(
            previous_score=8,
            upcoming_move="ESCALATE",
            scene_energy="neutral",
            landed_hit=False,
        )
        assert adjusted.inter_beat_delay_s == pytest.approx(base.inter_beat_delay_s - 0.5, abs=0.01)

    def test_taunt_adjustment_reduces_delay(self, controller: PacingController):
        """TAUNT upcoming move reduces delay by 0.5s."""
        base = controller.compute_delay(
            previous_score=8,
            upcoming_move="COUNTER",
            scene_energy="neutral",
            landed_hit=False,
        )
        adjusted = controller.compute_delay(
            previous_score=8,
            upcoming_move="TAUNT",
            scene_energy="neutral",
            landed_hit=False,
        )
        assert adjusted.inter_beat_delay_s == pytest.approx(base.inter_beat_delay_s - 0.5, abs=0.01)

    def test_concede_adjustment_increases_delay(self, controller: PacingController):
        """CONCEDE upcoming move increases delay by 0.5s."""
        base = controller.compute_delay(
            previous_score=8,
            upcoming_move="COUNTER",
            scene_energy="neutral",
            landed_hit=False,
        )
        adjusted = controller.compute_delay(
            previous_score=8,
            upcoming_move="CONCEDE",
            scene_energy="neutral",
            landed_hit=False,
        )
        assert adjusted.inter_beat_delay_s == pytest.approx(base.inter_beat_delay_s + 0.5, abs=0.01)

    def test_pivot_adjustment_increases_delay(self, controller: PacingController):
        """PIVOT upcoming move increases delay by 0.5s."""
        base = controller.compute_delay(
            previous_score=8,
            upcoming_move="COUNTER",
            scene_energy="neutral",
            landed_hit=False,
        )
        adjusted = controller.compute_delay(
            previous_score=8,
            upcoming_move="PIVOT",
            scene_energy="neutral",
            landed_hit=False,
        )
        assert adjusted.inter_beat_delay_s == pytest.approx(base.inter_beat_delay_s + 0.5, abs=0.01)


# ---------------------------------------------------------------------------
# Conflict resolution tests
# ---------------------------------------------------------------------------


class TestConflictResolution:
    """Tests for longest-delay-wins conflict resolution."""

    def test_landed_hit_beats_heated(self, controller: PacingController):
        """When landed_hit AND heated, landed_hit wins (4.0 > 2.0)."""
        result = controller.compute_delay(
            previous_score=13,
            upcoming_move="COUNTER",
            scene_energy="heated",
            landed_hit=True,
        )
        assert result.rule_applied == "landed_hit"
        assert result.inter_beat_delay_s == 4.0

    def test_cooling_beats_landed_hit(self, controller: PacingController):
        """When landed_hit AND cooling, cooling wins (6.5 > 4.0)."""
        result = controller.compute_delay(
            previous_score=13,
            upcoming_move="COUNTER",
            scene_energy="cooling",
            landed_hit=True,
        )
        assert result.rule_applied == "cooling"
        assert result.inter_beat_delay_s == 6.5

    def test_cooling_beats_heated_impossible_but_hypothetical(self, controller: PacingController):
        """Cooling delay (6.5) would beat heated delay (2.0) if both applied.

        Note: in practice a scene can't be both heated and cooling,
        but the rule resolution is longest wins regardless.
        """
        # This scenario won't happen in practice (scene_energy is one value)
        # but we test the explicit rule set when landed_hit is combined with cooling
        result = controller.compute_delay(
            previous_score=4,
            upcoming_move="COUNTER",
            scene_energy="cooling",
            landed_hit=True,
        )
        assert result.rule_applied == "cooling"


# ---------------------------------------------------------------------------
# CONCEDE pre-delivery pause tests
# ---------------------------------------------------------------------------


class TestConcedePreDeliveryPause:
    """Tests for the CONCEDE +2.0s additive pre-delivery pause."""

    def test_concede_adds_pre_delivery_pause(self, controller: PacingController):
        """CONCEDE move always gets 2.0s pre-delivery pause."""
        result = controller.compute_delay(
            previous_score=8,
            upcoming_move="CONCEDE",
            scene_energy="neutral",
            landed_hit=False,
        )
        assert result.pre_delivery_pause_s == 2.0

    def test_non_concede_no_pre_delivery_pause(self, controller: PacingController):
        """Non-CONCEDE moves get 0.0s pre-delivery pause."""
        for move in ["COUNTER", "ESCALATE", "DEFLECT", "TAUNT", "QUESTION", "PIVOT", "CALLBACK"]:
            result = controller.compute_delay(
                previous_score=8,
                upcoming_move=move,
                scene_energy="neutral",
                landed_hit=False,
            )
            assert result.pre_delivery_pause_s == 0.0, f"Expected 0.0 for {move}"

    def test_concede_pause_independent_of_rule(self, controller: PacingController):
        """CONCEDE pre-delivery pause applies regardless of which rule won."""
        # Heated scene + CONCEDE
        result = controller.compute_delay(
            previous_score=9,
            upcoming_move="CONCEDE",
            scene_energy="heated",
            landed_hit=False,
        )
        assert result.pre_delivery_pause_s == 2.0
        assert result.rule_applied == "heated"

        # Landed hit + CONCEDE
        result = controller.compute_delay(
            previous_score=13,
            upcoming_move="CONCEDE",
            scene_energy="neutral",
            landed_hit=True,
        )
        assert result.pre_delivery_pause_s == 2.0
        assert result.rule_applied == "landed_hit"


# ---------------------------------------------------------------------------
# Final clamping tests
# ---------------------------------------------------------------------------


class TestFinalClamping:
    """Tests for [1.0, 10.0] clamping."""

    def test_delay_never_below_minimum(self, controller: PacingController):
        """Inter-beat delay is always >= 1.0."""
        # Heated scene with ESCALATE adjustment (would be 2.0 - 0.5 = 1.5,
        # but heated scene rule doesn't use move adjustments since it's
        # a fixed value. The minimum can only be reached if somehow a
        # computation goes below 1.0, which we test defensively.)
        result = controller.compute_delay(
            previous_score=0,
            upcoming_move="ESCALATE",
            scene_energy="heated",
            landed_hit=False,
        )
        assert result.inter_beat_delay_s >= 1.0

    def test_delay_never_above_maximum(self, controller: PacingController):
        """Inter-beat delay is always <= 10.0."""
        result = controller.compute_delay(
            previous_score=15,
            upcoming_move="CONCEDE",
            scene_energy="cooling",
            landed_hit=True,
        )
        assert result.inter_beat_delay_s <= 10.0

    def test_default_with_low_score_and_escalate_clamped(self, controller: PacingController):
        """Default rule: score 0 + ESCALATE = 3.0 - 0.5 = 2.5, within bounds."""
        result = controller.compute_delay(
            previous_score=0,
            upcoming_move="ESCALATE",
            scene_energy="neutral",
            landed_hit=False,
        )
        assert result.inter_beat_delay_s == pytest.approx(2.5, abs=0.01)
        assert result.inter_beat_delay_s >= 1.0


# ---------------------------------------------------------------------------
# Return type tests
# ---------------------------------------------------------------------------


class TestReturnType:
    """Tests that compute_delay always returns PacingDecision."""

    def test_returns_pacing_decision(self, controller: PacingController):
        """compute_delay returns a PacingDecision dataclass."""
        result = controller.compute_delay(
            previous_score=7,
            upcoming_move="QUESTION",
            scene_energy="neutral",
            landed_hit=False,
        )
        assert isinstance(result, PacingDecision)
        assert isinstance(result.inter_beat_delay_s, float)
        assert isinstance(result.pre_delivery_pause_s, float)
        assert isinstance(result.rule_applied, str)


# ---------------------------------------------------------------------------
# Property-Based Tests (Hypothesis)
# ---------------------------------------------------------------------------

from hypothesis import given, settings
from hypothesis import strategies as st

from conftest import st_pacing_inputs, SCENE_ENERGY_LABELS


class TestProperty18PacingDelayBounds:
    """**Property 18: Pacing Delay Bounds**

    For any input combination, final delay is always in [1.0, 10.0].

    **Validates: Requirements 7.6**
    """

    @given(inputs=st_pacing_inputs())
    @settings(max_examples=500)
    def test_delay_always_in_bounds(self, inputs: tuple):
        """Inter-beat delay is always clamped to [1.0, 10.0]."""
        controller = PacingController()
        previous_score, upcoming_move, scene_energy, landed_hit = inputs

        result = controller.compute_delay(
            previous_score=previous_score,
            upcoming_move=upcoming_move,
            scene_energy=scene_energy,
            landed_hit=landed_hit,
        )

        assert 1.0 <= result.inter_beat_delay_s <= 10.0, (
            f"Delay {result.inter_beat_delay_s} out of [1.0, 10.0] bounds. "
            f"Inputs: score={previous_score}, move={upcoming_move}, "
            f"energy={scene_energy}, landed_hit={landed_hit}"
        )

    @given(inputs=st_pacing_inputs())
    @settings(max_examples=200)
    def test_pre_delivery_pause_non_negative(self, inputs: tuple):
        """Pre-delivery pause is always >= 0."""
        controller = PacingController()
        previous_score, upcoming_move, scene_energy, landed_hit = inputs

        result = controller.compute_delay(
            previous_score=previous_score,
            upcoming_move=upcoming_move,
            scene_energy=scene_energy,
            landed_hit=landed_hit,
        )

        assert result.pre_delivery_pause_s >= 0.0


class TestProperty19PacingRuleResolution:
    """**Property 19: Pacing Rule Resolution**

    Longest delay wins when multiple rules apply, and CONCEDE pause is always additive.

    **Validates: Requirements 7.2, 7.7**
    """

    @given(
        previous_score=st.integers(min_value=0, max_value=15),
        scene_energy=st.sampled_from(SCENE_ENERGY_LABELS),
    )
    @settings(max_examples=200)
    def test_longest_delay_wins(self, previous_score: int, scene_energy: str):
        """When multiple rules apply (landed_hit + scene_energy), longest wins."""
        controller = PacingController()
        result = controller.compute_delay(
            previous_score=previous_score,
            upcoming_move="COUNTER",
            scene_energy=scene_energy,
            landed_hit=True,
        )

        # Determine expected candidates
        candidates = [controller.LANDED_HIT_DELAY]  # 4.0
        if scene_energy == "heated":
            candidates.append(controller.HEATED_DELAY)  # 2.0
        elif scene_energy == "cooling":
            candidates.append(controller.COOLING_DELAY)  # 6.5

        expected_max = max(candidates)
        # The result should match the max candidate (clamped to [1.0, 10.0])
        expected_clamped = max(1.0, min(10.0, expected_max))
        assert result.inter_beat_delay_s == pytest.approx(expected_clamped, abs=0.01), (
            f"Expected {expected_clamped} but got {result.inter_beat_delay_s}. "
            f"Candidates: {candidates}, energy={scene_energy}"
        )

    @given(
        previous_score=st.integers(min_value=0, max_value=15),
        scene_energy=st.sampled_from(SCENE_ENERGY_LABELS),
        landed_hit=st.booleans(),
    )
    @settings(max_examples=200)
    def test_concede_pause_always_additive(
        self, previous_score: int, scene_energy: str, landed_hit: bool
    ):
        """CONCEDE pre-delivery pause is always 2.0s regardless of other rules."""
        controller = PacingController()
        result_concede = controller.compute_delay(
            previous_score=previous_score,
            upcoming_move="CONCEDE",
            scene_energy=scene_energy,
            landed_hit=landed_hit,
        )

        result_other = controller.compute_delay(
            previous_score=previous_score,
            upcoming_move="COUNTER",
            scene_energy=scene_energy,
            landed_hit=landed_hit,
        )

        # CONCEDE always gets 2.0s pre-delivery pause
        assert result_concede.pre_delivery_pause_s == 2.0
        # Non-CONCEDE gets 0.0s
        assert result_other.pre_delivery_pause_s == 0.0
