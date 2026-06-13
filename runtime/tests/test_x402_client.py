"""x402 service client tests — issue #58."""

from typing import Optional
from unittest.mock import AsyncMock, patch

import pytest
from services.client import invoke_x402_service


class _FakeResponse:
    def __init__(self, status_code: int, body: Optional[dict] = None, text: str = ""):
        self.status_code = status_code
        self._body = body or {}
        self.text = text or str(body)

    def json(self):
        return self._body


@pytest.mark.asyncio
async def test_invoke_completes_402_flow():
    responses = [
        _FakeResponse(402, {"error": "Payment Required"}),
        _FakeResponse(200, {"service": "world_stats", "status": "ok"}),
    ]
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=responses)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("services.client.httpx.AsyncClient", return_value=mock_client):
        result = await invoke_x402_service("http://localhost:8888/services/s1/world_stats", "0xabc")

    assert result.ok
    assert result.status_code == 200
    assert result.body["service"] == "world_stats"
    assert mock_client.get.call_count == 2


@pytest.mark.asyncio
async def test_invoke_rejects_missing_wallet():
    result = await invoke_x402_service("http://x", "")
    assert not result.ok
    assert result.error == "missing_payer_wallet"
