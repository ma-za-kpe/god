"""YouTube Data API v3 client — auth, token refresh, live chat read/write."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

import httpx

log = logging.getLogger("god.youtube.api")

_YT = "https://www.googleapis.com/youtube/v3"
_AUTH = "https://oauth2.googleapis.com/token"

# YouTube Live Chat send rate limit: ~1 msg/second, 250 msgs/day (conservative)
_RATE_WINDOW_S = 60.0
_RATE_LIMIT = 30


class _RateLimiter:
    def __init__(self, limit: int = _RATE_LIMIT, window: float = _RATE_WINDOW_S):
        self._limit = limit
        self._window = window
        self._timestamps: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        async with self._lock:
            now = time.monotonic()
            self._timestamps = [t for t in self._timestamps if now - t < self._window]
            if len(self._timestamps) >= self._limit:
                return False
            self._timestamps.append(now)
            return True


_chat_limiter = _RateLimiter()


def _access_token() -> str:
    return os.getenv("YOUTUBE_ACCESS_TOKEN", "")


def _refresh_token() -> str:
    return os.getenv("YOUTUBE_REFRESH_TOKEN", "")


def _client_id() -> str:
    return os.getenv("YOUTUBE_CLIENT_ID", "")


def _client_secret() -> str:
    return os.getenv("YOUTUBE_CLIENT_SECRET", "")


def _api_key() -> str:
    return os.getenv("YOUTUBE_API_KEY", "")


async def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    """Exchange a refresh token for a new access token."""
    client_id = _client_id()
    client_secret = _client_secret()
    if not all([client_id, client_secret, refresh_token]):
        return {"ok": False, "reason": "missing_credentials"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                _AUTH,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("access_token"):
                    os.environ["YOUTUBE_ACCESS_TOKEN"] = data["access_token"]
                log.info("YouTube token refreshed successfully")
                return {"ok": True, **data}
            return {"ok": False, "status": r.status_code, "body": r.text[:200]}
    except Exception as exc:
        log.warning("YouTube token refresh failed: %s", exc)
        return {"ok": False, "reason": str(exc)}


async def get_active_live_chat_id(channel_id: str | None = None) -> str | None:
    """Return the liveChatId for the channel's active broadcast, or None."""
    channel_id = channel_id or os.getenv("YOUTUBE_CHANNEL_ID", "")
    access_token = _access_token()
    if not channel_id or not access_token:
        return None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{_YT}/liveBroadcasts",
                params={
                    "part": "snippet",
                    "broadcastStatus": "active",
                    "broadcastType": "all",
                    "maxResults": "1",
                },
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if r.status_code == 401:
                refresh_result = await refresh_access_token(_refresh_token())
                if not refresh_result.get("ok"):
                    return None
                r = await client.get(
                    f"{_YT}/liveBroadcasts",
                    params={
                        "part": "snippet",
                        "broadcastStatus": "active",
                        "broadcastType": "all",
                        "maxResults": "1",
                    },
                    headers={"Authorization": f"Bearer {_access_token()}"},
                )
            if r.status_code != 200:
                return None
            items = r.json().get("items", [])
            if not items:
                return None
            return items[0]["snippet"].get("liveChatId")
    except Exception as exc:
        log.warning("YouTube get_active_live_chat_id failed: %s", exc)
        return None


async def list_chat_messages(
    live_chat_id: str,
    page_token: str = "",
    access_token: str | None = None,
) -> dict[str, Any]:
    """GET liveChat/messages — returns items + nextPageToken + pollingIntervalMillis."""
    access_token = access_token or _access_token()
    if not access_token or not live_chat_id:
        return {"ok": False, "reason": "missing_credentials", "items": []}

    params: dict[str, str] = {
        "liveChatId": live_chat_id,
        "part": "snippet,authorDetails",
        "maxResults": "200",
    }
    if page_token:
        params["pageToken"] = page_token

    async def _get(token: str) -> httpx.Response:
        async with httpx.AsyncClient(timeout=10.0) as client:
            return await client.get(
                f"{_YT}/liveChat/messages",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )

    try:
        r = await _get(access_token)
        if r.status_code == 401:
            refresh_result = await refresh_access_token(_refresh_token())
            if not refresh_result.get("ok"):
                return {"ok": False, "reason": "token_refresh_failed", "items": []}
            r = await _get(_access_token())

        if r.status_code != 200:
            return {"ok": False, "status": r.status_code, "body": r.text[:200], "items": []}

        data = r.json()
        return {
            "ok": True,
            "items": data.get("items", []),
            "nextPageToken": data.get("nextPageToken", ""),
            "pollingIntervalMillis": data.get("pollingIntervalMillis", 5000),
        }
    except Exception as exc:
        log.warning("YouTube list_chat_messages failed: %s", exc)
        return {"ok": False, "reason": str(exc), "items": []}


async def send_chat_message(
    live_chat_id: str,
    message: str,
    access_token: str | None = None,
) -> dict[str, Any]:
    """POST liveChat/messages — send one message to YouTube Live Chat."""
    access_token = access_token or _access_token()
    if not access_token or not live_chat_id:
        return {"ok": False, "reason": "missing_credentials"}
    if not message.strip():
        return {"ok": False, "reason": "empty_message"}

    allowed = await _chat_limiter.acquire()
    if not allowed:
        return {"ok": False, "reason": "rate_limited"}

    body = {
        "snippet": {
            "liveChatId": live_chat_id,
            "type": "textMessageEvent",
            "textMessageDetails": {"messageText": message[:200]},
        }
    }

    async def _post(token: str) -> httpx.Response:
        async with httpx.AsyncClient(timeout=8.0) as client:
            return await client.post(
                f"{_YT}/liveChat/messages",
                params={"part": "snippet"},
                json=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )

    try:
        r = await _post(access_token)
        if r.status_code == 401:
            log.info("YouTube 401 — attempting token refresh")
            refresh_result = await refresh_access_token(_refresh_token())
            if refresh_result.get("ok"):
                r = await _post(_access_token())
            else:
                return {"ok": False, "reason": "token_refresh_failed"}

        if r.status_code in (200, 204):
            return {"ok": True, "status": r.status_code}

        log.warning("YouTube chat send HTTP %s: %s", r.status_code, r.text[:200])
        return {"ok": False, "status": r.status_code, "body": r.text[:200]}
    except Exception as exc:
        log.warning("YouTube chat send failed: %s", exc)
        return {"ok": False, "reason": str(exc)}
