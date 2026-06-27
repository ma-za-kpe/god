"""
event_emitter.py - Publish structured events to NATS JetStream + persist to PostgreSQL.
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

WORLD_ID = os.getenv("WORLD_ID", "local-dev-world-1")
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
STREAM_NAME = "WORLD_EVENTS"
STREAM_SUBJECTS = ["world.*.events.>"]


class _NoopJetStream:
    async def publish(self, subject: str, data: bytes):
        class _Ack:
            seq = 0

        log.warning("Event publish skipped because NATS is unavailable: %s", subject)
        return _Ack()


class EventEmitter:
    def __init__(self):
        self.nc = None
        self.js = None
        self._stream_ready = False

    async def connect(self):
        self.nc = await nats.connect(NATS_URL)
        self.js = self.nc.jetstream()
        await self._ensure_stream()
        self._stream_ready = True
        log.info("EventEmitter connected -> %s", NATS_URL)

    async def _ensure_stream(self):
        if self.js is None:
            raise RuntimeError("JetStream client is not initialized")

        try:
            await self.js.find_stream(name=STREAM_NAME)
            self._stream_ready = True
            return
        except Exception as find_err:
            log.debug("JetStream stream lookup failed for %s: %s", STREAM_NAME, find_err)

        try:
            await self.js.add_stream(
                StreamConfig(
                    name=STREAM_NAME,
                    subjects=STREAM_SUBJECTS,
                    max_msgs=1_000_000,
                    max_bytes=512 * 1024 * 1024,
                )
            )
            log.info("Created JetStream stream: %s", STREAM_NAME)
        except Exception as add_err:
            # Another process may have created the stream during bootstrap.
            try:
                await self.js.find_stream(name=STREAM_NAME)
            except Exception:
                raise add_err

        self._stream_ready = True

    def is_ready(self) -> bool:
        return bool(
            self.nc is not None
            and not self.nc.is_closed
            and self.js is not None
            and self._stream_ready
            and not isinstance(self.js, _NoopJetStream)
        )

    async def _publish(self, subject: str, data: bytes):
        try:
            return await self.js.publish(subject, data)
        except Exception as exc:
            if self._looks_like_jetstream_bootstrap_error(exc):
                try:
                    self._stream_ready = False
                    await self._ensure_stream()
                    return await self.js.publish(subject, data)
                except Exception as retry_exc:
                    log.warning("Event publish failed after JetStream retry: %s", retry_exc)
            else:
                log.warning("Event publish failed after persistence: %s", exc)
            return await _NoopJetStream().publish(subject, data)

    @staticmethod
    def _looks_like_jetstream_bootstrap_error(exc: Exception) -> bool:
        name = exc.__class__.__name__
        msg = str(exc).lower()
        return (
            name in {"NoRespondersError", "NoStreamResponseError", "ServiceUnavailableError"}
            or "no response from stream" in msg
            or "no responders" in msg
            or "serviceunavailable" in msg
        )

    async def emit(self, category: str, event_type: str, payload: dict[str, Any]) -> str:
        full_type = f"{category}.{event_type}"

        # Narrator enhances drama feed without sanitizing ecology
        try:
            from .narrator import narrativize_event, should_emit_story

            story = narrativize_event(full_type, payload)
            if story:
                payload = {**payload, "narrative": story}
        except Exception:
            pass

        subject = f"world.{WORLD_ID}.events.{category}.{event_type}"
        event = {
            "event_id": str(uuid.uuid4()),
            "world_id": WORLD_ID,
            "category": category,
            "event_type": full_type,
            "timestamp": int(time.time()),
            **payload,
        }
        data = json.dumps(event, default=str).encode()
        ack = await self._publish(subject, data)
        log.debug("-> %s (seq=%s)", subject, ack.seq)

        # Persist to PostgreSQL so /events API can serve it
        await asyncio.get_running_loop().run_in_executor(None, self._persist, event)

        # WebSocket delta push for public observers
        try:
            from .world_stream import push_event

            asyncio.create_task(push_event(event))
        except Exception:
            pass

        # Companion narrative.story for significant drama
        try:
            from .narrator import should_emit_story

            narrative = event.get("narrative")
            if should_emit_story(full_type, narrative):
                story_event = {
                    "event_id": str(uuid.uuid4()),
                    "world_id": WORLD_ID,
                    "category": "narrative",
                    "event_type": "narrative.story",
                    "timestamp": int(time.time()),
                    "agent_id": event.get("agent_id"),
                    "source_event_id": event["event_id"],
                    "source_event_type": full_type,
                    "narrative": narrative,
                    "headline": narrative[:72],
                }
                await asyncio.get_event_loop().run_in_executor(None, self._persist, story_event)
                from .world_stream import push_event

                asyncio.create_task(push_event(story_event))
        except Exception:
            pass

        # Check for world firsts (non-blocking, best-effort)
        try:
            from .timeline import check_for_firsts

            asyncio.create_task(check_for_firsts(full_type, payload, event["event_id"]))
        except Exception:
            pass

        return event["event_id"]

    def _persist(self, event: dict):
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
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
                    psycopg2.extras.Json(
                        {
                            k: v
                            for k, v in event.items()
                            if k
                            not in (
                                "event_id",
                                "agent_id",
                                "event_type",
                                "timestamp",
                                "narrative",
                                "world_id",
                            )
                        }
                    ),
                    event["world_id"],
                ),
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            log.warning("Event persist failed: %s", e)

    async def close(self):
        if self.nc and not self.nc.is_closed:
            await self.nc.drain()


_emitter: EventEmitter | None = None
_emitter_lock: asyncio.Lock | None = None


def _get_emitter_lock() -> asyncio.Lock:
    global _emitter_lock
    if _emitter_lock is None:
        _emitter_lock = asyncio.Lock()
    return _emitter_lock


async def get_emitter() -> EventEmitter:
    global _emitter
    async with _get_emitter_lock():
        needs_refresh = (
            _emitter is None
            or (_emitter.nc is not None and _emitter.nc.is_closed)
            or not _emitter.is_ready()
        )
        if needs_refresh:
            emitter = EventEmitter()
            try:
                await emitter.connect()
                _emitter = emitter
            except Exception as exc:
                log.warning("EventEmitter NATS unavailable; events will persist only: %s", exc)
                try:
                    await emitter.close()
                except Exception:
                    pass
                emitter.js = _NoopJetStream()
                emitter._stream_ready = False
                _emitter = emitter
    return _emitter
