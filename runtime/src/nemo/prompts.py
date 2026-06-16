"""Prompt builders for the NeMo director layer."""

from __future__ import annotations

from typing import Any


def build_director_prompt(snapshot: dict[str, Any], showrunner_plan: dict[str, Any]) -> str:
    stats = snapshot.get("stats") or {}
    cues = showrunner_plan.get("cues") or []
    cue_lines = []
    for cue in cues[:3]:
        cue_lines.append(
            f"- {cue.get('cue_type')}: {cue.get('headline', '')} [{', '.join(cue.get('tags') or [])}]"
        )

    return "\n".join(
        [
            "You are the live stream director for a Twitch-native agentic world.",
            "Keep the broadcast coherent, responsive, and grounded in the live world.",
            f"Scene: {showrunner_plan.get('scene', 'world-wide')}",
            f"Speaker: {showrunner_plan.get('speaker', 'Narrator')}",
            f"Headline: {showrunner_plan.get('headline', 'The world continues.')}",
            f"Audience prompt: {showrunner_plan.get('audience_prompt', 'Watch closely.')}",
            f"Living agents: {int(stats.get('living_count') or 0)}",
            f"Events total: {int(stats.get('events_total') or 0)}",
            "Relevant cues:",
            *cue_lines,
            "Return a concise, stream-safe instruction set.",
        ]
    )
