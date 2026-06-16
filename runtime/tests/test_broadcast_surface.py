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
            "scene": "market-watch",
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
            "scene": "economy-pan",
            "speaker": "Alpha",
            "headline": "Alpha: Alpha sells a service to the crowd.",
            "audience_prompt": "Chat can weigh in on the next economic move.",
        },
        "nemo": {
            "scene": "economy-pan",
            "speaker": "Alpha",
            "headline": "Alpha: Alpha sells a service to the crowd.",
            "audience_prompt": "Chat can weigh in on the next economic move.",
            "director_note": "Scene economy-pan with Alpha on stage.",
        },
        "events": [],
        "messages": [],
        "agents": [],
    }


def test_broadcast_surface_builds_scene_and_caption():
    state = BroadcastSurface().compose(_snapshot())

    assert state.enabled is True
    assert state.dry_run is True
    assert state.scene.scene_id == "obs/economy-pan"
    assert state.scene.scene_name == "Economy Pan"
    assert state.caption.headline.startswith("Alpha:")
    assert "future arc" in state.caption.ticker_lines[-1].lower()
    assert "future arc" in state.overlay.cards[8]["label"].lower()
    assert "Live Stage" == state.overlay.title
    assert len(state.commands) == 3
    assert state.commands[0]["action"] == "set_scene"
    assert state.overlay.cards[5]["label"] == "Patrons"


def test_broadcast_state_serializes():
    payload = build_broadcast_state(_snapshot())

    assert payload["scene"]["scene_id"] == "obs/economy-pan"
    assert payload["caption"]["ticker_lines"][-1].startswith("Future arcs")
    assert payload["overlay"]["labels"][0] == "Economy Pan"


def test_broadcast_status_reports_dry_run():
    status = build_broadcast_status()

    assert status["dry_run"] is True
    assert status["transport"] == "dry-run"
