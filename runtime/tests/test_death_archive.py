"""Death archive and IPFS cluster pinning tests — issue #59."""

import json
from unittest.mock import patch

import pytest
from ipfs_client import ipfs_endpoints, pin_bytes


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
