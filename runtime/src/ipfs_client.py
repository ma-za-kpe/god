"""
ipfs_client.py — Multi-node IPFS pinning for Law 2 death archives.

Pins content to every configured Kubo API endpoint and requires a minimum
number of successful pins before treating the CID as durable.
"""

from __future__ import annotations

import asyncio
import json
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
MAX_STREAM_RESPONSE_BYTES = int(
    os.getenv("IPFS_STREAM_RESPONSE_MAX_BYTES", os.getenv("IPFS_ADD_RESPONSE_MAX_BYTES", "1048576"))
)


@dataclass(frozen=True)
class PinResult:
    ok: bool
    cid: str = ""
    pinned_nodes: int = 0
    verified_nodes: int = 0
    required_nodes: int = MIN_PINS
    errors: tuple[str, ...] = field(default_factory=tuple)


def ipfs_endpoints() -> list[str]:
    endpoints = [e.strip() for e in ENDPOINTS_RAW.split(",") if e.strip()]
    return endpoints or [DEFAULT_ENDPOINT]


def _json_object_from_line(line: bytes, endpoint: str) -> dict | None:
    line = line.strip()
    if not line:
        return None
    try:
        body = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(body, dict):
        raise ValueError(f"unexpected IPFS response from {endpoint}")
    return body


async def _first_streamed_json(
    client: httpx.AsyncClient,
    endpoint: str,
    url: str,
    *,
    params: dict[str, str] | None = None,
    files: dict[str, tuple[str, bytes, str]] | None = None,
) -> dict:
    buffer = b""
    kwargs = {}
    if params is not None:
        kwargs["params"] = params
    if files is not None:
        kwargs["files"] = files

    async with client.stream("POST", url, **kwargs) as resp:
        resp.raise_for_status()
        async for chunk in resp.aiter_bytes():
            buffer += chunk

            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                body = _json_object_from_line(line, endpoint)
                if body is not None:
                    return body

            body = _json_object_from_line(buffer, endpoint)
            if body is not None:
                return body

            if len(buffer) > MAX_STREAM_RESPONSE_BYTES:
                raise ValueError(f"IPFS response from {endpoint} exceeded byte limit")

    body = _json_object_from_line(buffer, endpoint)
    if body is not None:
        return body
    raise ValueError(f"empty IPFS response from {endpoint}")


def _cid_from_add_line(line: bytes, endpoint: str) -> str | None:
    body = _json_object_from_line(line, endpoint)
    if body is None:
        return None
    cid = body.get("Hash") or body.get("hash") or body.get("Cid") or body.get("cid")
    if not cid:
        raise ValueError(f"no CID in response from {endpoint}")
    return str(cid)


async def _pin_once(
    client: httpx.AsyncClient,
    endpoint: str,
    data: bytes,
    filename: str,
) -> str:
    url = f"{endpoint.rstrip('/')}/api/v0/add"
    body = await _first_streamed_json(
        client,
        endpoint,
        url,
        params={"pin": "true"},
        files={"file": (filename, data, "application/octet-stream")},
    )
    cid = body.get("Hash") or body.get("hash") or body.get("Cid") or body.get("cid")
    if cid:
        return str(cid)
    raise ValueError(f"no CID in response from {endpoint}")


async def _verify_once(
    client: httpx.AsyncClient,
    endpoint: str,
    cid: str,
) -> bool:
    body = await _first_streamed_json(
        client,
        endpoint,
        f"{endpoint.rstrip('/')}/api/v0/pin/ls",
        params={"arg": cid},
    )
    keys = body.get("Keys") or body.get("keys") or {}
    if isinstance(keys, dict) and cid in keys:
        return True
    pins = body.get("Pins") or body.get("pins") or []
    if isinstance(pins, list) and cid in pins:
        return True
    if str(body.get("Type") or body.get("type") or "").lower() == "recursive":
        return True
    return False


async def _verify_replication(
    cid: str,
    endpoints: list[str],
) -> tuple[int, list[str]]:
    verified = 0
    errors: list[str] = []
    async with httpx.AsyncClient(timeout=PIN_TIMEOUT_S) as client:
        tasks = [_verify_once(client, ep, cid) for ep in endpoints]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    for ep, result in zip(endpoints, results):
        if isinstance(result, Exception):
            msg = f"{ep}: {result}"
            errors.append(msg)
            log.debug(msg)
            continue
        if result:
            verified += 1
    return verified, errors


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
                verified, verify_errors = await _verify_replication(cid, endpoints)
                errors.extend(verify_errors)
                if verified >= required:
                    log.info(f"IPFS pin ok: {cid} ({verified}/{len(endpoints)} nodes verified)")
                    return PinResult(
                        ok=True,
                        cid=cid,
                        pinned_nodes=count,
                        verified_nodes=verified,
                        required_nodes=required,
                    )
                errors.append(f"verification failed: {verified}/{required} nodes confirmed")

        last_errors = errors or [f"attempt {attempt}: insufficient pins ({cid_votes})"]
        if attempt < attempts:
            await asyncio.sleep(min(2**attempt, 8))

    log.warning(f"IPFS pin failed after {attempts} attempts: {last_errors}")
    return PinResult(
        ok=False,
        pinned_nodes=0,
        verified_nodes=0,
        required_nodes=required,
        errors=tuple(last_errors),
    )


async def pin_json(data: bytes, filename: str = "death_archive.json") -> PinResult:
    return await pin_bytes(data, filename=filename)
