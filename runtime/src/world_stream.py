"""
world_stream.py — WebSocket fanout for public observer clients.

Snapshot on connect, delta pushes on new events. Decouples observation from polling.
"""

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

log = logging.getLogger("god.stream")

_subscribers: set[WebSocket] = set()
_lock = asyncio.Lock()
_epoch = 0


def current_epoch() -> int:
    return _epoch


def bump_epoch():
    global _epoch
    _epoch += 1


async def subscribe(ws: WebSocket):
    await ws.accept()
    async with _lock:
        _subscribers.add(ws)
    log.debug(f"WS subscriber connected ({len(_subscribers)} total)")


async def unsubscribe(ws: WebSocket):
    async with _lock:
        _subscribers.discard(ws)
    log.debug(f"WS subscriber disconnected ({len(_subscribers)} total)")


async def broadcast(message: dict[str, Any]):
    """Push JSON to all connected observers. Drops dead sockets."""
    if not _subscribers:
        return
    data = json.dumps(message, default=str)
    dead: list[WebSocket] = []
    async with _lock:
        clients = list(_subscribers)
    for ws in clients:
        try:
            await ws.send_text(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        await unsubscribe(ws)


async def push_event(event: dict[str, Any]):
    bump_epoch()
    await broadcast(
        {
            "type": "delta",
            "epoch": _epoch,
            "events": [event],
            "messages": [],
        }
    )


async def push_snapshot(snapshot: dict[str, Any]):
    bump_epoch()
    await broadcast(
        {
            "type": "snapshot",
            "epoch": _epoch,
            **snapshot,
        }
    )


def has_subscribers() -> bool:
    return bool(_subscribers)
