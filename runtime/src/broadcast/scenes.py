"""OBS scene selection for the live broadcast surface."""

from __future__ import annotations

from typing import Any

SCENE_MAP = {
    "graveyard-cut": {
        "scene_id": "obs/graveyard-cut",
        "scene_name": "Graveyard Cut",
        "layout": "dramatic-close-up",
        "fallback_scene": "obs/world-wide",
    },
    "banter-table": {
        "scene_id": "obs/banter-table",
        "scene_name": "Banter Table",
        "layout": "talk-show",
        "fallback_scene": "obs/world-wide",
    },
    "ensemble-stage": {
        "scene_id": "obs/ensemble-stage",
        "scene_name": "Ensemble Stage",
        "layout": "avatar-led-grid",
        "fallback_scene": "obs/world-wide",
    },
    "void-silence": {
        "scene_id": "obs/void-silence",
        "scene_name": "Void Silence",
        "layout": "minimal",
        "fallback_scene": "obs/world-wide",
    },
    "world-wide": {
        "scene_id": "obs/world-wide",
        "scene_name": "World Wide",
        "layout": "default",
        "fallback_scene": "obs/world-wide",
    },
}


def _source_scene(snapshot: dict[str, Any]) -> dict[str, Any]:
    nemo = snapshot.get("nemo") or {}
    showrunner = snapshot.get("showrunner") or {}
    return {
        "scene": str(nemo.get("scene") or showrunner.get("scene") or "world-wide"),
        "speaker": str(nemo.get("speaker") or showrunner.get("speaker") or "Narrator"),
        "headline": str(
            nemo.get("headline") or showrunner.get("headline") or "The world keeps moving."
        ),
        "audience_prompt": str(
            nemo.get("audience_prompt") or showrunner.get("audience_prompt") or "Watch closely."
        ),
    }


def select_scene(snapshot: dict[str, Any]) -> dict[str, Any]:
    source = _source_scene(snapshot)
    scene_key = source["scene"]
    profile = SCENE_MAP.get(scene_key, SCENE_MAP["world-wide"]).copy()
    profile.update(
        {
            "scene_key": scene_key,
            "speaker": source["speaker"],
            "headline": source["headline"],
            "audience_prompt": source["audience_prompt"],
            "reason": f"source={scene_key}",
        }
    )
    return profile
