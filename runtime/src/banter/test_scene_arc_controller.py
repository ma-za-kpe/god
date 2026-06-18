from collections import deque

from banter.move_selector import compute_distribution
from banter.pacing_controller import PacingController
from banter.scene_arc_controller import SceneArcController, ScenePhase
from banter.types import Beat, BeatResult, MoveContext, SceneContextData


def _scene_data(*, energy: str = "neutral") -> SceneContextData:
    return SceneContextData(
        recent_beats=deque(maxlen=3),
        has_the_room=None,
        landed_hit=None,
        landed_hit_remaining=0,
        scene_energy=energy,  # type: ignore[arg-type]
    )


def _beat(move: str, score: int) -> BeatResult:
    return BeatResult(
        line=f"{move} {score}",
        move=move,
        quality_score=score,
        delay_s=0.0,
        pre_pause_s=0.0,
        source="remote",
        metadata={},
    )


def _scene_beat(move: str, score: int) -> Beat:
    return Beat(
        speaker="shade",
        content=f"{move} {score}",
        move=move,
        quality_score=score,
        energy_label="hot" if score >= 13 else "warm" if score >= 9 else "flat",
        timestamp=0.0,
    )


def test_scene_arc_enters_release_after_two_high_tension_beats():
    controller = SceneArcController()
    scene_data = _scene_data(energy="heated")

    assert controller.resolve(beat_number=1, scene_data=scene_data) == ScenePhase.BUILD

    controller.record(
        beat_number=1,
        beat=_beat("ESCALATE", 14),
        scene_data=scene_data,
    )
    assert controller.resolve(beat_number=2, scene_data=scene_data) == ScenePhase.BUILD

    controller.record(
        beat_number=2,
        beat=_beat("TAUNT", 14),
        scene_data=scene_data,
    )
    assert controller.resolve(beat_number=3, scene_data=scene_data) == ScenePhase.RELEASE


def test_scene_arc_release_expires_into_reset():
    controller = SceneArcController()
    scene_data = _scene_data(energy="heated")

    controller.record(
        beat_number=1,
        beat=_beat("ESCALATE", 14),
        scene_data=scene_data,
    )
    controller.record(
        beat_number=2,
        beat=_beat("TAUNT", 14),
        scene_data=scene_data,
    )
    assert controller.resolve(beat_number=15, scene_data=_scene_data()) == ScenePhase.RESET


def test_scene_phase_biases_move_distribution():
    base_ctx = {
        "archetype": "prophet",
        "last_3_moves": ["QUESTION", "QUESTION"],
        "tension_level": 6,
        "momentum": "shifting",
        "arc_theme": "test",
        "fear_keywords": [],
        "consecutive_counters_in_pair": 0,
        "consecutive_low_scores": 0,
        "scene_phase": None,
    }
    release_ctx = {**base_ctx, "scene_phase": "release"}

    base = compute_distribution(MoveContext(**base_ctx))
    release = compute_distribution(MoveContext(**release_ctx))

    assert (
        release.probabilities["PIVOT"] + release.probabilities["CONCEDE"]
        > base.probabilities["PIVOT"] + base.probabilities["CONCEDE"]
    )


def test_scene_phase_changes_pacing():
    pacing = PacingController()

    base = pacing.compute_delay(
        previous_score=8,
        upcoming_move="QUESTION",
        scene_energy="neutral",
        landed_hit=False,
    )
    release = pacing.compute_delay(
        previous_score=8,
        upcoming_move="QUESTION",
        scene_energy="neutral",
        landed_hit=False,
        scene_phase="release",
    )
    climax = pacing.compute_delay(
        previous_score=8,
        upcoming_move="QUESTION",
        scene_energy="neutral",
        landed_hit=False,
        scene_phase="climax",
    )

    assert release.inter_beat_delay_s >= base.inter_beat_delay_s
    assert climax.inter_beat_delay_s <= base.inter_beat_delay_s


def test_release_requests_a_pivot_when_the_room_has_earned_it():
    controller = SceneArcController()
    scene_data = _scene_data(energy="heated")

    controller.record(
        beat_number=1,
        beat=_scene_beat("ESCALATE", 14),
        scene_data=scene_data,
    )
    controller.record(
        beat_number=2,
        beat=_scene_beat("TAUNT", 14),
        scene_data=scene_data,
    )

    assert controller.resolve(beat_number=3, scene_data=scene_data) == ScenePhase.RELEASE
    assert (
        controller.macro_move_override(
            phase=ScenePhase.RELEASE,
            beat_number=3,
            scene_data=scene_data,
        )
        == "PIVOT"
    )


def test_release_exits_once_a_breathing_move_lands():
    controller = SceneArcController()
    scene_data = _scene_data(energy="heated")

    controller.record(
        beat_number=1,
        beat=_scene_beat("ESCALATE", 14),
        scene_data=scene_data,
    )
    controller.record(
        beat_number=2,
        beat=_scene_beat("TAUNT", 14),
        scene_data=scene_data,
    )
    assert controller.resolve(beat_number=3, scene_data=scene_data) == ScenePhase.RELEASE

    controller.record(
        beat_number=3,
        beat=_scene_beat("PIVOT", 11),
        scene_data=_scene_data(energy="neutral"),
    )
    assert controller.resolve(beat_number=4, scene_data=_scene_data(energy="neutral")) == ScenePhase.RESET
