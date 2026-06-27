"""Basic functional tests for move_selector.py."""

import sys

sys.path.insert(0, "/app/src")

from banter.move_selector import compute_distribution, ARCHETYPE_SIGNATURE_MOVE, ALL_MOVES
from banter.types import MoveContext


def test_basic_distribution_sums_to_one():
    ctx = MoveContext(
        archetype="parasite",
        last_3_moves=[],
        tension_level=5,
        momentum=None,
        arc_theme="power",
        fear_keywords=[],
        consecutive_counters_in_pair=0,
        consecutive_low_scores=0,
    )
    dist = compute_distribution(ctx)
    total = sum(dist.probabilities.values())
    assert abs(total - 1.0) < 0.01, f"Sum was {total}"


def test_counter_loop_breaker():
    ctx = MoveContext(
        archetype="parasite",
        last_3_moves=["COUNTER", "COUNTER", "COUNTER"],
        tension_level=5,
        momentum=None,
        arc_theme="power",
        fear_keywords=[],
        consecutive_counters_in_pair=3,
        consecutive_low_scores=0,
    )
    dist = compute_distribution(ctx)
    assert dist.probabilities["PIVOT"] == 0.50
    assert dist.probabilities["CONCEDE"] == 0.50
    # All others must be 0.0
    for move in ALL_MOVES:
        if move not in ("PIVOT", "CONCEDE"):
            assert dist.probabilities[move] == 0.0


def test_signature_move_capped_at_040():
    for archetype, sig_move in ARCHETYPE_SIGNATURE_MOVE.items():
        ctx = MoveContext(
            archetype=archetype,
            last_3_moves=[],
            tension_level=None,
            momentum=None,
            arc_theme="power",
            fear_keywords=[],
            consecutive_counters_in_pair=0,
            consecutive_low_scores=0,
        )
        dist = compute_distribution(ctx)
        assert dist.probabilities[sig_move] <= 0.40 + 0.001, (
            f"{archetype} signature {sig_move} = {dist.probabilities[sig_move]}"
        )


def test_non_signature_at_least_002():
    for archetype, sig_move in ARCHETYPE_SIGNATURE_MOVE.items():
        ctx = MoveContext(
            archetype=archetype,
            last_3_moves=[],
            tension_level=None,
            momentum=None,
            arc_theme="power",
            fear_keywords=[],
            consecutive_counters_in_pair=0,
            consecutive_low_scores=0,
        )
        dist = compute_distribution(ctx)
        for move, prob in dist.probabilities.items():
            if move != sig_move:
                assert prob >= 0.02 - 0.001, f"{archetype}: {move} = {prob} < 0.02"


def test_consecutive_move_penalty():
    # Use signature move (QUESTION for prophet) which starts at 0.30
    # After 2 consecutive uses, it should be reduced to 0.10
    ctx = MoveContext(
        archetype="prophet",
        last_3_moves=["QUESTION", "QUESTION"],
        tension_level=None,
        momentum=None,
        arc_theme="power",
        fear_keywords=[],
        consecutive_counters_in_pair=0,
        consecutive_low_scores=0,
    )
    dist = compute_distribution(ctx)
    base_ctx = MoveContext(
        archetype="prophet",
        last_3_moves=[],
        tension_level=None,
        momentum=None,
        arc_theme="power",
        fear_keywords=[],
        consecutive_counters_in_pair=0,
        consecutive_low_scores=0,
    )
    base_dist = compute_distribution(base_ctx)
    # The penalized move should have lower probability than base
    assert dist.probabilities["QUESTION"] < base_dist.probabilities["QUESTION"]


def test_losing_the_room_pivot_dominant():
    ctx = MoveContext(
        archetype="prophet",
        last_3_moves=[],
        tension_level=None,
        momentum=None,
        arc_theme="power",
        fear_keywords=[],
        consecutive_counters_in_pair=0,
        consecutive_low_scores=2,
    )
    dist = compute_distribution(ctx)
    # PIVOT should be the dominant move (close to 0.50)
    assert dist.probabilities["PIVOT"] >= 0.40
    # Should still sum to 1.0
    total = sum(dist.probabilities.values())
    assert abs(total - 1.0) < 0.01


def test_high_tension_boosts_concede_pivot():
    # Without tension
    ctx_low = MoveContext(
        archetype="trickster",
        last_3_moves=[],
        tension_level=5,
        momentum=None,
        arc_theme="power",
        fear_keywords=[],
        consecutive_counters_in_pair=0,
        consecutive_low_scores=0,
    )
    dist_low = compute_distribution(ctx_low)

    # With high tension
    ctx_high = MoveContext(
        archetype="trickster",
        last_3_moves=[],
        tension_level=9,
        momentum=None,
        arc_theme="power",
        fear_keywords=[],
        consecutive_counters_in_pair=0,
        consecutive_low_scores=0,
    )
    dist_high = compute_distribution(ctx_high)

    cp_low = dist_low.probabilities["CONCEDE"] + dist_low.probabilities["PIVOT"]
    cp_high = dist_high.probabilities["CONCEDE"] + dist_high.probabilities["PIVOT"]

    # High tension should boost CONCEDE+PIVOT
    assert cp_high > cp_low


def test_fear_keyword_match_boosts_escalate_question():
    # Without fear match
    ctx_no_fear = MoveContext(
        archetype="parasite",
        last_3_moves=[],
        tension_level=None,
        momentum=None,
        arc_theme="power",
        fear_keywords=["exposure", "worthlessness"],
        consecutive_counters_in_pair=0,
        consecutive_low_scores=0,
    )
    dist_no_fear = compute_distribution(ctx_no_fear)

    # With fear match (arc_theme matches a fear keyword)
    ctx_fear = MoveContext(
        archetype="parasite",
        last_3_moves=[],
        tension_level=None,
        momentum=None,
        arc_theme="exposure",
        fear_keywords=["exposure", "worthlessness"],
        consecutive_counters_in_pair=0,
        consecutive_low_scores=0,
    )
    dist_fear = compute_distribution(ctx_fear)

    eq_no_fear = dist_no_fear.probabilities["ESCALATE"] + dist_no_fear.probabilities["QUESTION"]
    eq_fear = dist_fear.probabilities["ESCALATE"] + dist_fear.probabilities["QUESTION"]

    # Fear match should boost ESCALATE+QUESTION
    assert eq_fear > eq_no_fear


def test_sample_returns_valid_move():
    ctx = MoveContext(
        archetype="parasite",
        last_3_moves=[],
        tension_level=None,
        momentum=None,
        arc_theme="power",
        fear_keywords=[],
        consecutive_counters_in_pair=0,
        consecutive_low_scores=0,
    )
    dist = compute_distribution(ctx)
    for _ in range(50):
        sample = dist.sample()
        assert sample in ALL_MOVES


def test_all_archetypes_produce_valid_distributions():
    for archetype in ARCHETYPE_SIGNATURE_MOVE:
        ctx = MoveContext(
            archetype=archetype,
            last_3_moves=[],
            tension_level=5,
            momentum="escalating",
            arc_theme="power",
            fear_keywords=[],
            consecutive_counters_in_pair=0,
            consecutive_low_scores=0,
        )
        dist = compute_distribution(ctx)
        total = sum(dist.probabilities.values())
        assert abs(total - 1.0) < 0.01, f"{archetype}: sum = {total}"
        assert all(p >= 0 for p in dist.probabilities.values())
