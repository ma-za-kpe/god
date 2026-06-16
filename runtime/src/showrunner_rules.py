"""showrunner_rules.py - deterministic heuristics for selecting broadcast cues."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

try:  # pragma: no cover - package import path in runtime
    from .showrunner_state import ShowrunnerCue
except ImportError:  # pragma: no cover - flat import path in tests
    from showrunner_state import ShowrunnerCue

PRIORITY_BY_EVENT = {
    "world.genesis": 100,
    "lifecycle.world.genesis": 100,
    "lifecycle.agent.born": 75,
    "lifecycle.agent.died": 95,
    "lifecycle.agent.reproduced": 70,
    "economy.service.purchased": 85,
    "economy.deal.settled": 80,
    "economy.deal.failed": 60,
    "economy.rent.paid": 55,
    "economy.rent.missed": 90,
    "economy.agent.transfer": 65,
    "economy.token.deployed": 70,
    "social.agent.broadcast": 76,
    "social.agent.message_sent": 50,
    "social.coalition.formed": 84,
    "agent.throttled": 88,
    "cognitive.agent.thought": 20,
}


def event_priority(event_type: str) -> int:
    return PRIORITY_BY_EVENT.get(event_type, 10)


def select_scene(cues: Iterable[ShowrunnerCue], state: dict[str, Any]) -> str:
    cue_list = list(cues)
    top_tags = set(cue_list[0].tags) if cue_list else set()
    if "death" in top_tags:
        return "graveyard-cut"
    if "economy" in top_tags:
        return "economy-pan"
    if "social" in top_tags:
        return "banter-table"
    if state.get("living_count", 0) == 0:
        return "void-silence"
    if state.get("transfers_24h", 0) > 0:
        return "market-watch"
    return "world-wide"


def speaker_for(cues: list[ShowrunnerCue], snapshot: dict[str, Any]) -> str:
    if not cues:
        return "Narrator"
    best = max(cues, key=lambda cue: (cue.priority, cue.agent_name, cue.agent_id))
    return best.agent_name or best.agent_id or "Narrator"


def audience_prompt_for(cues: list[ShowrunnerCue], snapshot: dict[str, Any]) -> str:
    if not cues:
        return "Watch the world for the next major turn."
    best = max(cues, key=lambda cue: (cue.priority, cue.agent_name, cue.agent_id))
    if "patronage" in best.tags or "economy" in best.tags:
        return "Chat can weigh in on the next economic move."
    if "death" in best.tags:
        return "Hold the line and watch who responds."
    if "social" in best.tags:
        return "Let chat decide who is winning the argument."
    return "Watch for the next decisive shift."


def event_to_cue(event: dict[str, Any]) -> ShowrunnerCue | None:
    event_type = str(event.get("event_type") or event.get("type") or "").strip()
    if not event_type:
        return None
    payload = event.get("payload") or {}
    if not isinstance(payload, dict):
        payload = {}

    if event_type not in PRIORITY_BY_EVENT:
        return None

    agent_id = str(event.get("agent_id") or payload.get("agent_id") or "")
    agent_name = str(
        payload.get("name")
        or payload.get("agent_name")
        or event.get("agent_name")
        or agent_id
        or "Narrator"
    )
    headline = str(payload.get("narrative") or event.get("narrative") or event_type)
    details = str(
        payload.get("thought")
        or payload.get("content")
        or payload.get("summary")
        or headline
    )
    tags = _tags_for_event(event_type, payload)
    event_id = str(event.get("event_id") or payload.get("event_id") or "")

    return ShowrunnerCue(
        cue_type=event_type,
        headline=headline,
        details=details,
        priority=event_priority(event_type),
        agent_id=agent_id,
        agent_name=agent_name,
        tags=tags,
        source_event_ids=(event_id,) if event_id else (),
    )


def _tags_for_event(event_type: str, payload: dict[str, Any]) -> tuple[str, ...]:
    tags: list[str] = []
    if event_type.startswith("economy.") or event_type == "world.genesis":
        tags.append("economy")
    if "rent" in event_type or "deal" in event_type or "token" in event_type:
        tags.append("economy")
    if "death" in event_type or "died" in event_type:
        tags.append("death")
    if event_type.startswith("social."):
        tags.append("social")
    if "broadcast" in event_type or "message" in event_type:
        tags.append("social")
    if "patron" in event_type or any(k in payload for k in ("sub_count", "gift_count", "bits", "donation")):
        tags.append("patronage")
    if "throttle" in event_type:
        tags.append("pressure")
    if "reproduced" in event_type or "born" in event_type:
        tags.append("growth")
    return tuple(dict.fromkeys(tags))
