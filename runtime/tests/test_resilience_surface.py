"""Resilience and fallback surface tests."""

from resilience import build_resilience_status


def test_resilience_status_reports_local_first_defaults(monkeypatch):
    monkeypatch.delenv("NEMO_ENABLED", raising=False)
    monkeypatch.delenv("NEMO_ENDPOINT", raising=False)
    monkeypatch.delenv("VOICE_ENABLED", raising=False)
    monkeypatch.delenv("TTS_MODEL", raising=False)
    monkeypatch.delenv("TWITCH_EVENTSUB_ENABLED", raising=False)
    monkeypatch.delenv("TWITCH_EVENTSUB_TOKEN", raising=False)
    monkeypatch.delenv("TWITCH_BOT_TOKEN", raising=False)
    monkeypatch.delenv("OBS_ENABLED", raising=False)
    monkeypatch.delenv("OBS_WEBSOCKET_URL", raising=False)

    status = build_resilience_status({"epoch": 100})

    assert status["local_first"] is True
    assert status["tier"] in {"cold-start", "degraded", "warming-up"}
    assert status["fallbacks"]["nemo"] == "stub"
    assert status["fallbacks"]["voice"] == "stub"
    assert status["fallbacks"]["avatar"] == "stub"
    assert status["fallbacks"]["twitch"] == "stub"
    assert status["fallbacks"]["obs"] == "dry-run"
    assert status["snapshot_age_seconds"] >= 0
    assert "adapters" in status
    assert "twitch" in status["adapters"]
    assert "voice" in status["adapters"]
    assert "avatar" in status["adapters"]
    assert "broadcast" in status["adapters"]


def test_resilience_status_exposes_delivery_state():
    status = build_resilience_status()

    assert "epoch" in status
    assert "stream" in status
    assert "subscriber_count" in status["stream"]
    assert "push_age_seconds" in status["stream"]
    assert "restart_safe" in status
