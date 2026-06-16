"""Audience and patronage weave from Twitch events into world state."""

from __future__ import annotations

import os
from collections import defaultdict
from typing import Any

try:  # pragma: no cover - runtime package import path
    from .state import AudienceState
except ImportError:  # pragma: no cover - flat test path
    from state import AudienceState


def _env_bool(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")


def _event_type(event: dict[str, Any]) -> str:
    return str(event.get("event_type") or event.get("type") or "").strip()


def _payload(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload") or {}
    return payload if isinstance(payload, dict) else {}


def _actor_key(event: dict[str, Any]) -> str:
    payload = _payload(event)
    return str(
        payload.get("user_name")
        or payload.get("chatter_name")
        or payload.get("from_broadcaster_user_name")
        or event.get("agent_name")
        or event.get("agent_id")
        or payload.get("user_id")
        or "audience"
    ).strip() or "audience"


def _event_support(event: dict[str, Any]) -> dict[str, Any] | None:
    event_type = _event_type(event)
    payload = _payload(event)
    if not event_type:
        return None

    actor = _actor_key(event)
    narrative = str(event.get("narrative") or payload.get("message") or event_type)
    support_points = 0.0
    label = "audience"
    kind = "signal"
    tone = "neutral"

    if event_type.endswith("social.twitch.chat.message") or event_type == "social.twitch.chat.message":
        support_points = 0.4
        label = "chat"
        kind = "chat"
        tone = "cognitive"
        narrative = f"{actor} steers the room: {narrative[:120]}"
    elif event_type.endswith("social.twitch.follow") or event_type == "social.twitch.follow":
        support_points = 1.0
        label = "follow"
        kind = "follow"
        tone = "social"
        narrative = f"{actor} follows the channel."
    elif event_type.endswith("social.twitch.raid") or event_type == "social.twitch.raid":
        viewers = int(payload.get("metadata", {}).get("viewer_count") or payload.get("viewer_count") or payload.get("viewers") or 0)
        support_points = max(2.0, viewers / 10.0)
        label = "raid"
        kind = "raid"
        tone = "threat"
        narrative = f"{actor} raids with {viewers} viewers."
    elif event_type.endswith("economy.twitch.subscribe") or event_type == "economy.twitch.subscribe":
        support_points = 8.0
        label = "subscribe"
        kind = "subscribe"
        tone = "gold"
        narrative = f"{actor} becomes a patron."
    elif event_type.endswith("economy.twitch.subscription.gift") or event_type == "economy.twitch.subscription_gift":
        gifts = int(payload.get("metadata", {}).get("gift_count") or payload.get("gift_count") or 1)
        support_points = max(12.0, gifts * 6.0)
        label = "gift"
        kind = "gift"
        tone = "gold"
        narrative = f"{actor} gifts {gifts} subscriptions."
    elif event_type.endswith("economy.twitch.subscription.message") or event_type == "economy.twitch.subscription_message":
        support_points = 4.5
        label = "renewal"
        kind = "renewal"
        tone = "gold"
        narrative = f"{actor} renews their patronage."
    elif event_type.endswith("economy.twitch.cheer") or event_type == "economy.twitch.cheer":
        bits = int(payload.get("metadata", {}).get("bits") or payload.get("bits") or 0)
        support_points = max(1.0, bits / 100.0)
        label = "cheer"
        kind = "cheer"
        tone = "gold"
        narrative = f"{actor} cheers {bits} bits."
    elif event_type.endswith("social.twitch.channel_point") or event_type == "social.twitch.channel_point":
        support_points = 1.8
        label = "channel-point"
        kind = "redemption"
        tone = "manifesto"
        narrative = f"{actor} spends channel points to steer the stage."
    else:
        return None

    return {
        "event_id": str(event.get("event_id") or payload.get("event_id") or ""),
        "event_type": event_type,
        "actor": actor,
        "label": label,
        "kind": kind,
        "tone": tone,
        "support_points": round(float(support_points), 3),
        "narrative": narrative,
        "payload": payload,
    }


def _scene_for_audience(support_kinds: dict[str, int], chat_pressure: int, raid_waves: int) -> str:
    if support_kinds.get("subscribe") or support_kinds.get("gift") or support_kinds.get("cheer"):
        return "market-watch"
    if raid_waves > 0:
        return "banter-table"
    if chat_pressure > 0:
        return "banter-table"
    return "world-wide"


class AudienceSurface:
    """Compose a live audience/patronage view from the current world snapshot."""

    def __init__(self, enabled: bool | None = None, dry_run: bool | None = None):
        self.enabled = _env_bool("AUDIENCE_ENABLED", "true") if enabled is None else enabled
        self.dry_run = _env_bool("AUDIENCE_DRY_RUN", "true") if dry_run is None else dry_run
        self.mode = os.getenv("AUDIENCE_MODE", "deterministic")
        self.transport = os.getenv("AUDIENCE_TRANSPORT", "dry-run")

    def compose(self, snapshot: dict[str, Any]) -> AudienceState:
        stats = snapshot.get("stats") or {}
        events = snapshot.get("events") or []
        source_epoch = int(snapshot.get("epoch") or 0)
        world_id = str(snapshot.get("world_id") or "")

        signals: list[dict[str, Any]] = []
        support_by_actor: dict[str, float] = defaultdict(float)
        events_by_actor: dict[str, int] = defaultdict(int)
        support_kinds: dict[str, int] = defaultdict(int)
        chat_pressure = 0
        raid_waves = 0

        for event in events:
            signal = _event_support(event)
            if not signal:
                continue
            signals.append(signal)
            actor = signal["actor"]
            support_by_actor[actor] += float(signal["support_points"])
            events_by_actor[actor] += 1
            support_kinds[signal["kind"]] += 1
            if signal["kind"] == "chat":
                chat_pressure += 1
            elif signal["kind"] == "raid":
                raid_waves += 1

        signals.sort(key=lambda item: (item["support_points"], item["kind"], item["actor"]), reverse=True)

        patronage_index = round(sum(float(signal["support_points"]) for signal in signals), 2)
        hype_index = round(
            patronage_index
            + chat_pressure * 0.25
            + raid_waves * 2.5
            + float(stats.get("service_purchases_24h") or 0) * 0.5,
            2,
        )

        top_supporters = [
            {
                "name": actor,
                "support_points": round(points, 2),
                "events": events_by_actor[actor],
            }
            for actor, points in sorted(
                support_by_actor.items(),
                key=lambda item: (item[1], events_by_actor[item[0]], item[0]),
                reverse=True,
            )[:5]
        ]

        if support_kinds.get("subscribe") or support_kinds.get("gift") or support_kinds.get("cheer"):
            story_hook = "Patrons are funding the cast; reward the room with a stronger turn."
        elif raid_waves:
            story_hook = "A raid just widened the audience; escalate the conflict for the new viewers."
        elif chat_pressure >= 8:
            story_hook = "Chat is loud enough to steer the stage; answer the room directly."
        elif chat_pressure > 0:
            story_hook = "The audience is present; keep the agents responsive and legible."
        else:
            story_hook = "The audience is quiet; let the world breathe on its own."

        scene_name = _scene_for_audience(support_kinds, chat_pressure, raid_waves)
        summary = (
            f"{scene_name}: {int(patronage_index)} support points, "
            f"{chat_pressure} chat beats, {raid_waves} raid wave(s)."
        )

        cards = [
            {"label": "Patronage", "value": f"{patronage_index:.1f}", "tone": "gold"},
            {"label": "Chat", "value": chat_pressure, "tone": "cognitive"},
            {"label": "Patrons", "value": len(top_supporters), "tone": "social"},
            {"label": "Raids", "value": raid_waves, "tone": "threat"},
            {"label": "Hype", "value": f"{hype_index:.1f}", "tone": "life"},
        ]
        labels = (
            "audience",
            "patronage",
            scene_name,
            "live-weave",
        )
        commands = (
            {
                "action": "set_audience_hook",
                "target": "stage",
                "value": story_hook,
                "reason": "audience-pressure",
                "metadata": {
                    "support_points": patronage_index,
                    "chat_pressure": chat_pressure,
                    "raid_waves": raid_waves,
                },
            },
        )
        return AudienceState(
            enabled=self.enabled,
            dry_run=self.dry_run,
            mode=self.mode,
            world_id=world_id,
            source_epoch=source_epoch,
            scene=scene_name,
            chat_pressure=chat_pressure,
            unique_supporters_24h=len(support_by_actor),
            supporter_waves_24h=sum(events_by_actor.values()),
            raid_waves_24h=raid_waves,
            patronage_index=patronage_index,
            hype_index=hype_index,
            story_hook=story_hook,
            summary=summary,
            labels=labels,
            cards=tuple(cards),
            top_supporters=tuple(top_supporters),
            signals=tuple(signals[:25]),
            commands=commands,
        )

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "dry_run": self.dry_run,
            "mode": self.mode,
            "transport": self.transport,
            "supported_event_types": [
                "social.twitch.chat.message",
                "social.twitch.follow",
                "social.twitch.raid",
                "social.twitch.channel_point",
                "economy.twitch.subscribe",
                "economy.twitch.subscription_gift",
                "economy.twitch.subscription_message",
                "economy.twitch.cheer",
            ],
        }


def build_audience_state(snapshot: dict[str, Any]) -> dict[str, Any]:
    return AudienceSurface().compose(snapshot).to_dict()


def build_audience_status() -> dict[str, Any]:
    return AudienceSurface().status()
