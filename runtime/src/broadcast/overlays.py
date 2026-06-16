"""Overlay card generation for OBS/browser sources."""

from __future__ import annotations

from typing import Any


def build_overlay(snapshot: dict[str, Any], scene: dict[str, Any]) -> dict[str, Any]:
    stats = snapshot.get("stats") or {}
    board = [
        {"label": "Alive", "value": int(stats.get("living_count") or 0)},
        {"label": "Born", "value": int(stats.get("total_born") or 0)},
        {"label": "Died", "value": int(stats.get("total_died") or 0)},
        {"label": "USDC", "value": round(float(stats.get("total_usdc_in_world") or 0), 2)},
        {"label": "Events", "value": int(stats.get("events_total") or 0)},
    ]
    tags = [
        scene.get("scene_name", "World Wide"),
        scene.get("layout", "default"),
        "live-weave",
    ]
    return {
        "title": "Live Stage",
        "subtitle": str(scene.get("headline") or "The world keeps moving."),
        "cards": board,
        "labels": tags,
    }
