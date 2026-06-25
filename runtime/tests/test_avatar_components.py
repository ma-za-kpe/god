"""Tests for avatar runtime components."""

from __future__ import annotations

from collections import deque

from avatar import AvatarSurface, SceneComposer, VisualReactor
from banter.types import Beat, PairState, SceneContextData
from voice import VoiceSurface


def test_visual_reactor_sets_crack_override():
    reactor = VisualReactor(
        crack_expression_duration_seconds=25, flinch_expression_duration_seconds=8
    )
    beat = Beat(
        speaker="Alpha",
        content="You already lost.",
        move="CRACK",
        quality_score=13,
        energy_label="hot",
        timestamp=1.0,
    )
    agent = {"soul_id": "alpha", "current_name": "Alpha"}

    expression = reactor.on_beat_delivered(
        beat, PairState(tension_level=9, last_interaction_ts=0), [agent], current_epoch=100
    )

    assert expression == "vulnerable"
    assert agent["visual_state"]["expression_override"] == "vulnerable"
    assert agent["visual_state"]["override_expiry_epoch"] == 125


def test_scene_composer_centers_has_the_room():
    composer = SceneComposer()
    ctx = SceneContextData(
        recent_beats=deque(
            [
                Beat("Alpha", "first", "ESCALATE", 9, "hot", 1.0),
                Beat("Beta", "second", "COUNTER", 10, "hot", 2.0),
                Beat("Beta", "third", "TAUNT", 11, "hot", 3.0),
            ],
            maxlen=3,
        ),
        has_the_room="Beta",
        landed_hit=None,
        landed_hit_remaining=0,
        scene_energy="heated",
    )

    layout = composer.compose_scene(
        ctx,
        {("Alpha", "Beta"): PairState(tension_level=9, last_interaction_ts=0)},
        {"Alpha": {}, "Beta": {}},
    )

    assert layout.composition_type == "duo"
    dominant = next(el for el in layout.elders if el.soul_id == "Beta")
    assert dominant.position == (0.5, 0.5)
    assert dominant.scale == 1.0


def test_avatar_surface_uses_expression_override():
    surface = AvatarSurface(enabled=True, dry_run=True)
    snapshot = {
        "epoch": 100,
        "showrunner": {"scene": "ensemble-stage", "speaker": "Beta"},
        "audience": {"patronage_index": 7},
        "agents": [
            {
                "soul_id": "beta",
                "current_name": "Beta",
                "visual_state": {
                    "current_expression": "neutral",
                    "expression_override": "vulnerable",
                    "override_expiry_epoch": 200,
                    "scar_layers": [],
                    "presentation_mode": "standard",
                },
            },
            {"soul_id": "alpha", "current_name": "Alpha"},
        ],
        "recent_beats": [
            {
                "speaker": "Alpha",
                "content": "A",
                "move": "ESCALATE",
                "quality_score": 9,
                "energy_label": "hot",
                "timestamp": 1.0,
            },
            {
                "speaker": "Beta",
                "content": "B",
                "move": "COUNTER",
                "quality_score": 10,
                "energy_label": "hot",
                "timestamp": 2.0,
            },
        ],
        "has_the_room": "Beta",
        "scene_energy": "heated",
        "last_dialogue_turn": {
            "sender_name": "Beta",
            "content": "I am here and I am speaking.",
            "move": "ESCALATE",
            "quality_score": 11,
        },
    }

    state = surface.compose(snapshot)

    assert state.plan.expression == "vulnerable"
    assert state.speaker_soul_id == "beta"
    assert state.speaking is True
    assert state.mouth_open > 0
    assert state.presentation_mode == "speaking"
    assert surface._last_scene_layout is not None
    assert surface._last_scene_layout["composition_type"] == "duo"


def test_voice_surface_applies_prosody_tags():
    surface = VoiceSurface(enabled=True, dry_run=True)
    snapshot = {
        "last_dialogue_turn": {
            "sender_name": "Beta",
            "content": "I always get what I want.",
            "move": "CRACK",
            "quality_score": 13,
        },
        "pair_state": {"tension_level": 9, "reconciliation_arc": False},
        "agents": [
            {
                "soul_id": "beta",
                "current_name": "Beta",
                "voice_params": {
                    "prosody_map": {
                        "CRACK": "wounded",
                        "ESCALATE": "emphasis",
                        "CONCEDE": "whisper",
                        "TAUNT": "cold",
                        "SILENCE": "pause",
                    },
                    "supports_prosody_tags": True,
                },
            }
        ],
    }

    state = surface.compose(snapshot)

    assert state.plan.prosody_tag.startswith("[emphasis]")
    assert "[wounded]" in state.plan.line
