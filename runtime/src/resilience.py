"""Resilience and fallback status for the live stream stack."""

from __future__ import annotations

import os
import time
from typing import Any


def _env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _fallback_mode(enabled: bool, live_value: str, fallback_value: str) -> str:
    return live_value if enabled else fallback_value


def build_resilience_status(snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compose a deterministic local-first resilience summary."""
    snapshot = snapshot or {}

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

    nemo_live = _env_flag("NEMO_ENABLED") or bool(os.getenv("NEMO_ENDPOINT"))
    voice_live = _env_flag("VOICE_ENABLED") or bool(os.getenv("TTS_MODEL"))
    twitch_live = _env_flag("TWITCH_EVENTSUB_ENABLED") or bool(
        os.getenv("TWITCH_EVENTSUB_TOKEN") or os.getenv("TWITCH_BOT_TOKEN")
    )
    obs_live = _env_flag("OBS_ENABLED") or bool(os.getenv("OBS_WEBSOCKET_URL"))

    fallbacks = {
        "nemo": _fallback_mode(nemo_live, "live", "stub"),
        "voice": _fallback_mode(voice_live, "live", "stub"),
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

    return {
        "tier": tier,
        "epoch": current_epoch(),
        "snapshot_age_seconds": snapshot_age,
        "stream": stream,
        "fallbacks": fallbacks,
        "notes": notes,
        "local_first": True,
    }
