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


def test_avatar_surface_compose_is_stable():
    surface = AvatarSurface(enabled=True, dry_run=True)
    state = surface.compose(_snapshot())

    assert state.enabled is True
    assert state.plan.speaker == "Beta"
