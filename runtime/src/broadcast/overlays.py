"""Overlay card generation for OBS/browser sources."""

from __future__ import annotations

from typing import Any


def build_overlay(snapshot: dict[str, Any], scene: dict[str, Any]) -> dict[str, Any]:
    audience = snapshot.get("audience") or {}
    content_bank = snapshot.get("content_bank") or {}

    tags = [
        "avatars",
        "drama",
        scene.get("scene_name", "World Wide"),
        scene.get("layout", "default"),
    ]
    return {
        "title": "Avatar Stage",
        "subtitle": str(
            content_bank.get("summary")
            or audience.get("story_hook")
            or scene.get("headline")
            or "Watch the cast."
        ),
        "cards": (),
        "labels": tags,
    }
