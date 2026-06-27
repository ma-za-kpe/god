"""Broadcast surface tests."""

from broadcast import BroadcastSurface, build_broadcast_state, build_broadcast_status


def _snapshot() -> dict:
    return {
        "epoch": 789,
        "world_id": "local-dev-world-1",
        "stats": {
            "living_count": 4,
            "events_total": 12,
            "transfers_24h": 3,
            "service_purchases_24h": 2,
            "total_born": 8,
            "total_died": 1,
            "total_usdc_in_world": 44.2,
            "top_earners": [{"current_name": "Alpha"}],
        },
        "audience": {
            "scene": "ensemble-stage",
            "story_hook": "Patrons are funding the cast; reward the room with a stronger turn.",
            "patronage_index": 16.5,
            "chat_pressure": 7,
            "unique_supporters_24h": 4,
            "hype_index": 19.0,
        },
        "content_bank": {
            "bank_id": "bank-123",
            "summary": "3 future arc(s), 3 dialogue beats, 3 scene prompts, focus=patron-funded escalation.",
            "horizon_days": 30,
            "arc_count": 3,
            "dialogue_count": 3,
            "scene_count": 3,
            "clip_count": 3,
            "focus": "patron-funded escalation",
        },
        "showrunner": {
            "scene": "ensemble-stage",
            "speaker": "Alpha",
            "headline": "Alpha: Alpha sells a service to the crowd.",
            "audience_prompt": "Chat can weigh in on the next economic move.",
        },
        "nemo": {
            "scene": "ensemble-stage",
            "speaker": "Alpha",
            "headline": "Alpha: Alpha sells a service to the crowd.",
            "audience_prompt": "Chat can weigh in on the next economic move.",
            "director_note": "Scene ensemble-stage with Alpha on stage.",
        },
        "events": [],
        "messages": [],
        "agents": [],
    }


def test_broadcast_surface_builds_scene_and_caption():
    state = BroadcastSurface(enabled=True).compose(_snapshot())

    assert state.enabled is True
    assert state.dry_run is True
    assert state.scene.scene_id == "obs/ensemble-stage"
    assert state.scene.scene_name == "Ensemble Stage"
    assert state.caption.headline.startswith("Alpha:")
    assert "takes the stage" in state.caption.ticker_lines[0].lower()
    assert "Avatar Stage" == state.overlay.title
    assert len(state.commands) == 3
    assert state.commands[0]["action"] == "set_scene"
    assert len(state.overlay.cards) == 0


def test_broadcast_state_serializes():
    payload = build_broadcast_state(_snapshot())

    assert payload["scene"]["scene_id"] == "obs/ensemble-stage"
    assert payload["caption"]["ticker_lines"][0].startswith("Alpha")
    assert payload["overlay"]["labels"][0] == "avatars"


def test_broadcast_status_reports_dry_run():
    status = build_broadcast_status()

    assert status["dry_run"] is True
    assert status["transport"] == "dry-run"


def test_broadcast_status_probes_obs_websocket_with_tcp(monkeypatch):
    def _fake_probe_tcp(host: str, port: int, timeout: float = 1.5):
        return {"ok": True, "probe": "tcp", "host": host, "port": port, "timeout": timeout}

    monkeypatch.setenv("OBS_WEBSOCKET_URL", "ws://127.0.0.1:4444")
    monkeypatch.setattr("broadcast.obs.probe_tcp", _fake_probe_tcp)

    status = build_broadcast_status()

    assert status["health"]["ok"] is True
    assert status["health"]["probe"] == "websocket_tcp"
    assert status["health"]["url"] == "ws://127.0.0.1:4444"
