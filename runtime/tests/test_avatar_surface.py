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
    assert state["body_motion"]["source"] == "ai4animationpy-contract"
    assert state["body_motion"]["target_runtime"] == "ai4animationpy"
    assert state["plan"]["body_motion"] == state["body_motion"]


def test_avatar_surface_compose_is_stable():
    surface = AvatarSurface(enabled=True, dry_run=True)
    state = surface.compose(_snapshot())

    assert state.enabled is True
    assert state.plan.speaker == "Beta"
    assert 0.0 <= state.life["breathing_phase"] <= 1.0
    assert state.body_motion["source"] == "ai4animationpy-contract"
    assert state.body_motion["status"] == "idle"
    assert any(command.get("name") == "idle_shift" for command in state.body_motion["commands"])


def test_avatar_surface_body_motion_tracks_speaking_alphabet():
    snapshot = _snapshot()
    snapshot["last_dialogue_turn"] = {
        "sender_name": "Beta",
        "content": "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z.",
    }
    snapshot["voice"] = {
        "plan": {
            "speaker": "Beta",
            "utterance_id": "alphabet-1",
            "line": "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z.",
        },
        "synthesis": {"ok": True, "duration_seconds": 6.0},
    }

    state = AvatarSurface(enabled=True, dry_run=True).compose(snapshot)

    assert state.speaking is True
    assert state.body_motion["source"] == "ai4animationpy-contract"
    assert state.body_motion["status"] == "ready"
    assert any(command["type"] == "walk_to" for command in state.body_motion["commands"])
    assert any(
        command.get("name") == "counting_left_hand" for command in state.body_motion["commands"]
    )


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
        },
        "synthesis": {"ok": True, "audio_present": True},
    }

    state = AvatarSurface(enabled=True, dry_run=True).compose(snapshot)

    live_video = state.video_manifest["live_video"]
    assert live_video["kind"] == "live"
    assert live_video["provider"] == "musetalk"
    assert live_video["url"] == "http://embodiment.local/stream/s-beta/alphabet-1.m3u8"
    assert state.plan.video_manifest == state.video_manifest
    assert state.live_embodiment["ready"] is True


def test_avatar_surface_queues_live_embodiment_for_fish_audio(monkeypatch):
    from avatar import live_embodiment

    live_embodiment._ENSURE_CACHE.clear()
    monkeypatch.setenv("LIVE_EMBODIMENT_ENABLED", "true")
    monkeypatch.setenv("LIVE_EMBODIMENT_ENDPOINT", "http://embodiment.local")
    monkeypatch.setenv("LIVE_EMBODIMENT_RUNTIME_BASE_URL", "http://runtime.local")
    monkeypatch.setenv("LIVE_EMBODIMENT_ENSURE_INLINE", "true")
    monkeypatch.setenv("LIVE_EMBODIMENT_ENSURE_TTL_S", "0")

    def fake_probe(url, timeout=1.5):
        return {
            "ok": True,
            "url": url,
            "body": {"ready": True, "status": "ready", "model_loaded": True},
        }

    calls = []

    def fake_post_json(url, payload, timeout):
        calls.append((url, payload, timeout))
        return {"ok": True, "status": 202, "body": {"ok": True}}

    monkeypatch.setattr("avatar.live_embodiment.probe_url", fake_probe)
    monkeypatch.setattr("avatar.live_embodiment.post_json", fake_post_json)
    snapshot = _snapshot()
    snapshot["last_dialogue_turn"] = {"sender_name": "Beta", "content": "A B C."}
    snapshot["voice"] = {
        "plan": {"speaker": "Beta", "utterance_id": "alphabet-1"},
        "synthesis": {"ok": True, "audio_present": True},
    }

    state = AvatarSurface(enabled=True, dry_run=True).compose(snapshot)

    assert state.video_manifest["live_video"]["kind"] == "live"
    assert len(calls) == 1
    url, payload, timeout = calls[0]
    assert url == "http://embodiment.local/embody"
    assert timeout == 1.5
    assert payload["soul_id"] == "s-beta"
    assert payload["utterance_id"] == "alphabet-1"
    assert payload["audio_url"] == "http://runtime.local/voice/audio/alphabet-1"
    assert payload["portrait_url"] == "http://runtime.local/ipfs/bafy-avatar"
    assert payload["portrait_cid"] == "bafy-avatar"
    assert payload["blocking"] is False


