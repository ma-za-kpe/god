"""Caption generation for the stage surface."""

from __future__ import annotations

from typing import Any


def build_caption(snapshot: dict[str, Any], scene: dict[str, Any]) -> dict[str, Any]:
    stats = snapshot.get("stats") or {}
    nemo = snapshot.get("nemo") or {}
    showrunner = snapshot.get("showrunner") or {}
    audience = snapshot.get("audience") or {}
    content_bank = snapshot.get("content_bank") or {}
    top_earners = stats.get("top_earners") or []
    top_name = top_earners[0].get("current_name") if top_earners else "None"
    ticker_lines = [
        f"Living {int(stats.get('living_count') or 0)} | Events {int(stats.get('events_total') or 0)}",
        f"Transfers 24h {int(stats.get('transfers_24h') or 0)} | Service buys {int(stats.get('service_purchases_24h') or 0)}",
        f"Top earner {top_name}",
        f"Audience {int(audience.get('chat_pressure') or 0)} chat beats | Patronage {float(audience.get('patronage_index') or 0):.1f}",
        f"Future arcs {int(content_bank.get('arc_count') or 0)} | Horizon {int(content_bank.get('horizon_days') or 0)}d",
    ]
    headline = str(scene.get("headline") or showrunner.get("headline") or "The world keeps moving.")
    subhead = str(
        audience.get("story_hook")
        or nemo.get("director_note")
        or showrunner.get("audience_prompt")
        or "Watch closely."
    )
    lower_third = f"{scene.get('scene_name', 'World Wide')} · {scene.get('speaker', 'Narrator')}"
    return {
        "headline": headline,
        "subhead": subhead,
        "lower_third": lower_third,
        "ticker_lines": ticker_lines,
    }
