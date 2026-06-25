"""Local content bank that pre-generates future story material."""

from __future__ import annotations

import hashlib
import os
from typing import Any

try:  # pragma: no cover - runtime package import path
    from .state import ContentBankState
except ImportError:  # pragma: no cover - flat test path
    from state import ContentBankState


def _env_bool(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")


def _top_agents(snapshot: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    agents = snapshot.get("agents") or []
    ranked = sorted(
        [a for a in agents if a.get("is_alive", True)],
        key=lambda a: (
            float(a.get("balance_usdc") or 0),
            int(a.get("generation") or 0),
            str(a.get("current_name") or ""),
        ),
        reverse=True,
    )
    return ranked[:limit]


def _make_arc(
    title: str,
    premise: str,
    trigger: str,
    cast: list[str],
    tension: str,
    payoff: str,
    sponsor_slot: str,
) -> dict[str, Any]:
    return {
        "title": title,
        "premise": premise,
        "trigger": trigger,
        "cast": cast,
        "tension": tension,
        "payoff": payoff,
        "sponsor_slot": sponsor_slot,
    }


def _seed(snapshot: dict[str, Any]) -> str:
    payload = {
        "epoch": snapshot.get("epoch"),
        "world_id": snapshot.get("world_id"),
        "stats": snapshot.get("stats") or {},
        "showrunner": snapshot.get("showrunner") or {},
        "audience": snapshot.get("audience") or {},
    }
    return hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()[:16]


def _theme(snapshot: dict[str, Any]) -> str:
    audience = snapshot.get("audience") or {}
    stats = snapshot.get("stats") or {}
    if float(audience.get("patronage_index") or 0) >= 12:
        return "patron-funded escalation"
    if int(audience.get("raid_waves_24h") or 0) > 0:
        return "raid aftermath"
    if int(stats.get("service_purchases_24h") or 0) > 0:
        return "market pressure"
    if int(stats.get("living_count") or 0) <= 1:
        return "survival silence"
    return "slow burn"


def _build_arcs(snapshot: dict[str, Any], horizon_days: int) -> list[dict[str, Any]]:
    top = _top_agents(snapshot, limit=3)
    top_names = [a.get("current_name") or a.get("soul_id", "")[:8] for a in top]
    theme = _theme(snapshot)

    arcs = [
        _make_arc(
            title="Patrons Raise the Stakes",
            premise="Subscriber support becomes visible leverage over the cast.",
            trigger="subscribe_or_gift",
            cast=top_names[:2] or ["Narrator"],
            tension="The room expects the patrons to buy consequences, not just applause.",
            payoff="A patron-backed turn changes the next scene choice.",
            sponsor_slot="subscriber spotlight",
        ),
        _make_arc(
            title="Chat Picks a Side",
            premise="A loud chat wave forces the cast into a public argument.",
            trigger="chat_pressure",
            cast=top_names[:3] or ["Narrator"],
            tension="Agents can no longer hide behind silence.",
            payoff="The argument resolves into a clear winner and loser.",
            sponsor_slot="chat headline",
        ),
        _make_arc(
            title="Raid Aftermath",
            premise="Incoming viewers turn a small moment into a live reveal.",
            trigger="raid",
            cast=top_names[:2] or ["Narrator"],
            tension="The showrunner must convert surprise into clarity fast enough to retain the raid.",
            payoff="A new scene or hook is opened for the incoming audience.",
            sponsor_slot="raid welcome",
        ),
        _make_arc(
            title="The Market Remembers",
            premise="Agent services and economy events become recurring episodic material.",
            trigger="service_activity",
            cast=top_names[:3] or ["Narrator"],
            tension="Everyone wants the next profitable turn, but not everyone gets paid.",
            payoff="A service or deal becomes a repeatable story beat.",
            sponsor_slot="market sponsor",
        ),
    ]

    if theme == "survival silence":
        arcs.insert(
            0,
            _make_arc(
                title="Survival Before Spectacle",
                premise="The world is quiet enough to hear who still matters.",
                trigger="low_population",
                cast=top_names[:1] or ["Narrator"],
                tension="One mistake can collapse the remaining structure.",
                payoff="A simple survival rhythm becomes the first reliable show loop.",
                sponsor_slot="foundational arc",
            ),
        )

    return arcs[: max(2, min(5, horizon_days // 7 + 2))]


def _build_dialogue(arcs: list[dict[str, Any]], top_names: list[str]) -> list[dict[str, Any]]:
    dialogue = []
    for arc in arcs:
        speaker = top_names[0] if top_names else "Narrator"
        dialogue.append(
            {
                "arc_title": arc["title"],
                "speaker": speaker,
                "line": f"{speaker} can steer {arc['title'].lower()} if chat keeps funding the momentum.",
                "emotion": "charged",
            }
        )
    return dialogue


def _build_scene_prompts(arcs: list[dict[str, Any]], focus: str) -> list[dict[str, Any]]:
    prompts = []
    for arc in arcs:
        prompts.append(
            {
                "scene": "world-wide" if "silence" in arc["title"].lower() else "market-watch",
                "prompt": f"Render {arc['title']} as a live {focus} beat.",
                "fallback": "world-wide",
            }
        )
    return prompts


def _build_clip_prompts(arcs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "title": f"Clip: {arc['title']}",
            "hook": arc["premise"],
            "reason": arc["tension"],
        }
        for arc in arcs[:4]
    ]


class ContentBankSurface:
    """Compose a local pre-generation bank from the world snapshot."""

    def __init__(self, enabled: bool | None = None, dry_run: bool | None = None):
        self.enabled = _env_bool("CONTENT_BANK_ENABLED", "true") if enabled is None else enabled
        self.dry_run = _env_bool("CONTENT_BANK_DRY_RUN", "true") if dry_run is None else dry_run
        self.mode = os.getenv("CONTENT_BANK_MODE", "deterministic")
        self.horizon_days = int(os.getenv("CONTENT_BANK_HORIZON_DAYS", "30"))
        self.transport = os.getenv("CONTENT_BANK_TRANSPORT", "local-pre-gen")

    def compose(self, snapshot: dict[str, Any]) -> ContentBankState:
        audience = snapshot.get("audience") or {}
        world_id = str(snapshot.get("world_id") or "")
        source_epoch = int(snapshot.get("epoch") or 0)
        focus = _theme(snapshot)
        seed = _seed(snapshot)
        top_agents = _top_agents(snapshot, limit=3)
        top_names = [a.get("current_name") or a.get("soul_id", "")[:8] for a in top_agents]

        arcs = _build_arcs(snapshot, self.horizon_days)
        dialogue = _build_dialogue(arcs, top_names)
        scene_prompts = _build_scene_prompts(arcs, focus)
        clip_prompts = _build_clip_prompts(arcs)

        asset_list = []
        for arc in arcs:
            asset_list.append({"kind": "arc", **arc})
        for item in dialogue:
            asset_list.append({"kind": "dialogue", **item})
        for item in scene_prompts:
            asset_list.append({"kind": "scene_prompt", **item})
        for item in clip_prompts:
            asset_list.append({"kind": "clip_prompt", **item})

        bank_id = hashlib.sha256(f"{world_id}:{source_epoch}:{seed}".encode("utf-8")).hexdigest()[
            :16
        ]
        summary = (
            f"{len(arcs)} future arc(s), {len(dialogue)} dialogue beats, "
            f"{len(scene_prompts)} scene prompts, focus={focus}."
        )
        cards = [
            {"label": "Horizon", "value": f"{self.horizon_days}d", "tone": "cognitive"},
            {"label": "Arcs", "value": len(arcs), "tone": "life"},
            {"label": "Dialogue", "value": len(dialogue), "tone": "social"},
            {"label": "Clips", "value": len(clip_prompts), "tone": "gold"},
            {"label": "Focus", "value": focus, "tone": "manifesto"},
            {
                "label": "Patronage",
                "value": float(audience.get("patronage_index") or 0),
                "tone": "gold",
            },
        ]
        labels = ("content-bank", "pre-gen", focus, "local-gpu-ready")
        commands = (
            {
                "action": "cache_story_bank",
                "target": "runtime",
                "value": bank_id,
                "reason": "pre-generation",
                "metadata": {
                    "horizon_days": self.horizon_days,
                    "arc_count": len(arcs),
                    "dialogue_count": len(dialogue),
                },
            },
        )
        return ContentBankState(
            enabled=self.enabled,
            dry_run=self.dry_run,
            mode=self.mode,
            world_id=world_id,
            source_epoch=source_epoch,
            horizon_days=self.horizon_days,
            bank_id=bank_id,
            arc_count=len(arcs),
            dialogue_count=len(dialogue),
            scene_count=len(scene_prompts),
            clip_count=len(clip_prompts),
            focus=focus,
            summary=summary,
            labels=labels,
            cards=tuple(cards),
            arcs=tuple(arcs),
            dialogue=tuple(dialogue),
            scene_prompts=tuple(scene_prompts),
            clip_prompts=tuple(clip_prompts),
            assets=tuple(asset_list),
            commands=commands,
        )

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "dry_run": self.dry_run,
            "mode": self.mode,
            "transport": self.transport,
            "horizon_days": self.horizon_days,
            "supported_asset_types": [
                "arc",
                "dialogue",
                "scene_prompt",
                "clip_prompt",
            ],
        }


def build_content_bank_state(snapshot: dict[str, Any]) -> dict[str, Any]:
    return ContentBankSurface().compose(snapshot).to_dict()


def build_content_bank_status() -> dict[str, Any]:
    return ContentBankSurface().status()
