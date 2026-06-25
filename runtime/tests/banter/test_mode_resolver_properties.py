"""Property tests for ModeResolver — validates Section 5 and 8 contract.

Properties tested:
- Property 6: BeatModePolicy matches contract table
- Property 7: Chaos lasts exactly one beat
- Property 10: CRACK fires only when all conditions met
- Property 15: CRACK rate limited to max 1 per 30 eligible beats per pair
"""

from __future__ import annotations

import random


from banter.mode_resolver import ModeResolver
from banter.mode_types import (
    BACKCHANNEL_POLICY,
    CHAOS_POLICY,
    CRACK_POLICY,
    NORMAL_POLICY,
    SILENCE_POLICY,
    SNAP_BACK_POLICY,
    BeatMode,
    POLICY_TABLE,
)
from banter.rate_controllers import SlidingWindowController
from banter.silence_controller import SilenceController
from banter.types import PairState, SceneContextData


def _make_scene_data(landed_hit=None, landed_hit_remaining=0):
    """Create a SceneContextData for testing."""
    data = SceneContextData()
    if landed_hit is not None:
        data.landed_hit = landed_hit
        data.landed_hit_remaining = landed_hit_remaining
    return data


def _make_pair_state(
    tension: int = 5,
    recent_betrayal: bool = False,
    consecutive_counters: int = 0,
    consecutive_escalations: int = 0,
) -> PairState:
    """Create a PairState for testing."""
    import time

    return PairState(
        tension_level=tension,
        last_interaction_ts=time.time(),
        recent_betrayal=recent_betrayal,
        consecutive_counters=consecutive_counters,
        consecutive_escalations=consecutive_escalations,
    )


# ---------------------------------------------------------------------------
# Property 6: BeatModePolicy matches contract table for all modes
# ---------------------------------------------------------------------------


class TestProperty6PolicyTable:
    """Property 6: BeatModePolicy matches contract table for all modes.

    For any BeatMode value, the resolved BeatModePolicy must have fields
    matching the contract table.

    Validates: Requirements 5.4, 5.5, 7.4, 12.2
    """

    def test_normal_policy_matches_contract(self):
        assert NORMAL_POLICY.mode == BeatMode.NORMAL
        assert NORMAL_POLICY.quality_threshold == 9
        assert NORMAL_POLICY.refinement_allowed is True
        assert NORMAL_POLICY.anti_repetition_enabled is True
        assert NORMAL_POLICY.hard_bans_enabled is True
        assert NORMAL_POLICY.word_count_min == 4
        assert NORMAL_POLICY.word_count_max == 30
        assert NORMAL_POLICY.move_override is None

    def test_chaos_policy_matches_contract(self):
        assert CHAOS_POLICY.mode == BeatMode.CHAOS
        assert CHAOS_POLICY.quality_threshold == 6
        assert CHAOS_POLICY.refinement_allowed is False
        assert CHAOS_POLICY.anti_repetition_enabled is False
        assert CHAOS_POLICY.hard_bans_enabled is True
        assert CHAOS_POLICY.word_count_min == 4
        assert CHAOS_POLICY.word_count_max == 30
        assert CHAOS_POLICY.move_override == "ESCALATE"

    def test_crack_policy_matches_contract(self):
        assert CRACK_POLICY.mode == BeatMode.CRACK
        assert CRACK_POLICY.quality_threshold == 5
        assert CRACK_POLICY.refinement_allowed is False
        assert CRACK_POLICY.anti_repetition_enabled is True
        assert CRACK_POLICY.hard_bans_enabled is True
        assert CRACK_POLICY.word_count_min == 4
        assert CRACK_POLICY.word_count_max == 20
        assert CRACK_POLICY.move_override is None

    def test_snap_back_policy_matches_contract(self):
        assert SNAP_BACK_POLICY.mode == BeatMode.SNAP_BACK
        assert SNAP_BACK_POLICY.quality_threshold == 8
        assert SNAP_BACK_POLICY.refinement_allowed is True
        assert SNAP_BACK_POLICY.anti_repetition_enabled is True
        assert SNAP_BACK_POLICY.hard_bans_enabled is True
        assert SNAP_BACK_POLICY.word_count_min == 4
        assert SNAP_BACK_POLICY.word_count_max == 30
        assert SNAP_BACK_POLICY.move_override is None

    def test_backchannel_policy_matches_contract(self):
        assert BACKCHANNEL_POLICY.mode == BeatMode.BACKCHANNEL
        assert BACKCHANNEL_POLICY.quality_threshold is None
        assert BACKCHANNEL_POLICY.refinement_allowed is False
        assert BACKCHANNEL_POLICY.anti_repetition_enabled is False
        assert BACKCHANNEL_POLICY.hard_bans_enabled is True
        assert BACKCHANNEL_POLICY.word_count_min == 2
        assert BACKCHANNEL_POLICY.word_count_max == 6
        assert BACKCHANNEL_POLICY.move_override is None

    def test_silence_policy_matches_contract(self):
        assert SILENCE_POLICY.mode == BeatMode.SILENCE
        assert SILENCE_POLICY.quality_threshold is None
        assert SILENCE_POLICY.refinement_allowed is False
        assert SILENCE_POLICY.anti_repetition_enabled is False
        assert SILENCE_POLICY.hard_bans_enabled is False
        assert SILENCE_POLICY.word_count_min == 0
        assert SILENCE_POLICY.word_count_max == 0
        assert SILENCE_POLICY.move_override is None

    def test_policy_table_covers_all_modes(self):
        """Every BeatMode value has an entry in the POLICY_TABLE."""
        for mode in BeatMode:
            assert mode in POLICY_TABLE, f"Missing policy for mode: {mode}"


