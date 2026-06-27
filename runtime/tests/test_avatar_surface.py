"""Avatar surface tests."""

from avatar import AvatarSurface, build_avatar_state, build_avatar_status


def _snapshot() -> dict:
    return {
        "epoch": 456,
        "showrunner": {
            "scene": "ensemble-stage",
            "speaker": "Beta",
            "headline": "Beta closes the deal.",
            "audience_prompt": "Follow the money.",
        },
        "audience": {
            "patronage_index": 7.0,
        },
        "agents": [
            {
                "soul_id": "s-beta",
                "current_name": "Beta",
                "archetype": "trader",
                "avatar_cid": "bafy-avatar",
            }
        ],
        "resilience": {
            "tier": "healthy",
        },
    }


def test_avatar_status_exposes_render_contract():
    status = build_avatar_status()

    assert "enabled" in status
    assert "renderer" in status
    assert "avatar_format" in status
    assert "health" in status


def test_avatar_state_layers_from_snapshot():
    state = build_avatar_state(_snapshot())

    assert state["plan"]["speaker"] == "Beta"
    assert state["plan"]["expression"] in {"focused", "animated", "attentive", "calm", "intense"}
    assert state["plan"]["pose"] in {"lead", "debate", "presenting", "still"}
    assert state["avatar_format"] == "vrm"
    assert set(state["life"]) >= {
        "breathing_phase",
        "blink_state",
        "head_sway_x",
        "head_sway_y",
        "mouth_amplitude",
        "eye_focus_x",
        "eye_focus_y",
    }
    assert state["plan"]["life"] == state["life"]


def test_avatar_surface_compose_is_stable():
    surface = AvatarSurface(enabled=True, dry_run=True)
    state = surface.compose(_snapshot())

    assert state.enabled is True
    assert state.plan.speaker == "Beta"
    assert 0.0 <= state.life["breathing_phase"] <= 1.0


def test_avatar_surface_does_not_use_voice_model_as_visual_fallback(monkeypatch):
    monkeypatch.delenv("AVATAR_ASSET", raising=False)
    monkeypatch.delenv("AVATAR_RIGGED_ASSET", raising=False)
    snapshot = _snapshot()
    snapshot["agents"][0].pop("avatar_cid")
    snapshot["agents"][0]["voice_model_cid"] = "bafy-voice-reference"

    state = AvatarSurface(enabled=True, dry_run=True).compose(snapshot)

    assert state.avatar_asset == ""
    assert state.rigged_avatar_cid == ""
