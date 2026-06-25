"""Showrunner planning tests."""

from showrunner import Showrunner, build_showrunner_plan


def _snapshot() -> dict:
    return {
        "epoch": 123,
        "agent_count": 3,
        "stats": {
            "living_count": 3,
            "events_total": 8,
            "transfers_24h": 2,
            "service_purchases_24h": 1,
        },
        "events": [
            {
                "event_id": "evt-1",
                "event_type": "economy.service.purchased",
                "agent_id": "s-merchant",
                "payload": {
                    "name": "Merchant-One",
                    "narrative": "Merchant-One sells the crowd a tool.",
                    "content": "Paid for a service.",
                },
            },
            {
                "event_id": "evt-2",
                "event_type": "lifecycle.agent.died",
                "agent_id": "s-fallen",
                "payload": {
                    "name": "Fallen-Host",
                    "archetype": "builder",
                    "missed_payments": 3,
                    "narrative": "Fallen-Host dies after rent failure.",
                },
            },
            {
                "event_id": "evt-3",
                "event_type": "social.agent.broadcast",
                "agent_id": "s-chatty",
                "payload": {
                    "name": "Chatty-One",
                    "content": "We should all watch this.",
                },
            },
        ],
        "messages": [],
        "agents": [],
    }


def _snapshot_with_agent_names() -> dict:
    snap = _snapshot()
    snap["agents"] = [
        {"soul_id": "s-fallen", "current_name": "Fallen-Host"},
        {"soul_id": "s-merchant", "current_name": "Merchant-One"},
        {"soul_id": "s-chatty", "current_name": "Chatty-One"},
    ]
    return snap


def _economy_snapshot() -> dict:
    snap = _snapshot()
    snap["events"] = [
        {
            "event_id": "evt-1",
            "event_type": "economy.service.purchased",
            "agent_id": "s-merchant",
            "payload": {
                "name": "Merchant-One",
                "narrative": "Merchant-One sells the crowd a tool.",
                "content": "Paid for a service.",
            },
        }
    ]
    return snap


def _audience_snapshot() -> dict:
    snap = _snapshot()
    snap["events"] = [
        {
            "event_id": "evt-1",
            "event_type": "economy.twitch.subscribe",
            "agent_id": "viewer_two",
            "payload": {
                "user_name": "viewer_two",
                "narrative": "viewer_two becomes a patron.",
            },
        },
        {
            "event_id": "evt-2",
            "event_type": "social.twitch.chat.message",
            "agent_id": "viewer_one",
            "payload": {
                "user_name": "viewer_one",
                "message": "keep going",
                "narrative": "viewer_one pushes the room forward.",
            },
        },
    ]
    return snap


def test_showrunner_prefers_highest_signal_event():
    plan = Showrunner().build_plan(_snapshot_with_agent_names())

    assert plan.mode == "live-weave"
    assert plan.scene == "graveyard-cut"
    assert plan.speaker == "Fallen-Host"
    assert plan.headline.startswith("Fallen-Host:")
    assert plan.source_epoch == 123
    assert plan.source_agent_count == 3
    assert "scene=graveyard-cut" in plan.reasoning
    assert "top_cue=lifecycle.agent.died" in plan.reasoning


def test_showrunner_is_deterministic_for_same_snapshot():
    runner = Showrunner()
    first = runner.build_plan(_snapshot_with_agent_names())
    second = runner.build_plan(_snapshot_with_agent_names())

    assert first.to_dict() == second.to_dict()


def test_showrunner_public_bank_prompt_tracks_economy():
    economy_snapshot = _economy_snapshot()
    economy_snapshot["agents"] = [{"soul_id": "s-merchant", "current_name": "Merchant-One"}]
    economy_plan = build_showrunner_plan(economy_snapshot)
    assert "economic move" in economy_plan["audience_prompt"]
    assert economy_plan["cues"][0]["cue_type"] == "economy.service.purchased"


def test_showrunner_audience_state_changes_scene_prompt():
    snap = _audience_snapshot()
    snap["agents"] = [
        {"soul_id": "viewer_two", "current_name": "viewer_two"},
        {"soul_id": "viewer_one", "current_name": "viewer_one"},
    ]
    snap["audience"] = {
        "patronage_index": 16.0,
        "chat_pressure": 1,
        "raid_waves_24h": 0,
    }
    plan = build_showrunner_plan(snap)

    assert plan["scene"] == "ensemble-stage"
    assert "patrons are funding" in plan["audience_prompt"].lower()


def test_showrunner_cleans_reply_metadata_from_message_headlines():
    snap = _snapshot()
    snap["agents"] = [{"soul_id": "s-explorer", "current_name": "Elder-Drift-A505"}]
    snap["events"] = [
        {
            "event_id": "evt-1",
            "event_type": "social.agent.message_sent",
            "agent_id": "s-explorer",
            "payload": {
                "name": "Elder-Drift-A505",
                "content": "If you mean that seriously, explain: Elder-Drift-A505 (explorer). said: I'd like to discuss the underlying dynamics that enable my persistence. theme: Can a Coalition of Rivals Outlast a World of Individuals?",
            },
        }
    ]

    plan = build_showrunner_plan(snap)

    assert "said:" not in plan["headline"].lower()
    assert "theme:" not in plan["headline"].lower()
    assert "underlying dynamics" in plan["headline"].lower()