# ---------------------------------------------------------------------------
# Property 7: Chaos lasts exactly one beat
# ---------------------------------------------------------------------------


class TestProperty7ChaosOneBeat:
    """Property 7: Chaos lasts exactly one beat.

    When chaos fires, the mode resolver returns CHAOS for exactly one beat.
    The next beat returns non-CHAOS unless independently triggered.

    Validates: Requirements 5.3, 5.5
    """

    def test_chaos_fires_once_then_normal(self):
        """Chaos fires one beat then returns to NORMAL."""
        resolver = ModeResolver(
            silence_controller=SilenceController(rng=random.Random(999)),
            crack_rate_controller=SlidingWindowController(max_count=1, window_size=30),
        )

        # High tension triggers chaos
        ps = _make_pair_state(tension=9, consecutive_escalations=5)
        scene = _make_scene_data()

        # First call: should get CHAOS
        policy1 = resolver.resolve(
            elder="prophet",
            opponent="keeper",
            pair_state=ps,
            scene_data=scene,
            beat_number=1,
            prev_elder_mode=None,
            opponent_last_score=None,
        )
        assert policy1.mode == BeatMode.CHAOS

        # Second call (same conditions): should NOT get CHAOS (one-beat rule)
        policy2 = resolver.resolve(
            elder="prophet",
            opponent="keeper",
            pair_state=ps,
            scene_data=scene,
            beat_number=2,
            prev_elder_mode=BeatMode.CHAOS,
            opponent_last_score=None,
        )
        assert policy2.mode != BeatMode.CHAOS

    def test_chaos_can_fire_again_after_reset(self):
        """After a non-chaos beat, chaos can fire again if conditions hold."""
        resolver = ModeResolver(
            silence_controller=SilenceController(rng=random.Random(999)),
            crack_rate_controller=SlidingWindowController(max_count=1, window_size=30),
        )

        ps = _make_pair_state(tension=9, consecutive_escalations=5)
        scene = _make_scene_data()

        # Beat 1: CHAOS
        p1 = resolver.resolve("prophet", "keeper", ps, scene, 1, None, None)
        assert p1.mode == BeatMode.CHAOS

        # Beat 2: NOT CHAOS (one-beat cooldown)
        p2 = resolver.resolve("prophet", "keeper", ps, scene, 2, BeatMode.CHAOS, None)
        assert p2.mode != BeatMode.CHAOS

        # Beat 3: CHAOS can fire again (reset happened)
        p3 = resolver.resolve("prophet", "keeper", ps, scene, 3, BeatMode.NORMAL, None)
        assert p3.mode == BeatMode.CHAOS


