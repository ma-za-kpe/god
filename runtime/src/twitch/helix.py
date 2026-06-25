"""Twitch Helix API client — auth, token validation, chat send."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

import httpx

log = logging.getLogger("god.twitch.helix")

_HELIX = "https://api.twitch.tv/helix"
_AUTH = "https://id.twitch.tv/oauth2"

# Twitch chat rate limit: 20 messages per 30 seconds per channel (non-mod bot)
_RATE_WINDOW_S = 30
_RATE_LIMIT = 20


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


def _client_id() -> str:
    return os.getenv("TWITCH_CLIENT_ID", "")


def _client_secret() -> str:
    return os.getenv("TWITCH_CLIENT_SECRET", "")


def _bot_access_token() -> str:
    return os.getenv("TWITCH_BOT_ACCESS_TOKEN", "")


def _bot_refresh_token() -> str:
    return os.getenv("TWITCH_BOT_REFRESH_TOKEN", "")


def _broadcaster_id() -> str:
    return os.getenv("TWITCH_BROADCASTER_ID", "")


def _bot_user_id() -> str:
    return os.getenv("TWITCH_BOT_USER_ID", "")


async def validate_token(access_token: str) -> dict[str, Any]:
    """Call /oauth2/validate — returns parsed body or {"valid": False}."""
    if not access_token:
        return {"valid": False, "reason": "empty_token"}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                f"{_AUTH}/validate",
                headers={"Authorization": f"OAuth {access_token}"},
            )
            if r.status_code == 200:
                data = r.json()
                data["valid"] = True
                return data
            return {"valid": False, "status": r.status_code}
    except Exception as exc:
        log.warning("Helix token validate failed: %s", exc)
        return {"valid": False, "reason": str(exc)}


async def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    """Exchange a refresh token for a new access + refresh token pair."""
    client_id = _client_id()
    client_secret = _client_secret()
    if not all([client_id, client_secret, refresh_token]):
        return {"ok": False, "reason": "missing_credentials"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{_AUTH}/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )
            if r.status_code == 200:
                data = r.json()
                # Persist updated tokens to env so later calls pick them up
                if data.get("access_token"):
                    os.environ["TWITCH_BOT_ACCESS_TOKEN"] = data["access_token"]
                if data.get("refresh_token"):
                    os.environ["TWITCH_BOT_REFRESH_TOKEN"] = data["refresh_token"]
                log.info("Twitch token refreshed successfully")
                return {"ok": True, **data}
            return {"ok": False, "status": r.status_code, "body": r.text[:200]}
    except Exception as exc:
        log.warning("Helix token refresh failed: %s", exc)
        return {"ok": False, "reason": str(exc)}


async def send_chat_message(
    message: str,
    broadcaster_id: str | None = None,
    sender_id: str | None = None,
    access_token: str | None = None,
    reply_to_message_id: str = "",
) -> dict[str, Any]:
    """POST /helix/chat/messages — send one message to Twitch chat.

    Returns {"ok": True} on success or {"ok": False, "reason": ...}.
    Handles 401 by attempting a token refresh once, then retrying.
    """
    broadcaster_id = broadcaster_id or _broadcaster_id()
    sender_id = sender_id or _bot_user_id()
    access_token = access_token or _bot_access_token()
    client_id = _client_id()

    if not all([broadcaster_id, sender_id, access_token, client_id]):
        return {"ok": False, "reason": "missing_credentials"}
    if not message.strip():
        return {"ok": False, "reason": "empty_message"}

    allowed = await _chat_limiter.acquire()
    if not allowed:
        return {"ok": False, "reason": "rate_limited"}

    body: dict[str, Any] = {
        "broadcaster_id": broadcaster_id,
        "sender_id": sender_id,
        "message": message[:500],
    }
    if reply_to_message_id:
        body["reply_parent_message_id"] = reply_to_message_id

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Client-Id": client_id,
        "Content-Type": "application/json",
    }

    async def _post() -> httpx.Response:
        async with httpx.AsyncClient(timeout=8.0) as client:
            return await client.post(f"{_HELIX}/chat/messages", json=body, headers=headers)

    try:
        r = await _post()
        if r.status_code in (200, 204):
            return {"ok": True, "status": r.status_code}

        if r.status_code == 401:
            # Token expired — try refresh once
            log.info("Helix 401 — attempting token refresh")
            refresh_result = await refresh_access_token(_bot_refresh_token())
            if refresh_result.get("ok"):
                headers["Authorization"] = f"Bearer {_bot_access_token()}"
                r2 = await _post()
                if r2.status_code in (200, 204):
                    return {"ok": True, "status": r2.status_code, "refreshed": True}
                return {"ok": False, "status": r2.status_code, "body": r2.text[:200]}
            return {"ok": False, "reason": "token_refresh_failed", **refresh_result}

        log.warning("Helix chat send HTTP %s: %s", r.status_code, r.text[:200])
        return {"ok": False, "status": r.status_code, "body": r.text[:200]}

    except Exception as exc:
        log.warning("Helix chat send failed: %s", exc)
        return {"ok": False, "reason": str(exc)}


async def create_eventsub_subscription(
    session_id: str,
    sub_type: str,
    version: str,
    condition: dict[str, Any],
    access_token: str | None = None,
) -> dict[str, Any]:
    """POST /helix/eventsub/subscriptions for a WebSocket transport."""
    access_token = access_token or _bot_access_token()
    client_id = _client_id()
    if not all([session_id, access_token, client_id]):
        return {"ok": False, "reason": "missing_credentials"}
    payload = {
        "type": sub_type,
        "version": version,
        "condition": condition,
        "transport": {"method": "websocket", "session_id": session_id},
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{_HELIX}/eventsub/subscriptions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Client-Id": client_id,
                    "Content-Type": "application/json",
                },
            )
            if r.status_code in (200, 202):
                return {"ok": True, "type": sub_type, **r.json()}
            log.warning("EventSub subscribe %s HTTP %s: %s", sub_type, r.status_code, r.text[:200])
            return {"ok": False, "type": sub_type, "status": r.status_code, "body": r.text[:200]}
    except Exception as exc:
        log.warning("EventSub subscribe %s failed: %s", sub_type, exc)
        return {"ok": False, "type": sub_type, "reason": str(exc)}
