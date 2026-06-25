"""Resilience and fallback status for the live stream stack."""

from __future__ import annotations

import os
import time
from typing import Any

import psycopg2
import psycopg2.extras

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID = os.getenv("WORLD_ID", "local-dev-world-1")


def _env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _fallback_mode(enabled: bool, live_value: str, fallback_value: str) -> str:
    return live_value if enabled else fallback_value


def _db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def _load_persisted_snapshot() -> dict[str, Any] | None:
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT snapshot, created_at
            FROM resilience_snapshots
            WHERE world_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (WORLD_ID,),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return None
        snapshot = dict(row["snapshot"] or {})
        snapshot["persisted_at"] = int(row["created_at"])
        snapshot["source"] = "persisted"
        return snapshot
    except Exception:
        return None


def _persist_snapshot(status: dict[str, Any]) -> None:
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO resilience_snapshots (world_id, created_at, snapshot)
            VALUES (%s, %s, %s)
            """,
            (
                WORLD_ID,
                int(time.time()),
                psycopg2.extras.Json(status),
            ),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass


def build_resilience_status(snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compose a deterministic local-first resilience summary."""
    persisted = _load_persisted_snapshot() or {}
    snapshot = {**persisted, **(snapshot or {})}

    try:
        from .world_stream import current_epoch, has_subscribers, stream_status
    except Exception:

        def current_epoch() -> int:
            return 0

        def has_subscribers() -> bool:
            return False

        def stream_status() -> dict[str, Any]:
            return {
                "epoch": 0,
                "subscriber_count": 0,
                "has_subscribers": False,
                "last_push_kind": None,
                "last_push_at": None,
                "last_snapshot_at": None,
                "last_delta_at": None,
                "push_age_seconds": None,
            }

    stream = stream_status()
    now = int(time.time())
    snapshot_epoch = int(snapshot.get("epoch") or 0)
    snapshot_age = max(0, now - snapshot_epoch) if snapshot_epoch else None
    live_stream = bool(has_subscribers())
    ws_mode = "live" if live_stream else "poll-fallback"

    try:
        from .broadcast import build_broadcast_status
    except Exception:
        build_broadcast_status = None
    try:
        from .nemo import build_nemo_status
    except Exception:
        build_nemo_status = None
    try:
        from .voice import build_voice_status
    except Exception:
        build_voice_status = None
    try:
        from .avatar import build_avatar_status
    except Exception:
        build_avatar_status = None
    try:
        from .twitch.adapter import build_twitch_status
    except Exception:
        build_twitch_status = None

    twitch_status = build_twitch_status() if build_twitch_status else {}
    nemo_status = build_nemo_status() if build_nemo_status else {}
    voice_status = build_voice_status() if build_voice_status else {}
    avatar_status = build_avatar_status() if build_avatar_status else {}
    broadcast_status = build_broadcast_status() if build_broadcast_status else {}

    nemo_live = bool(nemo_status.get("health", {}).get("ok")) or _env_flag("NEMO_ENABLED")
    voice_live = (
        bool(voice_status.get("health", {}).get("ok"))
        or _env_flag("VOICE_ENABLED")
        or bool(os.getenv("TTS_MODEL"))
    )
    avatar_live = bool(avatar_status.get("health", {}).get("ok")) or bool(
        avatar_status.get("enabled")
    )
    twitch_live = bool(twitch_status.get("health", {}).get("eventsub", {}).get("ok")) or bool(
        twitch_status.get("health", {}).get("helix", {}).get("ok")
    )
    obs_live = bool(broadcast_status.get("health", {}).get("ok")) or _env_flag("OBS_ENABLED")

    fallbacks = {
        "nemo": _fallback_mode(nemo_live, "live", "stub"),
        "voice": _fallback_mode(voice_live, "live", "stub"),
        "avatar": _fallback_mode(avatar_live, "live", "stub"),
        "twitch": _fallback_mode(twitch_live, "live", "stub"),
        "obs": _fallback_mode(obs_live, "live", "dry-run"),
        "stream": ws_mode,
    }

    if live_stream and stream.get("last_push_at") is None:
        tier = "warming-up"
    elif live_stream:
        tier = "healthy"
    elif stream.get("last_push_at") is not None:
        tier = "degraded"
    else:
        tier = "cold-start"

    notes = [
        "Local-first runtime remains authoritative.",
        "Twitch, OBS, NeMo, and voice can remain stubbed until their adapters are ready.",
    ]
    if not live_stream:
        notes.append("No active WS subscribers, so the observer is using poll fallback.")
    if snapshot_age is not None and snapshot_age > 60:
        notes.append(f"Snapshot is {snapshot_age}s old and should be refreshed.")
    if not nemo_live:
        notes.append("NeMo is not enabled yet, so the director layer remains stubbed.")
    if not voice_live:
        notes.append("Voice is not enabled yet, so the stream will remain text-first.")
    if not avatar_live:
        notes.append(
            "Avatar rendering is not enabled yet, so the cast is visual-only in the browser stage."
        )

    status = {
        "tier": tier,
        "epoch": current_epoch(),
        "snapshot_age_seconds": snapshot_age,
        "stream": stream,
        "fallbacks": fallbacks,
        "notes": notes,
        "local_first": True,
        "restart_safe": bool(persisted),
        "source": snapshot.get("source", "live"),
        "persisted_at": snapshot.get("persisted_at"),
        "adapters": {
            "twitch": twitch_status,
            "nemo": nemo_status,
            "voice": voice_status,
            "avatar": avatar_status,
            "broadcast": broadcast_status,
        },
    }
    _persist_snapshot(status)
    return status
