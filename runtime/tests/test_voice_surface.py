"""Voice surface tests."""

from voice import VoiceSurface, build_voice_state, build_voice_status


def _snapshot() -> dict:
    return {
        "epoch": 123,
        "showrunner": {
            "scene": "ensemble-stage",
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


def _stale_snapshot() -> dict:
    data = _snapshot()
    data["last_dialogue_turn"] = {
        "content": "Useful. I am tired of pretending this does not",
        "sender_name": "Elder-Weave-C9B6",
        "sent_at": 1,
    }
    data["epoch"] = 999
    return data


def test_voice_status_exposes_tts_contract():
    status = build_voice_status()

    assert "enabled" in status
    assert "provider" in status
    assert "voice_model" in status
    assert "playback_mode" in status
    assert "health" in status


def test_voice_state_layers_from_snapshot():
    state = build_voice_state(_snapshot())

    assert state["plan"]["speaker"] == "Alpha"
    assert state["plan"]["line"] == "Watch the exchange."
    assert state["plan"]["emotion"] in {"playful", "charged", "focused"}
    assert state["plan"]["utterance_id"]
    assert state["plan"]["lip_sync_source"]
    assert state["voice_model"]


def test_voice_surface_compose_is_stable():
    surface = VoiceSurface(enabled=True, dry_run=True)
    state = surface.compose(_snapshot())

    assert state.enabled is True
    assert state.plan.speaker == "Alpha"


def test_voice_surface_falls_back_when_dialogue_is_stale():
    surface = VoiceSurface(enabled=True, dry_run=True)
    state = surface.compose(_stale_snapshot())

    assert state.plan.line == "Watch the exchange."


def test_voice_surface_synthesizes_when_tts_is_available(monkeypatch):
    surface = VoiceSurface(enabled=True, dry_run=False)
    snapshot = _snapshot()

    class _Response:
        status_code = 200
        headers = {"content-type": "application/json"}
        content = b'{"audio_url":"http://tts/audio.wav","duration_seconds":1.2}'

        def raise_for_status(self):
            return None

        def json(self):
            return {"audio_url": "http://tts/audio.wav", "duration_seconds": 1.2}

    monkeypatch.setenv("TTS_ENDPOINT", "http://fish-speech:7860")
    monkeypatch.setenv("VOICE_ENABLED", "true")
    monkeypatch.setenv("VOICE_SYNTHESIS_ENABLED", "true")
    monkeypatch.setattr("voice.engine.probe_url", lambda *args, **kwargs: {"ok": True})
    monkeypatch.setattr("voice.engine.httpx.post", lambda *args, **kwargs: _Response())

    state = surface.compose(snapshot)

    assert state.synthesis["ok"] is True
    assert state.synthesis["endpoint"].endswith("/v1/tts")
    assert state.synthesis["audio_url"] == "http://tts/audio.wav"
