"""Death archive and IPFS cluster pinning tests — issue #59."""

import json
from unittest.mock import patch

import pytest
from ipfs_client import _cid_from_add_line, _pin_once, _verify_once, ipfs_endpoints, pin_bytes


class _StreamingAddResponse:
    def __init__(self):
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.closed = True

    def raise_for_status(self):
        return None

    async def aiter_bytes(self):
        yield b'{"Name":"voice.wav","Hash":"QmStreamCID123","Size":"42"}\n'
        raise AssertionError("_pin_once should close after the first streamed CID")


class _StreamingAddClient:
    def __init__(self):
        self.response = _StreamingAddResponse()
        self.request = None

    def stream(self, method, url, *, params, files):
        self.request = {
            "method": method,
            "url": url,
            "params": params,
            "files": files,
        }
        return self.response


class _StreamingBlockStatResponse:
    def __init__(self):
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.closed = True

    def raise_for_status(self):
        return None

    async def aiter_bytes(self):
        yield b'{"Key":"QmStreamCID123","Size":42}\n'
        raise AssertionError("_verify_once should close after the first streamed block stat")


class _StreamingBlockStatClient:
    def __init__(self):
        self.response = _StreamingBlockStatResponse()
        self.request = None

    def stream(self, method, url, *, params):
        self.request = {
            "method": method,
            "url": url,
            "params": params,
        }
        return self.response


@pytest.mark.asyncio
async def test_pin_requires_minimum_nodes():
    data = json.dumps({"soul_id": "test"}).encode()

    async def fake_pin(client, endpoint, payload, filename):
        if "node-3" in endpoint:
            raise ConnectionError("node down")
        return "QmTestCID123"

    with patch(
        "ipfs_client.ipfs_endpoints",
        return_value=["http://node-1", "http://node-2", "http://node-3"],
    ):
        with patch("ipfs_client._pin_once", side_effect=fake_pin):
            with patch("ipfs_client._verify_replication", return_value=(2, [])):
                result = await pin_bytes(data, min_pins=2, retries=1)
    assert result.ok
    assert result.cid == "QmTestCID123"
    assert result.pinned_nodes == 2
    assert result.verified_nodes == 2


@pytest.mark.asyncio
async def test_pin_fails_when_insufficient_nodes():
    data = b"{}"

    async def always_fail(client, endpoint, payload, filename):
        raise ConnectionError("down")

    with patch("ipfs_client.ipfs_endpoints", return_value=["http://n1", "http://n2"]):
        with patch("ipfs_client._pin_once", side_effect=always_fail):
            with patch("ipfs_client._verify_replication", return_value=(0, [])):
                result = await pin_bytes(data, min_pins=2, retries=1)
    assert not result.ok
    assert result.cid == ""


@pytest.mark.asyncio
async def test_pin_fails_when_replication_not_verified():
    data = json.dumps({"soul_id": "test"}).encode()

    async def fake_pin(client, endpoint, payload, filename):
        return "QmTestCID123"

    with patch(
        "ipfs_client.ipfs_endpoints",
        return_value=["http://node-1", "http://node-2", "http://node-3"],
    ):
        with patch("ipfs_client._pin_once", side_effect=fake_pin):
            with patch("ipfs_client._verify_replication", return_value=(1, [])):
                result = await pin_bytes(data, min_pins=2, retries=1)

    assert not result.ok
    assert result.cid == ""
    assert result.verified_nodes == 0


def test_endpoints_parses_comma_list():
    with patch("ipfs_client.ENDPOINTS_RAW", "http://a:5001, http://b:5001"):
        eps = ipfs_endpoints()
    assert eps == ["http://a:5001", "http://b:5001"]


def test_add_response_parser_reads_kubo_hash_line():
    line = b'{"Name":"avatar.png","Hash":"QmAvatarCID123","Size":"100"}\n'
    assert _cid_from_add_line(line, "http://node-1") == "QmAvatarCID123"


@pytest.mark.asyncio
async def test_pin_once_returns_from_first_streamed_add_result():
    client = _StreamingAddClient()

    cid = await _pin_once(client, "http://node-1:5001", b"audio", "voice.wav")

    assert cid == "QmStreamCID123"
    assert client.response.closed
    assert client.request == {
        "method": "POST",
        "url": "http://node-1:5001/api/v0/add",
        "params": {"pin": "true"},
        "files": {"file": ("voice.wav", b"audio", "application/octet-stream")},
    }


@pytest.mark.asyncio
async def test_verify_once_returns_from_first_streamed_block_stat_result():
    client = _StreamingBlockStatClient()

    verified = await _verify_once(client, "http://node-1:5001", "QmStreamCID123")

    assert verified
    assert client.response.closed
    assert client.request == {
        "method": "POST",
        "url": "http://node-1:5001/api/v0/block/stat",
        "params": {"arg": "QmStreamCID123"},
    }
