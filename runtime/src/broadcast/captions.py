"""Caption generation for the stage surface."""

from __future__ import annotations

from typing import Any


def build_caption(snapshot: dict[str, Any], scene: dict[str, Any]) -> dict[str, Any]:
    stats = snapshot.get("stats") or {}
    nemo = snapshot.get("nemo") or {}
    showrunner = snapshot.get("showrunner") or {}
    audience = snapshot.get("audience") or {}
    top_earners = stats.get("top_earners") or []
    top_name = top_earners[0].get("current_name") if top_earners else "None"

    headline = str(scene.get("headline") or showrunner.get("headline") or "The world keeps moving.")
    subhead = str(
        audience.get("story_hook")
        or nemo.get("director_note")
        or showrunner.get("audience_prompt")
        or "Watch the cast."
    )
    lower_third = f"{scene.get('speaker', 'Narrator')} · {scene.get('scene_name', 'World Wide')}"
    ticker_lines = [
        f"{scene.get('speaker', 'Narrator')} takes the stage.",
        f"Cast {int(stats.get('living_count') or 0)} | Pressure {int(audience.get('chat_pressure') or 0)}",
        f"Top earner {top_name}",
    ]
    return {
        "headline": headline,
        "subhead": subhead,
        "lower_third": lower_third,
        "ticker_lines": ticker_lines,
    }
