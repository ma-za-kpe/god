"""Voice surface tests."""

from __future__ import annotations

import io
import math
import struct
import time
import wave

from voice import VoiceSurface, build_voice_state, build_voice_status
from voice.engine import _CachedHealthProbe, _audio_cache, _synthesis_cache


def _clear_voice_caches() -> None:
    _synthesis_cache.clear()
    _audio_cache.clear()


def _wav_bytes(*, amplitude: float = 0.45, seconds: float = 0.05, sample_rate: int = 8000) -> bytes:
    frames = int(sample_rate * seconds)
    with io.BytesIO() as buf:
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            for idx in range(frames):
                sample = int(32767 * amplitude * math.sin(2 * math.pi * 440 * idx / sample_rate))
                wav.writeframesraw(struct.pack("<h", sample))
        return buf.getvalue()


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
    assert status["phoneme_output"] is False
    assert status["voice_reference_semantics"] == "fish_reference_wav_cid"
    assert status["voice_model_semantics"] == "tts_backend_model_name"


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


def test_voice_surface_accepts_string_metadata_on_dialogue_turn():
    surface = VoiceSurface(enabled=True, dry_run=True)
    snapshot = _snapshot()
    snapshot["epoch"] = 200
    snapshot["last_dialogue_turn"] = {
        "content": "This line should still synthesize.",
        "sender_name": "Alpha",
        "sent_at": 199,
        "metadata": '{"move":"probe","cadence":"short"}',
    }

    state = surface.compose(snapshot)

    assert state.plan.speaker == "Alpha"
    assert state.plan.line == "This line should still synthesize."
    assert "move=PROBE" in state.plan.notes


def test_voice_surface_falls_back_when_dialogue_is_stale():
    surface = VoiceSurface(enabled=True, dry_run=True)
    state = surface.compose(_stale_snapshot())

    assert state.plan.line == "Watch the exchange."


def test_voice_surface_keeps_stale_one_alphabet_drill():
    surface = VoiceSurface(enabled=True, dry_run=True)
    snapshot = _snapshot()
    snapshot["epoch"] = 999
    snapshot["last_dialogue_turn"] = {
        "content": "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z.",
        "sender_name": "Alpha",
        "sent_at": 1,
    }

    state = surface.compose(snapshot)

    assert state.plan.speaker == "Alpha"
    assert state.plan.line == "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z."


def test_voice_surface_synthesizes_when_tts_is_available(monkeypatch):
    _clear_voice_caches()
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
    assert state.synthesis["mouth_amplitude"] > 0
    assert state.synthesis["audio_analysis"]["reason"] == "external_audio_url"
    assert state.synthesis["lip_sync"]["phoneme_output"] is False


def test_voice_surface_analyzes_fish_audio_for_mouth_amplitude(monkeypatch):
    _clear_voice_caches()
    surface = VoiceSurface(enabled=True, dry_run=False)
    snapshot = _snapshot()
    wav_audio = _wav_bytes(amplitude=0.6)

    class _OllamaResponse:
        status_code = 200
        headers = {"content-type": "application/json"}
        content = b"{}"

        def raise_for_status(self):
            return None

    class _AudioResponse:
        status_code = 200
        headers = {"content-type": "audio/wav"}
        content = wav_audio

        def raise_for_status(self):
            return None

    def _post(url, *args, **kwargs):
        if str(url).endswith("/v1/tts"):
            return _AudioResponse()
        return _OllamaResponse()

    monkeypatch.setenv("TTS_ENDPOINT", "http://fish-speech:7860")
    monkeypatch.setenv("VOICE_ENABLED", "true")
    monkeypatch.setenv("VOICE_SYNTHESIS_ENABLED", "true")
    monkeypatch.setattr("voice.engine.probe_url", lambda *args, **kwargs: {"ok": True})
    monkeypatch.setattr("voice.engine.httpx.post", _post)

    state = surface.compose(snapshot)

    assert state.synthesis["ok"] is True
    assert state.synthesis["audio_present"] is True
    assert state.synthesis["audio_rms"] > 0
    assert state.synthesis["audio_peak"] > 0
    assert state.synthesis["mouth_amplitude"] > state.synthesis["audio_rms"]
    assert state.synthesis["audio_analysis"]["ok"] is True
    assert _audio_cache[state.plan.utterance_id] == wav_audio


