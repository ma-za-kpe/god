"""NeMo director and guardrail tests."""

from nemo import NemoGuardrails, NemoMemory, build_nemo_directive, build_nemo_status
from nemo.client import NemoClient
from nemo.director import NemoDirector


def _snapshot() -> dict:
    return {
        "epoch": 456,
        "agent_count": 2,
        "stats": {
            "living_count": 2,
            "events_total": 9,
            "transfers_24h": 3,
            "service_purchases_24h": 1,
            "avg_balance": 1.5,
        },
        "events": [
            {
                "event_id": "evt-a",
                "event_type": "economy.service.purchased",
                "agent_id": "s-alpha",
                "payload": {
                    "name": "Alpha",
                    "narrative": "Alpha sells a service to the crowd.",
                },
            },
            {
                "event_id": "evt-b",
                "event_type": "social.agent.broadcast",
                "agent_id": "s-beta",
                "payload": {
                    "name": "Beta",
                    "content": "Stay tuned.",
                },
            },
        ],
        "messages": [],
        "agents": [
            {"soul_id": "s-alpha", "current_name": "Alpha"},
            {"soul_id": "s-beta", "current_name": "Beta"},
        ],
        "showrunner": {
            "scene": "economy-pan",
            "speaker": "Alpha",
            "headline": "Alpha: Alpha sells a service to the crowd.",
            "audience_prompt": "Chat can weigh in on the next economic move.",
            "cues": [
                {
                    "cue_type": "economy.service.purchased",
                    "headline": "Alpha sells a service to the crowd.",
                    "tags": ["economy"],
                }
            ],
            "reasoning": ["scene=economy-pan", "speaker=Alpha"],
        },
    }


def test_nemo_directive_builds_from_snapshot():
    directive = build_nemo_directive(_snapshot())

    assert directive["guardrail_status"] == "ok"
    assert directive["scene"] == "economy-pan"
    assert directive["speaker"] == "Alpha"
    assert "Summary:" in directive["director_note"]
    assert "prompt" in directive
    assert "memory" in directive
    assert directive["status"]["enabled"] is True


def test_nemo_guardrails_block_action_leaks():
    rails = NemoGuardrails()
    result = rails.validate('{"action":"send_message","content":"hi"}', _snapshot())

    assert not result.ok
    assert result.reason


def test_nemo_memory_updates_summary():
    memory = NemoMemory()
    summary = memory.update(_snapshot(), headline="Alpha takes the lead")

    assert "living=2" in summary
    assert "headline=Alpha takes the lead" in summary
    assert memory.last_event_ids == ["evt-a", "evt-b"]


def test_nemo_client_status_matches_config():
    status = build_nemo_status()
    client = NemoClient()

    assert client.status() == status
    assert status["provider"] == "stub"
    assert "guardrails" in status


def test_nemo_director_compose_is_structured():
    director = NemoDirector()
    directive = director.compose(_snapshot(), _snapshot()["showrunner"])

    assert directive["mode"] == "director"
    assert directive["guardrail_status"] == "ok"
    assert directive["summary"]
