"""YouTube Data API lifecycle tests."""

import pytest

from youtube import api


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.content = b"{}"
        self.text = str(payload)

    def json(self) -> dict:
        return self._payload


def _set_oauth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YOUTUBE_ACCESS_TOKEN", "access")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "refresh")
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "client")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "secret")


@pytest.mark.asyncio
async def test_ensure_broadcast_live_requires_oauth(monkeypatch):
    monkeypatch.delenv("YOUTUBE_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("YOUTUBE_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("YOUTUBE_CLIENT_ID", raising=False)
    monkeypatch.delenv("YOUTUBE_CLIENT_SECRET", raising=False)

    result = await api.ensure_broadcast_live("broadcast-1")

    assert result["ok"] is False
    assert result["reason"] == "missing_credentials"
    assert "YOUTUBE_ACCESS_TOKEN" in result["missing"]


@pytest.mark.asyncio
async def test_ensure_broadcast_live_transitions_after_active_ingest(monkeypatch):
    _set_oauth_env(monkeypatch)
    monkeypatch.setenv("YOUTUBE_BROADCAST_ID", "broadcast-1")
    calls: list[tuple[str, str, dict]] = []
    state = {"transitioned": False}

    class FakeClient:
        def __init__(self, timeout: float):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def request(self, method: str, url: str, **kwargs):
            params = kwargs.get("params") or {}
            calls.append((method, url, params))
            if url.endswith("/liveStreams"):
                return _FakeResponse(
                    200,
                    {
                        "items": [
                            {
                                "id": "stream-1",
                                "status": {"streamStatus": "active"},
                            }
                        ]
                    },
                )
            if url.endswith("/liveBroadcasts/transition"):
                state["transitioned"] = True
                return _FakeResponse(
                    200,
                    {
                        "id": "broadcast-1",
                        "status": {"lifeCycleStatus": "liveStarting"},
                    },
                )
            if url.endswith("/liveBroadcasts"):
                lifecycle = "liveStarting" if state["transitioned"] else "testing"
                return _FakeResponse(
                    200,
                    {
                        "items": [
                            {
                                "id": "broadcast-1",
                                "contentDetails": {"boundStreamId": "stream-1"},
                                "status": {"lifeCycleStatus": lifecycle},
                            }
                        ]
                    },
                )
            raise AssertionError(url)

    monkeypatch.setattr(api.httpx, "AsyncClient", FakeClient)

    result = await api.ensure_broadcast_live(timeout_s=0, poll_s=0)

    assert result["ok"] is True
    assert result["reason"] == "transitioned"
    assert result["lifeCycleStatus"] == "liveStarting"
    assert any(call[1].endswith("/liveBroadcasts/transition") for call in calls)


@pytest.mark.asyncio
async def test_ensure_broadcast_live_accepts_redundant_transition_when_live(monkeypatch):
    _set_oauth_env(monkeypatch)
    monkeypatch.setenv("YOUTUBE_BROADCAST_ID", "broadcast-1")
    state = {"broadcast_reads": 0}

    class FakeClient:
        def __init__(self, timeout: float):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def request(self, method: str, url: str, **kwargs):
            if url.endswith("/liveStreams"):
                return _FakeResponse(
                    200,
                    {
                        "items": [
                            {
                                "id": "stream-1",
                                "status": {"streamStatus": "active"},
                            }
                        ]
                    },
                )
            if url.endswith("/liveBroadcasts/transition"):
                return _FakeResponse(
                    403,
                    {
                        "error": {
                            "code": 403,
                            "errors": [{"reason": "redundantTransition"}],
                        }
                    },
                )
            if url.endswith("/liveBroadcasts"):
                state["broadcast_reads"] += 1
                lifecycle = "live" if state["broadcast_reads"] >= 2 else "testing"
                return _FakeResponse(
                    200,
                    {
                        "items": [
                            {
                                "id": "broadcast-1",
                                "contentDetails": {"boundStreamId": "stream-1"},
                                "status": {"lifeCycleStatus": lifecycle},
                            }
                        ]
                    },
                )
            raise AssertionError(url)

    monkeypatch.setattr(api.httpx, "AsyncClient", FakeClient)

    result = await api.ensure_broadcast_live(timeout_s=0, poll_s=0)

    assert result["ok"] is True
    assert result["reason"] == "already_live_redundant_transition"
    assert result["lifeCycleStatus"] == "live"
    assert result["streamStatus"] == "active"


@pytest.mark.asyncio
async def test_wait_for_bound_stream_active_reports_inactive(monkeypatch):
    _set_oauth_env(monkeypatch)

    class FakeClient:
        def __init__(self, timeout: float):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def request(self, method: str, url: str, **kwargs):
            if url.endswith("/liveBroadcasts"):
                return _FakeResponse(
                    200,
                    {
                        "items": [
                            {
                                "id": "broadcast-1",
                                "contentDetails": {"boundStreamId": "stream-1"},
                                "status": {"lifeCycleStatus": "ready"},
                            }
                        ]
                    },
                )
            if url.endswith("/liveStreams"):
                return _FakeResponse(
                    200,
                    {
                        "items": [
                            {
                                "id": "stream-1",
                                "status": {"streamStatus": "inactive"},
                            }
                        ]
                    },
                )
            raise AssertionError(url)

    monkeypatch.setattr(api.httpx, "AsyncClient", FakeClient)

    result = await api.wait_for_bound_stream_active(
        "broadcast-1",
        timeout_s=0,
        poll_s=0,
    )

    assert result["ok"] is False
    assert result["reason"] == "stream_not_active"
    assert result["streamStatus"] == "inactive"
