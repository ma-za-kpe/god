"""Shared platform boundary tests."""

from __future__ import annotations

from platforms import build_platform_audience_event


def test_platform_boundary_routes_allowed_events_to_showrunner_only():
    event = build_platform_audience_event(
        platform="twitch",
        event_id="evt-1",
        platform_event_type="channel.chat.message",
        channel_name="godshow",
        actor_name="viewer_one",
        actor_id="u1",
        message="keep going",
        timestamp=123,
    )

    payload = event.to_payload()

    assert payload["platform"] == "twitch"
    assert payload["presentation"]["route"] == "showrunner"
    assert payload["presentation"]["surface"] == "audience"
    assert payload["presentation"]["direct_effects"] == []
    assert payload["rate_limit"]["bucket"] == "twitch:godshow:u1:chat"
    assert payload["moderation"]["allowed"] is True


def test_platform_boundary_flags_blocked_terms_without_direct_effects(monkeypatch):
    monkeypatch.setenv("PLATFORM_BLOCKED_TERMS", "spoiler")

    event = build_platform_audience_event(
        platform="twitch",
        event_id="evt-2",
        platform_event_type="channel.chat.message",
        channel_name="godshow",
        actor_name="viewer_one",
        actor_id="u1",
        message="spoiler for the scene",
        timestamp=124,
    )

    assert event.moderation["allowed"] is False
    assert event.moderation["reason"] == "blocked_term"
    assert event.presentation["route"] == "moderation_log"
    assert event.presentation["direct_effects"] == []
