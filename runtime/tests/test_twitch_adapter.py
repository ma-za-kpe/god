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