def test_avatar_surface_keeps_live_video_available_after_speaking_window(monkeypatch):
    from avatar import live_embodiment

    live_embodiment._ENSURE_CACHE.clear()
    monkeypatch.setenv("LIVE_EMBODIMENT_ENABLED", "true")
    monkeypatch.setenv("LIVE_EMBODIMENT_ENDPOINT", "http://embodiment.local")
    monkeypatch.setenv(
        "LIVE_EMBODIMENT_STREAM_URL_TEMPLATE",
        "http://embodiment.local/stream/{soul_id}/{utterance_id}.mp4",
    )
    monkeypatch.setenv("LIVE_EMBODIMENT_RUNTIME_BASE_URL", "http://runtime.local")
    monkeypatch.setenv("LIVE_EMBODIMENT_ENSURE_INLINE", "true")
    monkeypatch.setenv("LIVE_EMBODIMENT_ENSURE_TTL_S", "0")

    def fake_probe(url, timeout=1.5):
        return {
            "ok": True,
            "url": url,
            "body": {"ready": True, "status": "ready", "model_loaded": True},
        }

    calls = []

    def fake_post_json(url, payload, timeout):
        calls.append(payload)
        return {"ok": True, "status": 202, "body": {"ok": True}}

    monkeypatch.setattr("avatar.live_embodiment.probe_url", fake_probe)
    monkeypatch.setattr("avatar.live_embodiment.post_json", fake_post_json)
    snapshot = _snapshot()
    snapshot["last_dialogue_turn"] = {}
    snapshot["voice"] = {
        "plan": {"speaker": "Beta", "utterance_id": "alphabet-1"},
        "synthesis": {"ok": True, "audio_present": True},
    }

    state = AvatarSurface(enabled=True, dry_run=True).compose(snapshot)

    assert state.speaking is False
    assert state.video_manifest["live_video"]["kind"] == "live"
    assert state.video_manifest["live_video"]["url"].endswith("/s-beta/alphabet-1.mp4")
    assert calls[0]["audio_url"] == "http://runtime.local/voice/audio/alphabet-1"


def test_avatar_surface_does_not_keep_stale_turn_speaking(monkeypatch):
    snapshot = _snapshot()
    snapshot["epoch"] = 1_000
    snapshot["last_dialogue_turn"] = {
        "sender_name": "Beta",
        "content": "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z.",
        "sent_at": 900,
    }
    snapshot["voice"] = {
        "plan": {"speaker": "Beta", "utterance_id": "alphabet-1"},
        "synthesis": {"ok": True, "audio_present": True, "duration_seconds": 8.0},
    }

    state = AvatarSurface(enabled=True, dry_run=True).compose(snapshot)

    assert state.speaking is False
    assert state.presentation_mode == "listening"
    assert state.life["mouth_amplitude"] == 0.0


def test_avatar_surface_requires_real_audio_before_live_video(monkeypatch):
    monkeypatch.setenv("LIVE_EMBODIMENT_ENABLED", "true")
    monkeypatch.setenv("LIVE_EMBODIMENT_ENDPOINT", "http://embodiment.local")

    def fake_probe(url, timeout=1.5):
        return {
            "ok": True,
            "url": url,
            "body": {"ready": True, "status": "ready", "model_loaded": True},
        }

    monkeypatch.setattr("avatar.live_embodiment.probe_url", fake_probe)
    snapshot = _snapshot()
    snapshot["last_dialogue_turn"] = {"sender_name": "Beta", "content": "A B C."}
    snapshot["voice"] = {"plan": {"speaker": "Beta", "utterance_id": "alphabet-1"}}

    state = AvatarSurface(enabled=True, dry_run=True).compose(snapshot)

    assert state.video_manifest == {}
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
