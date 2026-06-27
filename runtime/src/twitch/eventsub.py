"""Twitch EventSub WebSocket client.

Connects to wss://eventsub.wss.twitch.tv/ws, handles the session lifecycle,
subscribes to all world-relevant event types, and routes notification payloads
through TwitchAdapter → event_emitter so the runtime treats them as world events.

Runs as a background asyncio task started in main.py lifespan.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Callable, Coroutine

import websockets

log = logging.getLogger("god.twitch.eventsub")

_EVENTSUB_URL = "wss://eventsub.wss.twitch.tv/ws"
_KEEPALIVE_TIMEOUT_S = 30  # Twitch sends keepalive every 20s; we fail-safe at 30s

# (sub_type, version, condition_factory)
# condition_factory receives broadcaster_id -> dict
_SUBSCRIPTIONS: list[tuple[str, str, Callable[[str], dict[str, Any]]]] = [
    ("channel.chat.message", "1", lambda bid: {"broadcaster_user_id": bid, "user_id": bid}),
    ("channel.follow", "2", lambda bid: {"broadcaster_user_id": bid, "moderator_user_id": bid}),
    ("channel.subscribe", "1", lambda bid: {"broadcaster_user_id": bid}),
    ("channel.subscription.gift", "1", lambda bid: {"broadcaster_user_id": bid}),
    ("channel.subscription.message", "1", lambda bid: {"broadcaster_user_id": bid}),
    ("channel.cheer", "1", lambda bid: {"broadcaster_user_id": bid}),
    ("channel.raid", "1", lambda bid: {"to_broadcaster_user_id": bid}),
    (
        "channel.points.custom_reward_redemption.add",
        "1",
        lambda bid: {"broadcaster_user_id": bid},
    ),
]


def _broadcaster_id() -> str:
    return os.getenv("TWITCH_BROADCASTER_ID", "")


def _is_enabled() -> bool:
    return os.getenv("TWITCH_ENABLED", "false").lower() in ("1", "true", "yes")


def _is_dry_run() -> bool:
    return os.getenv("TWITCH_DRY_RUN", "true").lower() in ("1", "true", "yes")


async def _subscribe_all(session_id: str) -> None:
    """Register all event subscriptions for this WebSocket session."""
    from .helix import create_eventsub_subscription  # avoid circular at module load

    broadcaster_id = _broadcaster_id()
    if not broadcaster_id:
        log.warning("TWITCH_BROADCASTER_ID not set — skipping EventSub subscriptions")
        return

    for sub_type, version, condition_factory in _SUBSCRIPTIONS:
        condition = condition_factory(broadcaster_id)
        # channel.chat.message condition needs bot user_id, not broadcaster for user_id
        if sub_type == "channel.chat.message":
            bot_uid = os.getenv("TWITCH_BOT_USER_ID", broadcaster_id)
            condition = {"broadcaster_user_id": broadcaster_id, "user_id": bot_uid}
        result = await create_eventsub_subscription(
            session_id=session_id,
            sub_type=sub_type,
            version=version,
            condition=condition,
        )
        if result.get("ok"):
            log.info("EventSub subscribed: %s", sub_type)
        else:
            log.warning("EventSub subscribe failed: %s → %s", sub_type, result)
        await asyncio.sleep(0.05)  # avoid burst hitting rate limits


def _extract_twitch_payload(notification: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Pull event_type + flat payload dict from a Twitch notification message."""
    sub = notification.get("subscription", {})
    event = notification.get("event", {})
    event_type = sub.get("type", "")

    # Normalise field names to match TwitchAdapter expectations
    payload: dict[str, Any] = dict(event)
    payload.setdefault("event_id", sub.get("id", ""))
    payload.setdefault("ts", int(time.time()))

    # broadcaster_user_login → channel_name
    if "broadcaster_user_login" in payload:
        payload.setdefault("channel_name", payload["broadcaster_user_login"])
    if "broadcaster_user_name" in payload:
        payload.setdefault(
            "channel_name", payload.get("channel_name") or payload["broadcaster_user_name"]
        )

    # chatter_user_name / user_login → user_name
    if "chatter_user_name" in payload:
        payload.setdefault("user_name", payload["chatter_user_name"])
    if "user_login" in payload:
        payload.setdefault("user_name", payload.get("user_name") or payload["user_login"])
    if "user_name" in payload:
        payload.setdefault("user_id", payload.get("chatter_user_id") or payload.get("user_id", ""))

    # chat message text
    if "message" in payload and isinstance(payload["message"], dict):
        payload["message"] = payload["message"].get("text", "")

    # cheer bits
    if event_type == "channel.cheer":
        payload.setdefault("metadata", {"bits": payload.get("bits", 0)})

    # raid viewers
    if event_type == "channel.raid":
        payload.setdefault("metadata", {"viewer_count": payload.get("viewers", 0)})

    return event_type, payload


