"""
event_emitter.py — Publish structured events to NATS JetStream + persist to PostgreSQL.
Subject: world.{world_id}.events.{category}.{event_type}
"""
import asyncio
import json
import logging
import os
import time
import uuid
from typing import Any

import nats
import psycopg2
import psycopg2.extras
from nats.js.api import StreamConfig

log = logging.getLogger("god.events")

WORLD_ID     = os.getenv("WORLD_ID",     "local-dev-world-1")
NATS_URL     = os.getenv("NATS_URL",     "nats://localhost:4222")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
STREAM_NAME  = "WORLD_EVENTS"


class EventEmitter:
    def __init__(self):
        self.nc = None
        self.js = None

    async def connect(self):
        self.nc = await nats.connect(NATS_URL)
        self.js = self.nc.jetstream()
        try:
            await self.js.find_stream(name=STREAM_NAME)
        except Exception:
            await self.js.add_stream(StreamConfig(
                name=STREAM_NAME,
                subjects=["world.*.events.>"],
                max_msgs=1_000_000,
                max_bytes=512 * 1024 * 1024,
            ))
            log.info(f"Created JetStream stream: {STREAM_NAME}")
        log.info(f"EventEmitter connected → {NATS_URL}")

    async def emit(self, category: str, event_type: str, payload: dict[str, Any]) -> str:
        subject = f"world.{WORLD_ID}.events.{category}.{event_type}"
        event = {
            "event_id": str(uuid.uuid4()),
            "world_id": WORLD_ID,
            "category": category,
            "event_type": f"{category}.{event_type}",
            "timestamp": int(time.time()),
            **payload,
        }
        data = json.dumps(event, default=str).encode()
        ack = await self.js.publish(subject, data)
        log.debug(f"→ {subject} (seq={ack.seq})")

        # Persist to PostgreSQL so /events API can serve it
        await asyncio.get_event_loop().run_in_executor(None, self._persist, event)

        # Check for world firsts (non-blocking, best-effort)
        try:
            from .timeline import check_for_firsts
            asyncio.create_task(check_for_firsts(
                f"{category}.{event_type}", payload, event["event_id"]
            ))
        except Exception:
            pass

        return event["event_id"]

    def _persist(self, event: dict):
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur  = conn.cursor()
            cur.execute(
                """
                INSERT INTO events (event_id, agent_id, event_type, timestamp, narrative, payload, world_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_id) DO NOTHING
                """,
                (
                    event["event_id"],
                    event.get("agent_id"),
                    event["event_type"],
                    event["timestamp"],
                    event.get("narrative"),
                    psycopg2.extras.Json({k: v for k, v in event.items()
                                         if k not in ("event_id", "agent_id", "event_type",
                                                       "timestamp", "narrative", "world_id")}),
                    event["world_id"],
                ),
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            log.warning(f"Event persist failed: {e}")

    async def close(self):
        if self.nc and not self.nc.is_closed:
            await self.nc.drain()


_emitter: EventEmitter | None = None


async def get_emitter() -> EventEmitter:
    global _emitter
    if _emitter is None or (_emitter.nc is not None and _emitter.nc.is_closed):
        _emitter = EventEmitter()
        await _emitter.connect()
    return _emitter
