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


def test_ingest_chat_becomes_world_event():
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
