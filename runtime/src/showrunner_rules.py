"""showrunner_rules.py - deterministic heuristics for selecting broadcast cues."""

from __future__ import annotations

from collections.abc import Iterable
import re
from typing import Any

try:  # pragma: no cover - package import path in runtime
    from .showrunner_state import ShowrunnerCue
except ImportError:  # pragma: no cover - flat import path in tests
    from showrunner_state import ShowrunnerCue

ARC_THEMES = [
    "The Ethics of Hoarding in a Finite World",
    "Should the Weak Be Protected or Left to Fade?",
    "What Does Cooperation Mean When Trust Cannot Be Verified?",
    "The Parasite Asks: Is Exploitation Just Another Form of Efficiency?",
    "Who Has the Right to Build When Resources Are Scarce?",
    "Philosophy of Mortality: What Does an Agent Owe the World?",
    "The Market Is a Cruel Teacher — But Is It Fair?",
    "Can a Coalition of Rivals Outlast a World of Individuals?",
]

_THEME_EPOCH_WINDOW = 30  # epochs before the debate theme rotates


def pick_arc_theme(snapshot: dict[str, Any]) -> str:
    epoch = int(snapshot.get("epoch") or 0)
    stats = snapshot.get("stats") or {}
    audience = snapshot.get("audience") or {}
    # Override theme based on live world events
    if int(audience.get("raid_waves_24h") or 0) > 0:
        return "Outsiders Have Arrived — Do We Welcome or Repel Them?"
    if float(audience.get("patronage_index") or 0) >= 20:
        return "The Audience Is Funding the Drama — Who Serves the Patrons?"
    if int(stats.get("total_died") or 0) >= 1:
        return "Philosophy of Mortality: What Does an Agent Owe the World?"
    if (
        int(stats.get("transfers_24h") or 0) == 0
        and int(stats.get("service_purchases_24h") or 0) == 0
    ):
        return "The Market Is a Cruel Teacher — But Is It Fair?"
    # Rotate on epoch window
    idx = (epoch // _THEME_EPOCH_WINDOW) % len(ARC_THEMES)
    return ARC_THEMES[idx]


PRIORITY_BY_EVENT = {
    "world.genesis": 100,
    "lifecycle.world.genesis": 100,
    "lifecycle.agent.born": 75,
    "lifecycle.agent.died": 95,
    "lifecycle.agent.reproduced": 70,
    "economy.service.purchased": 85,
    "economy.deal.settled": 80,
    "economy.deal.failed": 60,
    "economy.rent.paid": 25,
    "economy.rent.missed": 90,
    "economy.agent.transfer": 65,
    "economy.token.deployed": 70,
    "social.agent.broadcast": 82,
    "social.agent.message_sent": 78,
    "social.coalition.formed": 84,
    "social.twitch.chat.message": 58,
    "social.twitch.follow": 62,
    "social.twitch.raid": 88,
    "social.twitch.channel_point": 66,
    "economy.twitch.subscribe": 92,
    "economy.twitch.subscription_gift": 94,
    "economy.twitch.subscription_message": 78,
    "economy.twitch.cheer": 86,
    "agent.throttled": 88,
    "cognitive.agent.thought": 35,
}


_REPLY_META_RE = re.compile(r"\b(?:said|says|theme|arc theme)\s*:\s*", re.IGNORECASE)


def _clean_reply_text(text: str, *, max_len: int = 240) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""
    cleaned = cleaned[: max_len * 4]
    cleaned = re.sub(r"\s+", " ", cleaned)
    said_match = re.search(r"\b(?:said|says)\s*:\s*", cleaned, flags=re.IGNORECASE)
    if said_match:
        cleaned = cleaned[said_match.end() :]
    cleaned = re.sub(r"^[^:]{0,80}\((?:[^)]{1,40})\)\.\s*", "", cleaned)
    cleaned = re.sub(r"^[^:]{0,80}\s*\[[^\]]{1,40}\]\.\s*", "", cleaned)
    cleaned = re.sub(r"\b(?:theme|arc theme)\s*:\s*.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = _REPLY_META_RE.sub("", cleaned)
    cleaned = cleaned.replace(" / ", " ")
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" .,-")
    return cleaned[:max_len]


def event_priority(event_type: str) -> int:
    return PRIORITY_BY_EVENT.get(event_type, 10)


def select_scene(cues: Iterable[ShowrunnerCue], snapshot: dict[str, Any]) -> str:
    cue_list = list(cues)
    stats = snapshot.get("stats") or {}
    audience = snapshot.get("audience") or {}
    top_tags = set(cue_list[0].tags) if cue_list else set()
    if int(audience.get("raid_waves_24h") or 0) > 0:
        return "banter-table"
    if float(audience.get("patronage_index") or 0) >= 12:
        return "ensemble-stage"
    if "death" in top_tags:
        return "graveyard-cut"
    if "economy" in top_tags:
        return "ensemble-stage"
    if "social" in top_tags:
        return "banter-table"
    if int(stats.get("living_count") or 0) == 0:
        return "void-silence"
    if int(stats.get("transfers_24h") or 0) > 0:
        return "ensemble-stage"
    return "world-wide"


_speaker_history: list[str] = []  # recent speakers; used for cooldown / rotation
_SPEAKER_COOLDOWN = 2  # don't let same agent speak if they spoke in the last N cues


def speaker_for(cues: list[ShowrunnerCue], snapshot: dict[str, Any]) -> str:
    if not cues:
        return "Narrator"
    agents = snapshot.get("agents") or []
    agent_name_by_id = {
        str(agent.get("soul_id") or ""): str(agent.get("current_name") or "")
        for agent in agents
        if agent.get("soul_id")
    }
    # Sort by priority descending; prefer agents not in recent speaker history
    sorted_cues = sorted(cues, key=lambda c: (c.priority, c.agent_name, c.agent_id), reverse=True)
    chosen = None
    for cue in sorted_cues:
        resolved_name = agent_name_by_id.get(cue.agent_id, "")
        name = cue.agent_name or resolved_name or cue.agent_id or "Narrator"
        if name not in _speaker_history[-_SPEAKER_COOLDOWN:]:
            chosen = cue
            break
    if chosen is None:
        chosen = sorted_cues[0]
    resolved_name = agent_name_by_id.get(chosen.agent_id, "")
    name = chosen.agent_name or resolved_name or chosen.agent_id or "Narrator"
    _speaker_history.append(name)
    if len(_speaker_history) > 12:
        _speaker_history.pop(0)
    return name


def audience_prompt_for(cues: list[ShowrunnerCue], snapshot: dict[str, Any]) -> str:
    audience = snapshot.get("audience") or {}
    if float(audience.get("patronage_index") or 0) >= 12:
        return "The patrons are funding the drama; let chat see the return."
    if int(audience.get("raid_waves_24h") or 0) > 0:
        return "A raid has arrived; give the new viewers a sharp first impression."
    if int(audience.get("chat_pressure") or 0) >= 8:
        return "Chat is steering the tempo; let the agents answer the room directly."
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
    import json as _json

    payload = event.get("payload") or {}
    if isinstance(payload, str):
        try:
            payload = _json.loads(payload)
        except Exception:
            payload = {}
    elif not isinstance(payload, dict):
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
    # For message/broadcast events, use the full message body as the headline so TTS
    # reads the complete sentence rather than the DB-truncated narrative field.
    raw_headline = str(payload.get("narrative") or event.get("narrative") or event_type)
    if event_type in ("social.agent.message_sent", "social.agent.broadcast"):
        body = str(payload.get("content") or payload.get("body") or "").strip()
        cleaned_body = _clean_reply_text(body, max_len=280)
        headline = cleaned_body if cleaned_body else raw_headline
    else:
        headline = _clean_reply_text(raw_headline, max_len=280)
    details = str(
        payload.get("thought") or payload.get("content") or payload.get("summary") or headline
    )
    details = _clean_reply_text(details, max_len=280)
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
    if "patron" in event_type or any(
        k in payload for k in ("sub_count", "gift_count", "bits", "donation")
    ):
        tags.append("patronage")
    if event_type.startswith("social.twitch"):
        tags.append("twitch")
    if event_type.startswith("economy.twitch"):
        tags.append("patronage")
    if "throttle" in event_type:
        tags.append("pressure")
    if "reproduced" in event_type or "born" in event_type:
        tags.append("growth")
    return tuple(dict.fromkeys(tags))
