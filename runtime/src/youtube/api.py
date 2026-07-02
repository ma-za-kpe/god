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


def _missing_oauth_fields() -> list[str]:
    required = {
        "YOUTUBE_ACCESS_TOKEN": _access_token(),
        "YOUTUBE_REFRESH_TOKEN": _refresh_token(),
        "YOUTUBE_CLIENT_ID": _client_id(),
        "YOUTUBE_CLIENT_SECRET": _client_secret(),
    }
    return [name for name, value in required.items() if not value]


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


async def _youtube_request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Issue an authenticated YouTube Data API request with one token refresh."""
    missing = _missing_oauth_fields()
    if missing:
        return {"ok": False, "reason": "missing_credentials", "missing": missing}

    async def _send(token: str) -> httpx.Response:
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.request(
                method,
                f"{_YT}/{path.lstrip('/')}",
                params=params or {},
                json=body,
                headers={"Authorization": f"Bearer {token}"},
            )

    try:
        response = await _send(_access_token())
        if response.status_code == 401:
            refresh_result = await refresh_access_token(_refresh_token())
            if not refresh_result.get("ok"):
                return {
                    "ok": False,
                    "reason": "token_refresh_failed",
                    "refresh": refresh_result,
                }
            response = await _send(_access_token())

        if 200 <= response.status_code < 300:
            payload: dict[str, Any] = {}
            if response.content:
                payload = response.json()
            return {"ok": True, "status": response.status_code, "data": payload}

        detail: dict[str, Any] = {}
        try:
            detail = response.json()
        except ValueError:
            detail = {"body": response.text[:400]}
        return {"ok": False, "status": response.status_code, "error": detail}
    except Exception as exc:
        log.warning("YouTube API request failed: %s %s: %s", method, path, exc)
        return {"ok": False, "reason": str(exc)}


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


def _broadcast_lifecycle(item: dict[str, Any] | None) -> str:
    return str(((item or {}).get("status") or {}).get("lifeCycleStatus") or "")


def _bound_stream_id(item: dict[str, Any] | None) -> str:
    return str(((item or {}).get("contentDetails") or {}).get("boundStreamId") or "")


def _youtube_error_reasons(result: dict[str, Any]) -> set[str]:
    error = result.get("error") or {}
    if not isinstance(error, dict):
        return set()
    detail = error.get("error") if isinstance(error.get("error"), dict) else error
    reasons: set[str] = set()
    for item in detail.get("errors") or []:
        if isinstance(item, dict) and item.get("reason"):
            reasons.add(str(item["reason"]))
    if detail.get("reason"):
        reasons.add(str(detail["reason"]))
    if error.get("reason"):
        reasons.add(str(error["reason"]))
    return reasons


async def get_live_broadcast(broadcast_id: str) -> dict[str, Any]:
    """Fetch one YouTube live broadcast by id."""
    broadcast_id = (broadcast_id or "").strip()
    if not broadcast_id:
        return {"ok": False, "reason": "missing_broadcast_id"}

    result = await _youtube_request(
        "GET",
        "liveBroadcasts",
        params={
            "part": "id,snippet,contentDetails,status",
            "id": broadcast_id,
        },
    )
    if not result.get("ok"):
        return result

    items = result.get("data", {}).get("items", [])
    if not items:
        return {"ok": False, "reason": "broadcast_not_found", "broadcast_id": broadcast_id}

    broadcast = items[0]
    return {
        "ok": True,
        "broadcast": broadcast,
        "lifeCycleStatus": _broadcast_lifecycle(broadcast),
        "boundStreamId": _bound_stream_id(broadcast),
    }


async def get_live_stream(stream_id: str) -> dict[str, Any]:
    """Fetch one bound YouTube live stream by id."""
    stream_id = (stream_id or "").strip()
    if not stream_id:
        return {"ok": False, "reason": "missing_stream_id"}

    result = await _youtube_request(
        "GET",
        "liveStreams",
        params={
            "part": "id,snippet,cdn,status",
            "id": stream_id,
        },
    )
    if not result.get("ok"):
        return result

    items = result.get("data", {}).get("items", [])
    if not items:
        return {"ok": False, "reason": "stream_not_found", "stream_id": stream_id}

    stream = items[0]
    stream_status = str((stream.get("status") or {}).get("streamStatus") or "")
    return {"ok": True, "stream": stream, "streamStatus": stream_status}


async def wait_for_bound_stream_active(
    broadcast_id: str,
    *,
    timeout_s: float = 90.0,
    poll_s: float = 5.0,
) -> dict[str, Any]:
    """Wait until the broadcast's bound stream is ingesting active video."""
    deadline = time.monotonic() + max(timeout_s, 0.0)
    last_status: dict[str, Any] = {}

    while True:
        broadcast_result = await get_live_broadcast(broadcast_id)
        if not broadcast_result.get("ok"):
            return broadcast_result

        lifecycle = str(broadcast_result.get("lifeCycleStatus") or "")
        if lifecycle in ("live", "liveStarting"):
            return {**broadcast_result, "ok": True, "streamStatus": "active"}

        stream_id = str(broadcast_result.get("boundStreamId") or "")
        if not stream_id:
            return {
                "ok": False,
                "reason": "broadcast_has_no_bound_stream",
                "broadcast_id": broadcast_id,
                "lifeCycleStatus": lifecycle,
            }

        stream_result = await get_live_stream(stream_id)
        if not stream_result.get("ok"):
            return stream_result

        stream_status = str(stream_result.get("streamStatus") or "")
        last_status = {
            "broadcast_id": broadcast_id,
            "stream_id": stream_id,
            "lifeCycleStatus": lifecycle,
            "streamStatus": stream_status,
        }
        if stream_status == "active":
            return {**last_status, "ok": True}

        if time.monotonic() >= deadline:
            return {"ok": False, "reason": "stream_not_active", **last_status}
        await asyncio.sleep(max(poll_s, 0.25))


