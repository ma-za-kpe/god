"""Twitch adapter tests."""

import pytest

from twitch.adapter import TwitchAdapter, build_twitch_status, normalize_twitch_event
from twitch.models import TwitchChatMessage


def test_normalizes_chat_message():
    event = normalize_twitch_event(
        "channel.chat.message",
        {
            "channel_name": "godshow",
            "user_name": "viewer_one",
            "user_id": "u1",
            "message": "hello world",
        },
    )

    assert event is not None
    assert event.event_type == "channel.chat.message"
    assert event.channel_name == "godshow"
    assert event.user_name == "viewer_one"


def test_ingest_chat_becomes_world_event(monkeypatch):
    monkeypatch.setattr("twitch.adapter._register_replay_key", lambda *args, **kwargs: True)
    adapter = TwitchAdapter(channel_name="godshow", dry_run=True)
    world_event = adapter.ingest(
        "channel.chat.message",
        {
            "channel_name": "godshow",
            "user_name": "viewer_one",
            "user_id": "u1",
            "message": "raid when",
        },
    )

    assert world_event is not None
    assert world_event["category"] == "social"
    assert world_event["event_type"] == "social.twitch.chat.message"
    assert "viewer_one" in world_event["narrative"]
    assert world_event["payload"]["platform"] == "twitch"
    assert world_event["payload"]["presentation"]["route"] == "showrunner"
    assert world_event["payload"]["presentation"]["direct_effects"] == []
    assert world_event["payload"]["rate_limit"]["bucket"] == "twitch:godshow:u1:chat"


def test_ingest_subscribe_becomes_patronage_event(monkeypatch):
    monkeypatch.setattr("twitch.adapter._register_replay_key", lambda *args, **kwargs: True)
    adapter = TwitchAdapter(channel_name="godshow", dry_run=True)
    world_event = adapter.ingest(
        "channel.subscribe",
        {
            "channel_name": "godshow",
            "user_name": "viewer_two",
            "user_id": "u2",
        },
    )

    assert world_event is not None
    assert world_event["category"] == "economy"
    assert world_event["event_type"] == "economy.twitch.subscribe"
    assert (
        "patron" in world_event["narrative"].lower()
        or "subscribed" in world_event["narrative"].lower()
    )


@pytest.mark.asyncio
async def test_send_chat_defaults_to_dry_run():
    adapter = TwitchAdapter(channel_name="godshow", dry_run=True)
    result = await adapter.send_chat(TwitchChatMessage(message="go live", channel_name="godshow"))

    assert result.ok
    assert result.dry_run
    assert result.reason == "dry_run"


def test_status_reflects_support():
    status = build_twitch_status()

    assert "supported_event_types" in status
    assert "channel.chat.message" in status["supported_event_types"]
    assert "health" in status
    assert status["platform_boundary"]["route"] == "showrunner"
    assert status["platform_boundary"]["direct_effects_allowed"] is False
    assert "bot_identity" in status


def test_ingest_rejects_duplicate_replay(monkeypatch):
    adapter = TwitchAdapter(channel_name="godshow", dry_run=True)

    calls = iter([True, False])

    monkeypatch.setattr("twitch.adapter._register_replay_key", lambda *args, **kwargs: next(calls))

    first = adapter.ingest(
        "channel.chat.message",
        {
            "channel_name": "godshow",
            "user_name": "viewer_one",
            "user_id": "u1",
            "message": "hello again",
            "event_id": "evt-1",
        },
    )
    second = adapter.ingest(
        "channel.chat.message",
        {
            "channel_name": "godshow",
            "user_name": "viewer_one",
            "user_id": "u1",
            "message": "hello again",
            "event_id": "evt-1",
        },
    )

    assert first is not None
    assert second is None


def test_replay_key_is_stable_for_eventsub_duplicate_payloads(monkeypatch):
    monkeypatch.setattr("twitch.adapter._register_replay_key", lambda *args, **kwargs: True)
    adapter = TwitchAdapter(channel_name="godshow", dry_run=True)
    payload = {
        "channel_name": "godshow",
        "user_name": "viewer_one",
        "user_id": "u1",
        "message": "hello again",
        "event_id": "evt-1",
        "timestamp": 111,
    }

    first = adapter.ingest("channel.chat.message", payload)
    second = adapter.ingest("channel.chat.message", {**payload, "timestamp": 222})

    assert first is not None
    assert second is not None
    assert first["replay_key"] == second["replay_key"]


def test_moderated_twitch_chat_does_not_feed_showrunner(monkeypatch):
    monkeypatch.setenv("PLATFORM_BLOCKED_TERMS", "spoiler")
    monkeypatch.setattr("twitch.adapter._register_replay_key", lambda *args, **kwargs: True)
    adapter = TwitchAdapter(channel_name="godshow", dry_run=True)

    world_event = adapter.ingest(
        "channel.chat.message",
        {
            "channel_name": "godshow",
            "user_name": "viewer_one",
            "user_id": "u1",
            "message": "spoiler for the room",
            "event_id": "evt-blocked",
        },
    )

    assert world_event is not None
    assert world_event["category"] == "moderation"
    assert world_event["event_type"] == "moderation.twitch.blocked"
    assert world_event["payload"]["moderation"]["allowed"] is False
    assert world_event["payload"]["presentation"]["route"] == "moderation_log"
