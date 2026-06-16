"""Overlay card generation for OBS/browser sources."""

from __future__ import annotations

from typing import Any


def build_overlay(snapshot: dict[str, Any], scene: dict[str, Any]) -> dict[str, Any]:
    stats = snapshot.get("stats") or {}
    audience = snapshot.get("audience") or {}
    board = [
        {"label": "Alive", "value": int(stats.get("living_count") or 0)},
        {"label": "Born", "value": int(stats.get("total_born") or 0)},
        {"label": "Died", "value": int(stats.get("total_died") or 0)},
        {"label": "USDC", "value": round(float(stats.get("total_usdc_in_world") or 0), 2)},
        {"label": "Events", "value": int(stats.get("events_total") or 0)},
        {"label": "Patrons", "value": int(audience.get("unique_supporters_24h") or 0)},
        {"label": "Chat", "value": int(audience.get("chat_pressure") or 0)},
        {"label": "Hype", "value": round(float(audience.get("hype_index") or 0), 1)},
    ]
    tags = [
        scene.get("scene_name", "World Wide"),
        scene.get("layout", "default"),
        "live-weave",
        "patronage",
    ]
    return {
        "title": "Live Stage",
        "subtitle": str(
            audience.get("story_hook")
            or scene.get("headline")
            or "The world keeps moving."
        ),
        "cards": board,
        "labels": tags,
    }
