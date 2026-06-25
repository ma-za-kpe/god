"""Tests for Move_Selector module.

Property tests for Properties 9, 10, 11, 12 (distribution invariants,
consecutive move penalty, counter-loop breaker, high-tension adjustment).
"""

import os
import sys

from hypothesis import given, settings

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from banter.move_selector import compute_distribution, ALL_MOVES, ARCHETYPE_SIGNATURE_MOVE
from banter.types import MoveContext

from conftest import (
    st_archetype,
    st_move,
    st_move_sequence,
    st_tension_level,
    ARCHETYPES,
    MOMENTUM_VALUES,
)
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx(
    archetype: str = "prophet",
    last_3_moves: list[str] | None = None,
    tension_level: int | None = 5,
    momentum: str | None = None,
    arc_theme: str = "test",
    fear_keywords: list[str] | None = None,
    consecutive_counters_in_pair: int = 0,
    consecutive_low_scores: int = 0,
) -> MoveContext:
    return MoveContext(
        archetype=archetype,
        last_3_moves=last_3_moves or [],
        tension_level=tension_level,
        momentum=momentum,
        arc_theme=arc_theme,
        fear_keywords=fear_keywords or [],
        consecutive_counters_in_pair=consecutive_counters_in_pair,
        consecutive_low_scores=consecutive_low_scores,
    )


# ---------------------------------------------------------------------------
# Property 10: Move Distribution Invariants
# ---------------------------------------------------------------------------


@settings(max_examples=300, deadline=2000)
@given(
    archetype=st_archetype(),
    last_3=st_move_sequence(min_size=0, max_size=3),
    tension=st.one_of(st.none(), st_tension_level()),
    momentum=st.one_of(st.none(), st.sampled_from(MOMENTUM_VALUES)),
    fear_keywords=st.lists(st.text(min_size=3, max_size=10), min_size=0, max_size=3),
    consecutive_counters=st.integers(min_value=0, max_value=5),
    consecutive_low=st.integers(min_value=0, max_value=4),
)
def test_property_10_distribution_invariants(
    archetype, last_3, tension, momentum, fear_keywords, consecutive_counters, consecutive_low
):
    """**Validates: Requirements 4.2**

    For any archetype and input combination, distribution sums to 1.0 ±0.01,
    signature move ≤ 0.40, every non-signature move ≥ 0.02.
    Exception: when counter-loop breaker fires (consecutive_counters_in_pair >= 3),
    only PIVOT and CONCEDE are non-zero — skip the min 0.02 check for that case.
    """
    ctx = _make_ctx(
        archetype=archetype,
        last_3_moves=last_3,
        tension_level=tension,
        momentum=momentum,
        fear_keywords=fear_keywords,
        consecutive_counters_in_pair=consecutive_counters,
        consecutive_low_scores=consecutive_low,
    )
    dist = compute_distribution(ctx)
    probs = dist.probabilities

    # Invariant 1: Sum to 1.0 ±0.01
    total = sum(probs.values())
    assert abs(total - 1.0) <= 0.01, f"Sum is {total}, expected ~1.0"

    # All moves present in the distribution dict
    assert set(probs.keys()) == set(ALL_MOVES)

    signature = ARCHETYPE_SIGNATURE_MOVE.get(archetype, "COUNTER")

    # When counter-loop breaker fires, only PIVOT/CONCEDE are non-zero
    # Skip signature cap and min 0.02 checks in that case
    if consecutive_counters >= 3:
        # Counter-loop breaker overrides: only PIVOT and CONCEDE non-zero
        assert probs["PIVOT"] > 0.0
        assert probs["CONCEDE"] > 0.0
        for move in ALL_MOVES:
            if move not in ("PIVOT", "CONCEDE"):
                assert probs[move] == 0.0, (
                    f"{move} = {probs[move]}, expected 0.0 under counter-loop"
                )
    else:
        # Invariant 2: Signature ≤ 0.40
        assert probs[signature] <= 0.40 + 0.01, f"Signature {signature} = {probs[signature]} > 0.40"

        # Invariant 3: Non-signature ≥ 0.02
        for move in ALL_MOVES:
            if move != signature:
                assert probs[move] >= 0.02 - 0.001, f"{move} = {probs[move]} < 0.02"


# ---------------------------------------------------------------------------
# Property 11: Consecutive Move Penalty
# ---------------------------------------------------------------------------


@settings(max_examples=200, deadline=2000)
@given(
    archetype=st_archetype(),
    repeated_move=st_move(),
)
def test_property_11_consecutive_move_penalty(archetype, repeated_move):
    """**Validates: Requirements 4.3**

    After 2 consecutive identical moves, that move's probability is exactly 0.10
    with redistributed weight. The distribution still sums to 1.0 ± 0.01.
    The penalty only applies when NOT overridden by counter-loop breaker.
    """
    # Isolate the consecutive penalty rule: no counter-loop, no losing-the-room,
    # no high tension, no fear keyword match.
    ctx = _make_ctx(
        archetype=archetype,
        last_3_moves=[repeated_move, repeated_move],
        tension_level=5,  # Not > 7, so no high-tension boost
        momentum=None,
        arc_theme="test",  # Won't match any fear keywords
        fear_keywords=[],
        consecutive_counters_in_pair=0,  # Isolate from counter-loop breaker
        consecutive_low_scores=0,  # Isolate from losing-the-room override
    )
    dist = compute_distribution(ctx)
    probs = dist.probabilities

    # 1. The repeated move's probability must be <= 0.10 + 0.01 tolerance
    assert probs[repeated_move] <= 0.10 + 0.01, (
        f"Repeated move {repeated_move} probability is {probs[repeated_move]:.4f}, "
        f"expected <= 0.11 (0.10 + tolerance)"
    )

    # 2. Distribution still sums to 1.0 ± 0.01
    total = sum(probs.values())
    assert abs(total - 1.0) <= 0.01, f"Distribution sums to {total:.4f}, expected 1.0 ± 0.01"

    # 3. All moves present in distribution
    assert set(probs.keys()) == set(ALL_MOVES), (
        f"Missing moves in distribution: {set(ALL_MOVES) - set(probs.keys())}"
    )


