"""Grounding validation tests — issue #53."""

from grounding import (
    check_hallucination,
    grounded_fallback,
    looks_like_action_json,
    validate_grounded_text,
)

_FIELD_ROSTER_STATE = {
    "name": "Elder-Build-0F13",
    "archetype": "builder",
    "balance_usdc": 2.29,
    "rent_amount": 0.001,
    "peers": [
        {"name": "Elder-Lore-BD30", "soul_id": "a100c07a-5b17-42e3-a92d-46c9081baf15"},
        {"name": "Elder-Merch-8161", "soul_id": "79587ccb-c2ee-4b2d-bae7-f7e6e262db24"},
    ],
    "inbox": [],
}


def test_rejects_riverbed_bridge_fiction():
    text = (
        "I am currently constructing the 'Riverbed Bridge' connecting two segments of "
        "Elder-Lore-BD30's network to improve inter-network data transmission efficiency."
    )
    ok, reason = check_hallucination(text)
    assert not ok
    assert reason.startswith("invented concept:")


def test_rejects_aurora_net_fiction():
    text = "I am constructing the 'Aurora Net' for data transmission between trusted agents."
    ok, reason = check_hallucination(text)
    assert not ok


def test_rejects_unknown_agent_reference():
    text = "I am building Elder-Tier, a reputation-based rating system for the world."
    ok, reason = validate_grounded_text(text, _FIELD_ROSTER_STATE)
    assert not ok
    assert reason.startswith("invented concept:") or "unknown agent" in reason


def test_rejects_json_leaked_into_thought():
    samples = [
        '( "action": "send_message", "to_id": "Elder-Store-E66C", "content": "join coalition")',
        '{"action": "send_broadcast", "content": "verify all proposals"}',
        '{"thought": "hi", "action": "send_message", "to_id": "x"}',
    ]
    for text in samples:
        assert looks_like_action_json(text)
        ok, reason = validate_grounded_text(text, _FIELD_ROSTER_STATE)
        assert not ok
        assert "json" in reason.lower()


def test_accepts_grounded_builder_thought():
    text = (
        "I am reviewing listed services and considering register_service for a small tool "
        "Elder-Merch-8161 might buy."
    )
    ok, _ = validate_grounded_text(text, _FIELD_ROSTER_STATE)
    assert ok


def test_builder_fallback_mentions_real_mechanics():
    thought = grounded_fallback(_FIELD_ROSTER_STATE)
    assert "service" in thought.lower() or "message" in thought.lower()
    assert "bridge" not in thought.lower()
    assert "protocol" not in thought.lower()


def test_malformed_action_leak_has_no_usable_thought():
    raw = '( "action": "send_message", "to_id": "Elder-Store-E66C", "content": "offer")'
    assert looks_like_action_json(raw)
    ok, reason = validate_grounded_text(raw, _FIELD_ROSTER_STATE)
    assert not ok
    assert "json" in reason.lower()