# ---------------------------------------------------------------------------
# Property 10: CRACK fires only when all production conditions met
# ---------------------------------------------------------------------------


class TestProperty10CRACKConditions:
    """Property 10: CRACK fires only when all trigger conditions met.

    CRACK requires: recent_betrayal AND tension > 8 AND consecutive_counters >= 3
    AND rate_controller allows.

    Validates: Requirements 8.2, 8.3, 8.5
    """

    def test_crack_requires_all_conditions(self):
        """CRACK does not fire when any single condition is missing."""
        resolver = ModeResolver(
            silence_controller=SilenceController(rng=random.Random(999)),
            crack_rate_controller=SlidingWindowController(max_count=1, window_size=30),
        )
        scene = _make_scene_data()

        # Missing recent_betrayal
        ps = _make_pair_state(tension=9, recent_betrayal=False, consecutive_counters=4)
        p = resolver.resolve("prophet", "keeper", ps, scene, 1, None, None)
        assert p.mode != BeatMode.CRACK

        # Missing high tension
        ps = _make_pair_state(tension=7, recent_betrayal=True, consecutive_counters=4)
        p = resolver.resolve("prophet", "keeper", ps, scene, 2, None, None)
        assert p.mode != BeatMode.CRACK

        # Missing consecutive_counters
        ps = _make_pair_state(tension=9, recent_betrayal=True, consecutive_counters=2)
        p = resolver.resolve("prophet", "keeper", ps, scene, 3, None, None)
        assert p.mode != BeatMode.CRACK

    def test_crack_fires_when_all_conditions_met(self):
        """CRACK fires when all conditions are satisfied."""
        resolver = ModeResolver(
            silence_controller=SilenceController(rng=random.Random(999)),
            crack_rate_controller=SlidingWindowController(max_count=1, window_size=30),
        )
        scene = _make_scene_data()

        ps = _make_pair_state(tension=9, recent_betrayal=True, consecutive_counters=4)
        p = resolver.resolve("prophet", "keeper", ps, scene, 1, None, None)
        assert p.mode == BeatMode.CRACK

    def test_snap_back_follows_crack(self):
        """When prev_elder_mode is CRACK, SNAP_BACK fires."""
        resolver = ModeResolver(
            silence_controller=SilenceController(rng=random.Random(999)),
            crack_rate_controller=SlidingWindowController(max_count=1, window_size=30),
        )
        scene = _make_scene_data()
        ps = _make_pair_state(tension=5)

        p = resolver.resolve("prophet", "keeper", ps, scene, 2, BeatMode.CRACK, None)
        assert p.mode == BeatMode.SNAP_BACK


# ---------------------------------------------------------------------------
# Property 15: CRACK rate limited to max 1 per 30 eligible beats
# ---------------------------------------------------------------------------


class TestProperty15CRACKRateLimit:
    """Property 15: CRACK rate limited to max 1 per 30 eligible beats per pair.

    Validates: Requirements 8.2, 12.4
    """

    def test_crack_fires_at_most_once_per_30_beats(self):
        """In 30 beats with all CRACK conditions always met, fires at most once."""
        resolver = ModeResolver(
            silence_controller=SilenceController(rng=random.Random(999)),
            crack_rate_controller=SlidingWindowController(max_count=1, window_size=30),
        )
        scene = _make_scene_data()
        ps = _make_pair_state(tension=9, recent_betrayal=True, consecutive_counters=4)

        crack_count = 0
        for i in range(30):
            p = resolver.resolve("prophet", "keeper", ps, scene, i + 1, None, None)
            if p.mode == BeatMode.CRACK:
                crack_count += 1

        assert crack_count <= 1, f"CRACK fired {crack_count} times in 30 beats (max 1)"
