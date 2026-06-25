"""YouTube Live Chat polling client.

Polls liveChat/messages at the interval YouTube prescribes, discovers the
active liveChatId on start (and re-discovers on stream restart), and routes
notification payloads through YouTubeAdapter → event_emitter.

Runs as a background asyncio task started in main.py lifespan.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Callable, Coroutine

log = logging.getLogger("god.youtube.chat_poller")

_DEFAULT_POLL_MS = 5000
_CHAT_DISCOVER_INTERVAL_S = 60  # re-check for active broadcast every 60s


def _is_enabled() -> bool:
    return os.getenv("YOUTUBE_ENABLED", "false").lower() in ("1", "true", "yes")


def _is_dry_run() -> bool:
    return os.getenv("YOUTUBE_DRY_RUN", "true").lower() in ("1", "true", "yes")


def _extract_event_type(item: dict[str, Any]) -> str:
    return item.get("snippet", {}).get("type", "")


def _extract_payload(item: dict[str, Any]) -> dict[str, Any]:
    """Flatten a liveChat/messages item into the shape YouTubeAdapter.ingest() expects."""
    snippet = item.get("snippet", {})
    author = item.get("authorDetails", {})
    event_type = snippet.get("type", "")

    payload: dict[str, Any] = {
        "event_id": item.get("id", ""),
        "channel_id": os.getenv("YOUTUBE_CHANNEL_ID", ""),
        "user_name": author.get("displayName", ""),
        "user_id": author.get("channelId", ""),
        "published_at": snippet.get("publishedAt", ""),
        "ts": int(time.time()),
        "metadata": {},
    }

    if event_type == "textMessageEvent":
        payload["message"] = snippet.get("textMessageDetails", {}).get("messageText", "")

    elif event_type == "superChatEvent":
        sc = snippet.get("superChatDetails", {})
        payload["message"] = sc.get("userComment", "")
        payload["amount_micros"] = sc.get("amountMicros", 0)
        payload["currency"] = sc.get("currency", "")
        payload["metadata"] = {
            "amount_micros": sc.get("amountMicros", 0),
            "currency": sc.get("currency", ""),
        }

    elif event_type == "superStickerEvent":
        ss = snippet.get("superStickerDetails", {})
        payload["amount_micros"] = ss.get("amountMicros", 0)
        payload["currency"] = ss.get("currency", "")

    elif event_type == "memberMilestoneChatEvent":
        mm = snippet.get("memberMilestoneChatDetails", {})
        payload["message"] = mm.get("userComment", "")
        payload["member_month"] = mm.get("memberMonth", 0)
        payload["metadata"] = {"member_month": mm.get("memberMonth", 0)}

    return payload


class ChatPoller:
    """Long-running YouTube Live Chat polling client."""

    def __init__(
        self,
        emit_fn: Callable[[str, str, dict[str, Any]], Coroutine[Any, Any, str]],
    ):
        self._emit = emit_fn
        self._running = False
        self._task: asyncio.Task | None = None

    def start(self) -> asyncio.Task:
        self._running = True
        self._task = asyncio.create_task(self._run_forever(), name="youtube_poller")
        return self._task

    def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()

    async def _run_forever(self) -> None:
        backoff = 5.0
        while self._running:
            try:
                await self._run_session()
                backoff = 5.0
            except asyncio.CancelledError:
                log.info("YouTube chat poller cancelled")
                return
            except Exception as exc:
                log.warning("YouTube poller error: %s — retrying in %.0fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 1.8, 120.0)

    async def _run_session(self) -> None:
        from .api import get_active_live_chat_id, list_chat_messages

        live_chat_id: str | None = None
        page_token = ""
        last_discover = 0.0

        log.info("YouTube chat poller starting")

        while self._running:
            now = time.monotonic()

            # Discover (or re-discover) active live chat
            if live_chat_id is None or now - last_discover > _CHAT_DISCOVER_INTERVAL_S:
                live_chat_id = await get_active_live_chat_id()
                last_discover = now
                if live_chat_id:
                    log.info("YouTube active liveChatId: %s", live_chat_id)
                else:
                    log.debug(
                        "No active YouTube broadcast — will retry in %ds", _CHAT_DISCOVER_INTERVAL_S
                    )
                    await asyncio.sleep(_CHAT_DISCOVER_INTERVAL_S)
                    continue

            if _is_dry_run():
                log.debug("YouTube poller dry-run — not fetching live chat")
                await asyncio.sleep(_DEFAULT_POLL_MS / 1000)
                continue

            result = await list_chat_messages(live_chat_id, page_token=page_token)

            if not result.get("ok"):
                log.warning("YouTube list_chat_messages failed: %s", result)
                # Reset chat id — stream may have ended
                live_chat_id = None
                page_token = ""
                await asyncio.sleep(15)
                continue

            page_token = result.get("nextPageToken", page_token)
            poll_s = result.get("pollingIntervalMillis", _DEFAULT_POLL_MS) / 1000

            for item in result.get("items", []):
                await self._handle_item(item)

            await asyncio.sleep(poll_s)

    async def _handle_item(self, item: dict[str, Any]) -> None:
        try:
            from .adapter import YouTubeAdapter
        except ImportError:
            from adapter import YouTubeAdapter  # flat test path

        adapter = YouTubeAdapter()
        event_type = _extract_event_type(item)
        payload = _extract_payload(item)

        world_event = adapter.ingest(event_type, payload)
        if world_event is None:
            return

        category = world_event.get("category", "social")
        wtype = world_event.get("event_type", "youtube.event")
        short_type = wtype.removeprefix(f"{category}.")

        try:
            await self._emit(category, short_type, world_event)
            log.debug("YouTube → world event: %s", wtype)
        except Exception as exc:
            log.warning("YouTube poller emit failed: %s", exc)
