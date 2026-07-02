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


def test_avatar_status_exposes_render_contract(monkeypatch):
    monkeypatch.delenv("LIVE_EMBODIMENT_ENABLED", raising=False)
    monkeypatch.delenv("EMBODIMENT_ENDPOINT", raising=False)
    monkeypatch.delenv("LIVE_EMBODIMENT_ENDPOINT", raising=False)

    status = build_avatar_status()

    assert "enabled" in status
    assert "renderer" in status
    assert "avatar_format" in status
    assert "health" in status
    assert status["live_embodiment"]["ready"] is False


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


def test_avatar_surface_exposes_live_embodiment_stream_only_when_ready(monkeypatch):
    monkeypatch.setenv("LIVE_EMBODIMENT_ENABLED", "true")
    monkeypatch.setenv(
        "LIVE_EMBODIMENT_STREAM_URL_TEMPLATE",
        "http://embodiment.local/stream/{soul_id}/{utterance_id}.m3u8",
    )
    monkeypatch.setenv("LIVE_EMBODIMENT_PROVIDER", "musetalk")

    def fake_probe(url, timeout=1.5):
        return {
            "ok": True,
            "url": url,
            "body": {"ready": True, "status": "ready", "model_loaded": True},
        }

    monkeypatch.setattr("avatar.live_embodiment.probe_url", fake_probe)
    snapshot = _snapshot()
    snapshot["last_dialogue_turn"] = {
        "sender_name": "Beta",
        "content": "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z.",
    }
    snapshot["voice"] = {
        "plan": {
            "speaker": "Beta",
            "utterance_id": "alphabet-1",
            "audio_rms": 0.3,
        }
    }

    state = AvatarSurface(enabled=True, dry_run=True).compose(snapshot)

    live_video = state.video_manifest["live_video"]
    assert live_video["kind"] == "live"
    assert live_video["provider"] == "musetalk"
    assert live_video["url"] == "http://embodiment.local/stream/s-beta/alphabet-1.m3u8"
    assert state.plan.video_manifest == state.video_manifest
    assert state.live_embodiment["ready"] is True


def test_avatar_surface_does_not_expose_live_video_when_sidecar_is_not_ready(monkeypatch):
    monkeypatch.setenv("LIVE_EMBODIMENT_ENABLED", "true")
    monkeypatch.setenv("LIVE_EMBODIMENT_ENDPOINT", "http://embodiment.local")

    def fake_probe(url, timeout=1.5):
        return {"ok": True, "url": url, "body": {"status": "warming"}}

    monkeypatch.setattr("avatar.live_embodiment.probe_url", fake_probe)
    snapshot = _snapshot()
    snapshot["last_dialogue_turn"] = {"sender_name": "Beta", "content": "hello"}
    snapshot["voice"] = {"plan": {"speaker": "Beta", "utterance_id": "u1"}}

    state = AvatarSurface(enabled=True, dry_run=True).compose(snapshot)

    assert state.video_manifest == {}
    assert state.live_embodiment["ready"] is False