class EventSubClient:
    """Long-running EventSub WebSocket client."""

    def __init__(
        self,
        emit_fn: Callable[[str, str, dict[str, Any]], Coroutine[Any, Any, str]],
    ):
        self._emit = emit_fn
        self._running = False
        self._task: asyncio.Task | None = None

    def start(self) -> asyncio.Task:
        self._running = True
        self._task = asyncio.create_task(self._run_forever(), name="eventsub")
        return self._task

    def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()

    async def _run_forever(self) -> None:
        backoff = 2.0
        while self._running:
            try:
                await self._run_session()
                backoff = 2.0
            except asyncio.CancelledError:
                log.info("EventSub client cancelled")
                return
            except Exception as exc:
                log.warning("EventSub session error: %s — reconnecting in %.0fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 1.8, 120.0)

    async def _run_session(self) -> None:
        url = os.getenv("TWITCH_EVENTSUB_URL", _EVENTSUB_URL)
        log.info("EventSub connecting → %s", url)

        async with websockets.connect(
            url,
            ping_interval=None,  # Twitch manages keepalives itself
            close_timeout=5,
        ) as ws:
            session_id: str | None = None
            last_keepalive = time.monotonic()

            async for raw in ws:
                if not self._running:
                    break
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("metadata", {}).get("message_type", "")

                if msg_type == "session_welcome":
                    session_id = msg["payload"]["session"]["id"]
                    log.info("EventSub session_welcome id=%s", session_id)
                    last_keepalive = time.monotonic()
                    if not _is_dry_run():
                        await _subscribe_all(session_id)
                    else:
                        log.info("EventSub dry-run — skipping live subscriptions")

                elif msg_type == "session_keepalive":
                    last_keepalive = time.monotonic()

                elif msg_type == "session_reconnect":
                    new_url = msg["payload"]["session"].get("reconnect_url", url)
                    log.info("EventSub session_reconnect → %s", new_url)
                    os.environ["TWITCH_EVENTSUB_URL"] = new_url
                    break  # reconnect with new URL

                elif msg_type == "notification":
                    last_keepalive = time.monotonic()
                    await self._handle_notification(msg["payload"])

                elif msg_type == "revocation":
                    sub = msg["payload"].get("subscription", {})
                    log.warning(
                        "EventSub subscription revoked: %s reason=%s",
                        sub.get("type"),
                        sub.get("status"),
                    )

                # Keepalive watchdog: Twitch sends keepalive every 20s
                if time.monotonic() - last_keepalive > _KEEPALIVE_TIMEOUT_S:
                    log.warning("EventSub keepalive timeout — reconnecting")
                    break

    async def _handle_notification(self, payload: dict[str, Any]) -> None:
        try:
            from .adapter import TwitchAdapter  # avoid circular at module level
        except ImportError:
            from adapter import TwitchAdapter  # flat test path

        adapter = TwitchAdapter()
        event_type, flat_payload = _extract_twitch_payload(payload)
        world_event = adapter.ingest(event_type, flat_payload)
        if world_event is None:
            return  # unsupported type or replay duplicate

        category = world_event.get("category", "social")
        wtype = world_event.get("event_type", "twitch.event")
        # Strip the "category." prefix from event_type for the emit call
        short_type = wtype.removeprefix(f"{category}.")

        try:
            await self._emit(category, short_type, world_event)
            log.debug("EventSub → world event: %s", wtype)
        except Exception as exc:
            log.warning("EventSub emit failed: %s", exc)
