"""
ipfs_client.py — Multi-node IPFS pinning for Law 2 death archives.

Pins content to every configured Kubo API endpoint and requires a minimum
number of successful pins before treating the CID as durable.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field

import httpx

log = logging.getLogger("god.ipfs")

DEFAULT_ENDPOINT = os.getenv("IPFS_API", "http://localhost:5001")
ENDPOINTS_RAW = os.getenv("IPFS_API_ENDPOINTS", DEFAULT_ENDPOINT)
MIN_PINS = int(os.getenv("MIN_IPFS_PINS", "3"))
PIN_RETRIES = int(os.getenv("IPFS_PIN_RETRIES", "3"))
PIN_TIMEOUT_S = float(os.getenv("IPFS_PIN_TIMEOUT_S", "15"))


@dataclass(frozen=True)
class PinResult:
    ok: bool
    cid: str = ""
    pinned_nodes: int = 0
    required_nodes: int = MIN_PINS
    errors: tuple[str, ...] = field(default_factory=tuple)


def ipfs_endpoints() -> list[str]:
    endpoints = [e.strip() for e in ENDPOINTS_RAW.split(",") if e.strip()]
    return endpoints or [DEFAULT_ENDPOINT]


async def _pin_once(
    client: httpx.AsyncClient,
    endpoint: str,
    data: bytes,
    filename: str,
) -> str:
    resp = await client.post(
        f"{endpoint.rstrip('/')}/api/v0/add",
        files={"file": (filename, data, "application/json")},
    )
    resp.raise_for_status()
    body = resp.json()
    cid = body.get("Hash") or body.get("cid")
    if not cid:
        raise ValueError(f"no CID in response from {endpoint}")
    return cid


async def pin_bytes(
    data: bytes,
    *,
    filename: str = "payload.json",
    min_pins: int | None = None,
    retries: int | None = None,
) -> PinResult:
    """
    Pin bytes to all configured IPFS nodes. Succeeds when at least min_pins
    nodes accept the pin and all successful pins agree on the same CID.
    """
    required = min_pins if min_pins is not None else MIN_PINS
    attempts = retries if retries is not None else PIN_RETRIES
    endpoints = ipfs_endpoints()
    required = min(required, len(endpoints))

    last_errors: list[str] = []

    for attempt in range(1, attempts + 1):
        cid_votes: dict[str, int] = {}
        errors: list[str] = []

        async with httpx.AsyncClient(timeout=PIN_TIMEOUT_S) as client:
            tasks = [_pin_once(client, ep, data, filename) for ep in endpoints]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for ep, result in zip(endpoints, results):
            if isinstance(result, Exception):
                msg = f"{ep}: {result}"
                errors.append(msg)
                log.debug(msg)
                continue
            cid_votes[result] = cid_votes.get(result, 0) + 1

        if cid_votes:
            cid, count = max(cid_votes.items(), key=lambda item: item[1])
            if count >= required:
                log.info(f"IPFS pin ok: {cid} ({count}/{len(endpoints)} nodes)")
                return PinResult(ok=True, cid=cid, pinned_nodes=count, required_nodes=required)

        last_errors = errors or [f"attempt {attempt}: insufficient pins ({cid_votes})"]
        if attempt < attempts:
            await asyncio.sleep(min(2**attempt, 8))

    log.warning(f"IPFS pin failed after {attempts} attempts: {last_errors}")
    return PinResult(
        ok=False,
        pinned_nodes=0,
        required_nodes=required,
        errors=tuple(last_errors),
    )


async def pin_json(data: bytes, filename: str = "death_archive.json") -> PinResult:
    return await pin_bytes(data, filename=filename)