def test_voice_surface_uses_cached_audio_when_health_probe_flakes(monkeypatch):
    _clear_voice_caches()
    snapshot = _snapshot()
    wav_audio = _wav_bytes(amplitude=0.5)

    class _OllamaResponse:
        status_code = 200
        headers = {"content-type": "application/json"}
        content = b"{}"

        def raise_for_status(self):
            return None

    class _AudioResponse:
        status_code = 200
        headers = {"content-type": "audio/wav"}
        content = wav_audio

        def raise_for_status(self):
            return None

    def _post(url, *args, **kwargs):
        if str(url).endswith("/v1/tts"):
            return _AudioResponse()
        return _OllamaResponse()

    monkeypatch.setenv("TTS_ENDPOINT", "http://fish-speech:7860")
    monkeypatch.setenv("VOICE_ENABLED", "true")
    monkeypatch.setenv("VOICE_SYNTHESIS_ENABLED", "true")
    monkeypatch.setattr("voice.engine.probe_url", lambda *args, **kwargs: {"ok": True})
    monkeypatch.setattr("voice.engine.httpx.post", _post)

    first = VoiceSurface(enabled=True, dry_run=False).compose(snapshot)
    assert first.synthesis["ok"] is True
    assert first.synthesis["audio_present"] is True

    def _unexpected_post(*args, **kwargs):
        raise AssertionError("cached synthesis should not call the TTS endpoint")

    monkeypatch.setattr(
        "voice.engine.probe_url",
        lambda *args, **kwargs: {"ok": False, "reason": "timeout"},
    )
    monkeypatch.setattr("voice.engine.httpx.post", _unexpected_post)

    second = VoiceSurface(enabled=True, dry_run=False).compose(snapshot)

    assert second.health["ok"] is False
    assert second.synthesis["ok"] is True
    assert second.synthesis["audio_present"] is True
    assert second.synthesis["endpoint"].endswith("/v1/tts")
    assert _audio_cache[second.plan.utterance_id] == wav_audio


def test_cached_health_probe_keeps_recent_success_after_single_failure(monkeypatch):
    monkeypatch.setenv("VOICE_HEALTH_FAILURE_GRACE_SECONDS", "30")
    probe = _CachedHealthProbe(ttl=0.0)

    monkeypatch.setattr(
        "voice.engine.probe_url",
        lambda *args, **kwargs: {"ok": True, "probe": "http", "url": "http://fish/health"},
    )
    probe._refresh("http://fish/health", timeout=0.01)
    assert probe._cached_result["ok"] is True

    monkeypatch.setattr(
        "voice.engine.probe_url",
        lambda *args, **kwargs: {"ok": False, "reason": "timeout", "url": "http://fish/health"},
    )
    probe._refresh("http://fish/health", timeout=0.01)
    assert probe._cached_result["ok"] is True
    assert probe._cached_result["stale_after_failure"] is True
    assert probe._cached_result["last_failure"]["reason"] == "timeout"

    probe._last_success_time = time.monotonic() - 31.0
    probe._refresh("http://fish/health", timeout=0.01)
    assert probe._cached_result["ok"] is False
    assert probe._cached_result["reason"] == "timeout"


def test_voice_reference_failure_reports_philosopher_fallback(monkeypatch):
    _clear_voice_caches()
    surface = VoiceSurface(enabled=True, dry_run=False)
    snapshot = _snapshot()
    snapshot["epoch"] = 200
    snapshot["agents"] = [
        {
            "soul_id": "agent-alpha",
            "current_name": "Alpha",
            "archetype": "unknown-archetype",
            "voice_model_cid": "bafybadreference",
        }
    ]
    snapshot["last_dialogue_turn"] = {
        "content": "I need the fallback to keep talking.",
        "sender_name": "Alpha",
        "sender_soul_id": "agent-alpha",
        "sent_at": 199,
    }

    class _RefFailure:
        status_code = 500
        headers = {"content-type": "text/plain"}
        content = b""

        def raise_for_status(self):
            return None

    class _OllamaResponse:
        status_code = 200
        headers = {"content-type": "application/json"}
        content = b"{}"

        def raise_for_status(self):
            return None

    class _SynthesisResponse:
        status_code = 200
        headers = {"content-type": "application/json"}
        content = b'{"audio_url":"http://tts/fallback.wav"}'

        def raise_for_status(self):
            return None

        def json(self):
            return {"audio_url": "http://tts/fallback.wav"}

    def _post(url, *args, **kwargs):
        text = str(url)
        if text.endswith("/api/v0/cat"):
            return _RefFailure()
        if text.endswith("/v1/tts"):
            return _SynthesisResponse()
        return _OllamaResponse()

    monkeypatch.setenv("TTS_ENDPOINT", "http://fish-speech:7860")
    monkeypatch.setenv("VOICE_ENABLED", "true")
    monkeypatch.setenv("VOICE_SYNTHESIS_ENABLED", "true")
    monkeypatch.setattr("voice.engine.probe_url", lambda *args, **kwargs: {"ok": True})
    monkeypatch.setattr("voice.engine.httpx.post", _post)

    state = surface.compose(snapshot)

    reference = state.synthesis["reference_audio"]
    assert state.synthesis["ok"] is True
    assert reference["source"] == "philosopher_seed_wav"
    assert reference["fallback_used"] is True
    assert reference["failure_reason"] == "cid_fetch_status:500"
    assert reference["semantics"] == "reference_wav"
    assert reference["legacy_field"] == "voice_model_cid"