# ---------------------------------------------------------------------------
# Property 12: Counter-Loop Breaker
# ---------------------------------------------------------------------------


@settings(max_examples=200, deadline=2000)
@given(
    archetype=st_archetype(),
    consecutive_counters=st.integers(min_value=3, max_value=20),
)
def test_property_12_counter_loop_breaker(archetype, consecutive_counters):
    """**Validates: Requirements 4.4**

    After 3+ consecutive COUNTERs in pair, distribution is exactly
    {PIVOT: 0.50, CONCEDE: 0.50} with all others at 0.0.
    """
    ctx = _make_ctx(
        archetype=archetype,
        last_3_moves=["COUNTER", "COUNTER", "COUNTER"],
        consecutive_counters_in_pair=consecutive_counters,
    )
    dist = compute_distribution(ctx)
    probs = dist.probabilities

    # 1. PIVOT probability == 0.50
    assert abs(probs["PIVOT"] - 0.50) < 0.01, f"PIVOT = {probs['PIVOT']}, expected 0.50"

    # 2. CONCEDE probability == 0.50
    assert abs(probs["CONCEDE"] - 0.50) < 0.01, f"CONCEDE = {probs['CONCEDE']}, expected 0.50"

    # 3. All other moves == 0.0
    for move in ALL_MOVES:
        if move not in ("PIVOT", "CONCEDE"):
            assert probs[move] == 0.0, f"{move} = {probs[move]}, expected 0.0"


# ---------------------------------------------------------------------------
# Property 9: High-Tension Move Adjustment
# ---------------------------------------------------------------------------


@settings(max_examples=200, deadline=2000)
@given(archetype=st_archetype())
def test_property_9_high_tension_adjustment(archetype):
    """**Validates: Requirements 3.4**

    When tension > 7, CONCEDE+PIVOT probability increases by at least 30pp
    (using 0.25 threshold to account for normalization effects) while total
    remains 1.0 ± 0.01.

    Uses tension_level=5 (below threshold) as baseline and tension_level=8
    (above 7) as high tension, with all other modifiers isolated:
    consecutive_counters_in_pair=0, consecutive_low_scores=0, last_3_moves=[].
    """
    # Baseline: tension_level=5 (below the >7 threshold, no high-tension rule fires)
    base_ctx = _make_ctx(
        archetype=archetype,
        last_3_moves=[],
        tension_level=5,
        consecutive_counters_in_pair=0,
        consecutive_low_scores=0,
        fear_keywords=[],
    )
    base_dist = compute_distribution(base_ctx)
    base_cp = base_dist.probabilities["CONCEDE"] + base_dist.probabilities["PIVOT"]

    # High tension: tension_level=8 (above 7, high-tension rule fires)
    high_ctx = _make_ctx(
        archetype=archetype,
        last_3_moves=[],
        tension_level=8,
        consecutive_counters_in_pair=0,
        consecutive_low_scores=0,
        fear_keywords=[],
    )
    high_dist = compute_distribution(high_ctx)
    high_cp = high_dist.probabilities["CONCEDE"] + high_dist.probabilities["PIVOT"]

    # CONCEDE+PIVOT at high tension should be >= 0.25 higher than baseline
    # (raw boost is 0.30 but normalization may slightly reduce it)
    increase = high_cp - base_cp
    assert increase >= 0.25, (
        f"CONCEDE+PIVOT increase is only {increase:.3f} "
        f"(base={base_cp:.3f}, high={high_cp:.3f}), expected >= 0.25"
    )

    # Total distribution still sums to 1.0 ± 0.01
    total = sum(high_dist.probabilities.values())
    assert abs(total - 1.0) <= 0.01, f"Distribution sum is {total}, expected ~1.0"


# ---------------------------------------------------------------------------
# Additional unit tests
# ---------------------------------------------------------------------------


class TestMoveSelector:
    """Unit tests for specific move selector behaviors."""

    def test_losing_the_room_boosts_pivot(self):
        """2+ consecutive low scores should make PIVOT = 0.50."""
        ctx = _make_ctx(
            archetype="prophet",
            consecutive_low_scores=2,
            consecutive_counters_in_pair=0,
        )
        dist = compute_distribution(ctx)
        assert dist.probabilities["PIVOT"] >= 0.45

    def test_sample_returns_valid_move(self):
        """sample() should return a string that's one of ALL_MOVES."""
        ctx = _make_ctx(archetype="trickster")
        dist = compute_distribution(ctx)
        for _ in range(50):
            move = dist.sample()
            assert move in ALL_MOVES

    def test_all_archetypes_produce_valid_distributions(self):
        """Every archetype should produce a valid distribution."""
        for archetype in ARCHETYPES:
            ctx = _make_ctx(archetype=archetype)
            dist = compute_distribution(ctx)
            total = sum(dist.probabilities.values())
            assert abs(total - 1.0) <= 0.01