async def transition_live_broadcast(
    broadcast_id: str,
    target_status: str = "live",
) -> dict[str, Any]:
    """Transition a configured YouTube broadcast to testing/live/complete."""
    broadcast_id = (broadcast_id or "").strip()
    target_status = (target_status or "").strip()
    if not broadcast_id:
        return {"ok": False, "reason": "missing_broadcast_id"}
    if target_status not in {"testing", "live", "complete"}:
        return {"ok": False, "reason": "invalid_target_status", "target": target_status}

    result = await _youtube_request(
        "POST",
        "liveBroadcasts/transition",
        params={
            "part": "id,snippet,contentDetails,status",
            "id": broadcast_id,
            "broadcastStatus": target_status,
        },
    )
    if not result.get("ok"):
        return result

    broadcast = result.get("data", {})
    return {
        "ok": True,
        "broadcast": broadcast,
        "lifeCycleStatus": _broadcast_lifecycle(broadcast),
    }


async def ensure_broadcast_live(
    broadcast_id: str | None = None,
    *,
    timeout_s: float | None = None,
    poll_s: float | None = None,
) -> dict[str, Any]:
    """Wait for RTMP ingest and transition the configured YouTube broadcast live."""
    broadcast_id = (broadcast_id or os.getenv("YOUTUBE_BROADCAST_ID", "")).strip()
    timeout_s = _env_float("YOUTUBE_GO_LIVE_TIMEOUT_S", 90.0) if timeout_s is None else timeout_s
    poll_s = _env_float("YOUTUBE_GO_LIVE_POLL_S", 5.0) if poll_s is None else poll_s

    if not broadcast_id:
        return {"ok": False, "reason": "missing_broadcast_id"}

    current = await get_live_broadcast(broadcast_id)
    if not current.get("ok"):
        return current

    lifecycle = str(current.get("lifeCycleStatus") or "")
    if lifecycle in ("live", "liveStarting"):
        return {
            "ok": True,
            "reason": "already_live",
            "broadcast_id": broadcast_id,
            "lifeCycleStatus": lifecycle,
        }
    if lifecycle in ("complete", "revoked"):
        return {
            "ok": False,
            "reason": "broadcast_not_transitionable",
            "broadcast_id": broadcast_id,
            "lifeCycleStatus": lifecycle,
        }

    stream_ready = await wait_for_bound_stream_active(
        broadcast_id,
        timeout_s=timeout_s,
        poll_s=poll_s,
    )
    if not stream_ready.get("ok"):
        return stream_ready

    transition = await transition_live_broadcast(broadcast_id, "live")
    if not transition.get("ok"):
        if "redundantTransition" in _youtube_error_reasons(transition):
            current = await get_live_broadcast(broadcast_id)
            lifecycle = str(current.get("lifeCycleStatus") or "")
            if current.get("ok") and lifecycle in ("live", "liveStarting"):
                return {
                    "ok": True,
                    "reason": "already_live_redundant_transition",
                    "broadcast_id": broadcast_id,
                    "lifeCycleStatus": lifecycle,
                    "streamStatus": stream_ready.get("streamStatus", ""),
                    "transition": transition,
                }
        return transition

    for _ in range(12):
        current = await get_live_broadcast(broadcast_id)
        lifecycle = str(current.get("lifeCycleStatus") or "")
        if current.get("ok") and lifecycle in ("live", "liveStarting"):
            return {
                "ok": True,
                "reason": "transitioned",
                "broadcast_id": broadcast_id,
                "lifeCycleStatus": lifecycle,
                "streamStatus": stream_ready.get("streamStatus", ""),
            }
        await asyncio.sleep(max(poll_s, 0.25))

    return {
        "ok": False,
        "reason": "transition_not_confirmed",
        "broadcast_id": broadcast_id,
        "transition": transition,
    }


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
