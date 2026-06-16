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


def test_showrunner_prefers_highest_signal_event():
    plan = Showrunner().build_plan(_snapshot())

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
    first = runner.build_plan(_snapshot())
    second = runner.build_plan(_snapshot())

    assert first.to_dict() == second.to_dict()


def test_showrunner_public_bank_prompt_tracks_economy():
    plan = build_showrunner_plan(_snapshot())

    economy_plan = build_showrunner_plan(_economy_snapshot())
    assert "economic move" in economy_plan["audience_prompt"]
    assert economy_plan["cues"][0]["cue_type"] == "economy.service.purchased"
