"""Voice surface tests."""

from voice import VoiceSurface, build_voice_state, build_voice_status


def _snapshot() -> dict:
    return {
        "epoch": 123,
        "showrunner": {
            "scene": "banter-table",
            "speaker": "Alpha",
            "headline": "Alpha takes the mic.",
            "audience_prompt": "Watch the exchange.",
        },
        "audience": {
            "patronage_index": 14.0,
        },
        "broadcast": {
            "caption": {
                "headline": "Alpha takes the mic.",
            }
        },
    }


def test_voice_status_exposes_tts_contract():
    status = build_voice_status()

    assert "enabled" in status
    assert "provider" in status
    assert "voice_model" in status
    assert "health" in status


def test_voice_state_layers_from_snapshot():
    state = build_voice_state(_snapshot())

    assert state["plan"]["speaker"] == "Alpha"
    assert state["plan"]["line"] == "Alpha takes the mic."
    assert state["plan"]["emotion"] in {"playful", "charged", "focused"}
    assert state["plan"]["lip_sync_source"]
    assert state["voice_model"]


def test_voice_surface_compose_is_stable():
    surface = VoiceSurface(enabled=True, dry_run=True)
    state = surface.compose(_snapshot())

    assert state.enabled is True
    assert state.plan.speaker == "Alpha"
