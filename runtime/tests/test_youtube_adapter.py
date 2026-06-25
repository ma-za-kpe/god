"""YouTube adapter tests."""

import pytest

from youtube.adapter import YouTubeAdapter, build_youtube_status, normalize_youtube_event
from youtube.models import YouTubeChatMessage


def test_normalizes_chat_message():
    event = normalize_youtube_event(
        "textMessageEvent",
        {
            "channel_id": "UC123",
            "user_name": "viewer_one",
            "user_id": "u1",
            "message": "hello world",
        },
    )

    assert event is not None
    assert event.event_type == "textMessageEvent"
    assert event.channel_id == "UC123"
    assert event.user_name == "viewer_one"


def test_normalizes_super_chat():
    event = normalize_youtube_event(
        "superChatEvent",
        {
            "channel_id": "UC123",
            "user_name": "big_fan",
            "user_id": "u2",
            "message": "keep it up!",
            "amount_micros": 5_000_000,
            "currency": "USD",
        },
    )

    assert event is not None
    assert event.event_type == "superChatEvent"
    assert event.metadata["amount_micros"] == 5_000_000
    assert event.metadata["currency"] == "USD"


def test_rejects_unknown_event_type():
    event = normalize_youtube_event("unknownEvent", {"channel_id": "UC123"})
    assert event is None


def test_rejects_missing_channel_id(monkeypatch):
    monkeypatch.delenv("YOUTUBE_CHANNEL_ID", raising=False)
    event = normalize_youtube_event("textMessageEvent", {"user_name": "x"})
    assert event is None


def test_ingest_chat_becomes_social_world_event():
    adapter = YouTubeAdapter(channel_id="UC123", dry_run=True)
    world_event = adapter.ingest(
        "textMessageEvent",
        {
            "channel_id": "UC123",
            "user_name": "viewer_one",
            "user_id": "u1",
            "message": "great stream",
        },
    )

    assert world_event is not None
    assert world_event["category"] == "social"
    assert world_event["event_type"] == "social.youtube.chat.message"
    assert "viewer_one" in world_event["narrative"]


def test_ingest_super_chat_becomes_economy_event():
    adapter = YouTubeAdapter(channel_id="UC123", dry_run=True)
    world_event = adapter.ingest(
        "superChatEvent",
        {
            "channel_id": "UC123",
            "user_name": "generous_fan",
            "user_id": "u2",
            "message": "love this",
            "amount_micros": 10_000_000,
            "currency": "USD",
        },
    )

    assert world_event is not None
    assert world_event["category"] == "economy"
    assert world_event["event_type"] == "economy.youtube.super_chat"
    assert "generous_fan" in world_event["narrative"]


def test_ingest_membership_becomes_economy_event():
    adapter = YouTubeAdapter(channel_id="UC123", dry_run=True)
    world_event = adapter.ingest(
        "newSponsorEvent",
        {
            "channel_id": "UC123",
            "user_name": "new_member",
            "user_id": "u3",
        },
    )

    assert world_event is not None
    assert world_event["category"] == "economy"
    assert world_event["event_type"] == "economy.youtube.membership"


@pytest.mark.asyncio
async def test_send_chat_defaults_to_dry_run():
    adapter = YouTubeAdapter(channel_id="UC123", dry_run=True)
    result = await adapter.send_chat(
        YouTubeChatMessage(message="hello chat", live_chat_id="lc_abc")
    )

    assert result.ok
    assert result.dry_run
    assert result.reason == "dry_run"


@pytest.mark.asyncio
async def test_send_chat_rejects_empty_message():
    adapter = YouTubeAdapter(channel_id="UC123", dry_run=True)
    result = await adapter.send_chat(
        YouTubeChatMessage(message="   ", live_chat_id="lc_abc")
    )

    assert not result.ok
    assert result.reason == "empty_message"


def test_status_exposes_supported_types():
    status = build_youtube_status()

    assert "supported_event_types" in status
    assert "textMessageEvent" in status["supported_event_types"]
    assert "superChatEvent" in status["supported_event_types"]
    assert "health" in status
