"""ModeResolver — strict-precedence mode resolution for the banter pipeline.

Determines the active BeatMode for each beat using the precedence chain:
SILENCE → BACKCHANNEL → SNAP_BACK → CRACK → CHAOS → NORMAL

Mode resolution happens BEFORE prompt construction. The resolved BeatModePolicy
is passed to all downstream components (PromptBuilder, QualityJudge, HardBanChecker).

Requirements: 5.2, 12.2
"""

from __future__ import annotations

from .backchannel import BackchannelSelector
from .mode_types import (
    BACKCHANNEL_POLICY,
    CHAOS_POLICY,
    CRACK_POLICY,
    NORMAL_POLICY,
    SILENCE_POLICY,
    SNAP_BACK_POLICY,
    BeatMode,
    BeatModePolicy,
)
from .rate_controllers import SlidingWindowController
from .silence_controller import SilenceController
from .types import PairState, SceneContextData


class ModeResolver:
    """Resolves the active BeatMode using strict precedence ordering.

    Precedence (highest to lowest):
    1. SILENCE — landed hit aftermath or falling tension
    2. BACKCHANNEL — opponent line qualifies and controller grants
    3. SNAP_BACK — same Elder's previous beat was CRACK
    4. CRACK — production PairState satisfies all trigger conditions
    5. CHAOS — tension >= 8 or consecutive_escalations >= 4
    6. NORMAL — default fallthrough

    Requirements: 5.2, 12.2
    """

    def __init__(
        self,
        silence_controller: SilenceController | None = None,
        backchannel_controller: BackchannelSelector | None = None,
        backchannel_rate_controller: SlidingWindowController | None = None,
        crack_rate_controller: SlidingWindowController | None = None,
    ) -> None:
        self._silence = silence_controller or SilenceController()
        self._backchannel = backchannel_controller or BackchannelSelector()
        # BACKCHANNEL: max 1 per 5 eligible beats per pair
        self._backchannel_rc = backchannel_rate_controller or SlidingWindowController(
            max_count=1, window_size=5
        )
        # CRACK: max 1 per 30 eligible beats per pair
        self._crack_rc = crack_rate_controller or SlidingWindowController(
            max_count=1, window_size=30
        )
        # Track chaos firing to enforce single-beat duration
        self._chaos_fired_last_beat: dict[str, bool] = {}

    def resolve(
        self,
        elder: str,
        opponent: str | None,
        pair_state: PairState | None,
        scene_data: SceneContextData,
        beat_number: int,
        prev_elder_mode: BeatMode | None,
        opponent_last_score: int | None,
    ) -> BeatModePolicy:
        """Resolve the active BeatModePolicy for this beat.

        Args:
            elder: Name of the speaking Elder.
            opponent: Name of the opponent Elder (None if solo).
            pair_state: Current relationship state (None if unavailable).
            scene_data: Current scene context.
            beat_number: Current beat number in the session.
            prev_elder_mode: The mode of THIS Elder's previous beat (for snap-back).
            opponent_last_score: Quality score of opponent's last beat (for backchannel).

        Returns:
            The resolved BeatModePolicy for this beat.
        """
        # Advance the CRACK rate controller's internal beat counter
        self._crack_rc.tick()

        # 1. SILENCE — highest priority
        if self._silence.should_silence(scene_data, pair_state):
            self._chaos_fired_last_beat[elder] = False
            return SILENCE_POLICY

        # 2. BACKCHANNEL — opponent line qualifies
        if opponent_last_score is not None and self._backchannel.should_fire(opponent_last_score):
            pair_id = f"{elder}:{opponent or 'solo'}"
            if self._backchannel_rc.allow(pair_id):
                self._backchannel_rc.record(pair_id)
                self._chaos_fired_last_beat[elder] = False
                return BACKCHANNEL_POLICY

        # 3. SNAP_BACK — same Elder's previous beat was CRACK
        if prev_elder_mode == BeatMode.CRACK:
            self._chaos_fired_last_beat[elder] = False
            return SNAP_BACK_POLICY

        # 4. CRACK — production PairState satisfies trigger
        if self._should_crack(pair_state, elder, opponent):
            self._chaos_fired_last_beat[elder] = False
            return CRACK_POLICY

        # 5. CHAOS — tension >= 8 or consecutive_escalations >= 4
        #    Fires for exactly one beat (Property 7)
        if self._should_chaos(pair_state, elder):
            self._chaos_fired_last_beat[elder] = True
            return CHAOS_POLICY

        # 6. NORMAL — default
        self._chaos_fired_last_beat[elder] = False
        return NORMAL_POLICY

    def _should_crack(
        self,
        pair_state: PairState | None,
        elder: str,
        opponent: str | None,
    ) -> bool:
        """Check if CRACK should fire from production PairState.

        All conditions must be satisfied (Section 8.2):
        - pair_state.recent_betrayal == True
        - pair_state.tension_level > 8
        - pair_state.consecutive_counters >= 3
        - rate_controller.allow(pair_id) (max 1 per 30 beats per pair)
        """
        if pair_state is None or opponent is None:
            return False

        if not pair_state.recent_betrayal:
            return False
        if pair_state.tension_level <= 8:
            return False
        if pair_state.consecutive_counters < 3:
            return False

        pair_id = f"{elder}:{opponent}"
        if not self._crack_rc.allow(pair_id):
            return False

        # Record the CRACK activation
        self._crack_rc.record(pair_id)
        return True

    def _should_chaos(self, pair_state: PairState | None, elder: str) -> bool:
        """Check if CHAOS should fire for exactly one beat.

        Conditions (Section 5.3):
        - tension >= 8 OR consecutive_escalations >= 4
        - Did NOT fire on this Elder's immediately previous beat (one-beat rule)
        """
        if pair_state is None:
            return False

        # Chaos must not fire on consecutive beats for the same Elder
        if self._chaos_fired_last_beat.get(elder, False):
            return False

        return (
            pair_state.tension_level >= 8
            or pair_state.consecutive_escalations >= 4
        )
