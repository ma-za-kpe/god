"""Viewer interaction surface tests."""

from viewer import ViewerSurface, build_viewer_state, build_viewer_status


def _snapshot() -> dict:
    return {
        "epoch": 777,
        "world_id": "local-dev-world-1",
        "stats": {
            "living_count": 6,
            "events_total": 30,
            "service_purchases_24h": 5,
        },
        "audience": {
            "patronage_index": 20.0,
            "raid_waves_24h": 1,
            "chat_pressure": 11,
            "unique_supporters_24h": 6,
            "hype_index": 26.5,
            "story_hook": "Patrons are funding the cast; reward the room with a stronger turn.",
        },
        "content_bank": {
            "summary": "4 future arc(s), 4 dialogue beats, 4 scene prompts, focus=patron-funded escalation.",
            "horizon_days": 30,
            "arc_count": 4,
            "dialogue_count": 4,
            "scene_count": 4,
            "clip_count": 4,
            "focus": "patron-funded escalation",
            "arcs": [
                {
                    "title": "Patrons Raise the Stakes",
                    "trigger": "subscribe_or_gift",
                    "payoff": "A patron-backed turn changes the next scene choice.",
                    "tension": "The room expects the patrons to buy consequences, not just applause.",
                },
                {
                    "title": "Chat Picks a Side",
                    "trigger": "chat_pressure",
                    "payoff": "The argument resolves into a clear winner and loser.",
                    "tension": "Agents can no longer hide behind silence.",
                },
                {
                    "title": "Raid Aftermath",
                    "trigger": "raid",
                    "payoff": "A new scene or hook is opened for the incoming audience.",
                    "tension": "The showrunner must convert surprise into clarity fast enough to retain the raid.",
                },
            ],
        },
        "showrunner": {
            "scene": "market-watch",
            "speaker": "Alpha",
            "headline": "Alpha: The market is moving.",
            "audience_prompt": "Chat can weigh in on the next economic move.",
        },
        "events": [],
        "messages": [],
        "agents": [],
    }


def test_viewer_surface_builds_poll_and_prediction():
    state = ViewerSurface().compose(_snapshot())

    assert state.enabled is True
    assert state.interaction_mode == "poll"
    assert "what should the cast do next" in state.poll["question"].lower()
    assert len(state.options) == 3
    assert state.cards[0]["label"] == "Mode"
    assert state.prediction["question"]
    assert state.commands[0]["action"] == "publish_viewer_overlay"


def test_viewer_state_serializes():
    payload = build_viewer_state(_snapshot())

    assert payload["interaction_mode"] == "poll"
    assert payload["options"][0]["label"] == "Patron-funded arc"
    assert payload["labels"][0] == "viewer"


def test_viewer_status_exposes_supported_interactions():
    status = build_viewer_status()

    assert status["enabled"] is True
    assert "poll" in status["supported_interactions"]
