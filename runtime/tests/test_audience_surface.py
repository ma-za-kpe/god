"""Audience/patronage surface tests."""

from audience import AudienceSurface, build_audience_state, build_audience_status


def _snapshot() -> dict:
    return {
        "epoch": 321,
        "world_id": "local-dev-world-1",
        "stats": {
            "living_count": 4,
            "events_total": 14,
            "service_purchases_24h": 2,
        },
        "events": [
            {
                "event_id": "chat-1",
                "event_type": "social.twitch.chat.message",
                "payload": {"user_name": "viewer_one", "message": "do it"},
                "narrative": "viewer_one asks for chaos.",
            },
            {
                "event_id": "sub-1",
                "event_type": "economy.twitch.subscribe",
                "payload": {"user_name": "viewer_two"},
                "narrative": "viewer_two becomes a patron.",
            },
            {
                "event_id": "raid-1",
                "event_type": "social.twitch.raid",
                "payload": {"user_name": "raider", "viewer_count": 42},
                "narrative": "raider arrives with a crowd.",
            },
        ],
        "messages": [],
        "agents": [],
        "showrunner": {"scene": "market-watch"},
    }


def test_audience_surface_turns_twitch_events_into_story_pressure():
    state = AudienceSurface().compose(_snapshot())

    assert state.scene == "market-watch"
    assert state.patronage_index > 8
    assert state.chat_pressure == 1
    assert state.raid_waves_24h == 1
    assert "patron" in state.story_hook.lower()
    assert state.cards[0]["label"] == "Patronage"


def test_audience_state_serializes():
    payload = build_audience_state(_snapshot())

    assert payload["scene"] == "market-watch"
    assert payload["unique_supporters_24h"] == 3
    assert payload["commands"][0]["action"] == "set_audience_hook"


def test_audience_status_exposes_supported_events():
    status = build_audience_status()

    assert status["enabled"] is True
    assert "economy.twitch.subscribe" in status["supported_event_types"]
