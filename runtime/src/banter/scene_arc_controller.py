"""Scene arc controller for macro-level dramatic rhythm.

This controller sits above micro-pacing and move selection. It tracks the
current dramatic phase of a scene and forces waves:
BUILD -> CLIMAX -> RELEASE -> RESET -> BUILD.

Requirements: dramatic rhythm / arc exploration for the contract-alignment
phase. The controller is intentionally lightweight and deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .types import Beat, SceneContextData


class ScenePhase(Enum):
    """Macro dramatic phases for a scene."""

    BUILD = "build"
    CLIMAX = "climax"
    RELEASE = "release"
    RESET = "reset"


@dataclass
class SceneArcState:
    """Mutable arc state tracked across a session."""

    phase: ScenePhase = ScenePhase.BUILD
    phase_started_beat: int = 0
    beats_in_phase: int = 0
    high_tension_streak: int = 0
    pressure_cluster_streak: int = 0
    release_until_beat: int = 0
    pivot_until_beat: int = 0


class SceneArcController:
    """Resolve and advance scene-phase transitions."""

    RELEASE_WINDOW_BEATS = 12
    RESET_WINDOW_BEATS = 6
    BUILD_WINDOW_BEATS = 12
    FORCE_SHIFT_WINDOW_BEATS = 48

    def __init__(self) -> None:
        self._state = SceneArcState()

    def resolve(self, *, beat_number: int, scene_data: SceneContextData) -> ScenePhase:
        """Resolve the phase that should govern the next beat."""
        self._maybe_close_windows(beat_number)

        if self._state.phase == ScenePhase.RELEASE and beat_number <= self._state.release_until_beat:
            return ScenePhase.RELEASE

        if beat_number > 0 and beat_number % self.FORCE_SHIFT_WINDOW_BEATS == 0:
            self._force_shift(scene_data, beat_number)

        if self._state.phase == ScenePhase.CLIMAX:
            if self._should_release_from_payoff(scene_data):
                self._transition(
                    ScenePhase.RELEASE,
                    beat_number,
                    release_until=beat_number + self.RELEASE_WINDOW_BEATS,
                    pivot_until=beat_number + 3,
                )

        return self._state.phase

    def record(
        self,
        *,
        beat_number: int,
        beat: Beat,
        scene_data: SceneContextData,
    ) -> ScenePhase:
        """Advance the arc state after a beat has been delivered."""
        high_tension = beat.quality_score >= 13 and beat.move in {"ESCALATE", "TAUNT", "CRACK"}
        pressure_move = beat.move in {"ESCALATE", "TAUNT", "COUNTER", "DEFLECT", "QUESTION"}
        release_move = beat.move in {"CONCEDE", "PIVOT", "CALLBACK", "BACKCHANNEL", "SILENCE"}

        if high_tension:
            self._state.high_tension_streak += 1
        elif release_move:
            self._state.high_tension_streak = 0
        else:
            self._state.high_tension_streak = max(0, self._state.high_tension_streak - 1)

        if pressure_move:
            self._state.pressure_cluster_streak += 1
        elif release_move:
            self._state.pressure_cluster_streak = 0
        else:
            self._state.pressure_cluster_streak = max(0, self._state.pressure_cluster_streak - 1)

        self._state.beats_in_phase += 1

        if self._state.phase == ScenePhase.BUILD:
            if self._should_release_from_payoff(scene_data):
                self._transition(
                    ScenePhase.RELEASE,
                    beat_number,
                    release_until=beat_number + self.RELEASE_WINDOW_BEATS,
                    pivot_until=beat_number + 3,
                )
            elif self._state.beats_in_phase >= self.BUILD_WINDOW_BEATS and scene_data.scene_energy == "heated":
                self._transition(ScenePhase.CLIMAX, beat_number)
            elif self._state.pressure_cluster_streak >= 4 and scene_data.scene_energy != "neutral":
                self._transition(ScenePhase.CLIMAX, beat_number)

        elif self._state.phase == ScenePhase.CLIMAX:
            if self._should_release_from_payoff(scene_data):
                self._transition(
                    ScenePhase.RELEASE,
                    beat_number,
                    release_until=beat_number + self.RELEASE_WINDOW_BEATS,
                    pivot_until=beat_number + 3,
                )

        elif self._state.phase == ScenePhase.RELEASE:
            if (
                beat.move in {"PIVOT", "CONCEDE", "CALLBACK", "BACKCHANNEL"}
                and self._state.beats_in_phase >= 1
            ) or (
                self._state.beats_in_phase >= 4 and scene_data.scene_energy != "heated"
            ) or beat_number >= self._state.release_until_beat:
                self._transition(ScenePhase.RESET, beat_number)

        elif self._state.phase == ScenePhase.RESET:
            if (
                self._state.beats_in_phase >= self.RESET_WINDOW_BEATS
                or (self._state.beats_in_phase >= 3 and self._state.pressure_cluster_streak == 0)
            ):
                self._transition(ScenePhase.BUILD, beat_number)

        return self._state.phase

    def macro_move_override(
        self,
        *,
        phase: ScenePhase,
        beat_number: int,
        scene_data: SceneContextData,
    ) -> str | None:
        """Return a macro move override when the scene needs a hard pivot."""
        if beat_number > 0 and beat_number % self.FORCE_SHIFT_WINDOW_BEATS == 0:
            return "PIVOT"

        if phase == ScenePhase.RELEASE:
            if beat_number <= self._state.pivot_until_beat:
                return "PIVOT"
            if self._state.pressure_cluster_streak >= 3 or scene_data.landed_hit is not None:
                return "PIVOT"
            if scene_data.scene_energy == "cooling":
                return "CALLBACK"

        if phase == ScenePhase.RESET:
            if self._state.beats_in_phase <= 2:
                return "QUESTION"
            return "PIVOT"

        if (
            phase == ScenePhase.CLIMAX
            and scene_data.landed_hit is not None
            and scene_data.landed_hit_remaining > 0
            and self._state.pressure_cluster_streak >= 2
        ):
            return "PIVOT"

        return None

    def rhythm_instruction(
        self,
        *,
        phase: ScenePhase,
        beat_number: int,
        scene_data: SceneContextData,
        move: str,
    ) -> str | None:
        """Return a phase-specific [RHYTHM] directive."""
        if phase == ScenePhase.CLIMAX:
            return (
                "This is a climax beat. Keep it sharp, direct, and final. "
                "Do not soften the hit."
            )

        if phase == ScenePhase.RELEASE:
            return (
                "This is a release beat. You may concede one inch, reflect on the room, "
                "or pivot to a deeper angle. Let the room breathe."
            )

        if phase == ScenePhase.RESET:
            return (
                "This is a reset beat. The prior pressure has spent itself. "
                "Shift the terrain and seed a new angle."
            )

        if beat_number > 0 and beat_number % self.FORCE_SHIFT_WINDOW_BEATS == 0:
            return (
                "This is a boundary beat. You are allowed one clean pivot if it exposes "
                "a deeper truth."
            )

        if scene_data.landed_hit is not None and scene_data.landed_hit_remaining > 0:
            return (
                "A landed hit is still in the room. Keep your line compact and aware "
                "of the impact."
            )

        if move in ("CONCEDE", "DEFLECT") and scene_data.scene_energy == "cooling":
            return (
                "The room is cooling. A shorter, trailing line is allowed if it stays intentional."
            )

        return None

    def phase_name(self) -> str:
        """Return the current phase as a string."""
        return self._state.phase.value

    def reset(self) -> None:
        """Reset the arc state for a new session."""
        self._state = SceneArcState()

    def _force_shift(self, scene_data: SceneContextData, beat_number: int) -> None:
        """Force a phase shift every fixed window."""
        if self._should_release_from_payoff(scene_data):
            self._transition(
                ScenePhase.RELEASE,
                beat_number,
                release_until=beat_number + self.RELEASE_WINDOW_BEATS,
                pivot_until=beat_number + 3,
            )
        elif scene_data.scene_energy == "heated" or (
            scene_data.landed_hit is not None and scene_data.landed_hit_remaining > 0
        ):
            self._transition(ScenePhase.CLIMAX, beat_number)
        elif scene_data.scene_energy == "cooling":
            self._transition(ScenePhase.RESET, beat_number)
        else:
            self._transition(ScenePhase.BUILD, beat_number)

    def _maybe_close_windows(self, beat_number: int) -> None:
        if self._state.phase == ScenePhase.RELEASE and beat_number > self._state.release_until_beat:
            self._transition(ScenePhase.RESET, beat_number)

    def _should_release_from_payoff(self, scene_data: SceneContextData) -> bool:
        """Return True when the scene has earned a release beat."""
        if self._state.high_tension_streak >= 2:
            return True
        if self._state.pressure_cluster_streak >= 4 and scene_data.scene_energy == "heated":
            return True
        if (
            scene_data.landed_hit is not None
            and scene_data.landed_hit_remaining > 0
            and self._state.beats_in_phase >= 4
        ):
            return True
        return False

    def _transition(
        self,
        phase: ScenePhase,
        beat_number: int,
        *,
        release_until: int | None = None,
        pivot_until: int | None = None,
    ) -> None:
        self._state.phase = phase
        self._state.phase_started_beat = beat_number
        self._state.beats_in_phase = 0
        self._state.high_tension_streak = 0
        if release_until is not None:
            self._state.release_until_beat = release_until
        elif phase != ScenePhase.RELEASE:
            self._state.release_until_beat = 0
        if pivot_until is not None:
            self._state.pivot_until_beat = pivot_until
        elif phase != ScenePhase.RELEASE:
            self._state.pivot_until_beat = 0
