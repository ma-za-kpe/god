"""Viewer extension and overlay planning from the world snapshot."""

from __future__ import annotations

import hashlib
import os
from typing import Any

try:  # pragma: no cover - runtime package import path
    from .state import ViewerState
except ImportError:  # pragma: no cover - flat test path
    from state import ViewerState


def _env_bool(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")


def _take_options(snapshot: dict[str, Any], count: int = 3) -> list[dict[str, Any]]:
    content_bank = snapshot.get("content_bank") or {}
    audience = snapshot.get("audience") or {}
    arcs = list(content_bank.get("arcs") or [])
    options: list[dict[str, Any]] = []
    for arc in arcs[:count]:
        options.append(
            {
                "label": arc.get("title") or "Arc",
                "value": arc.get("trigger") or arc.get("title") or "arc",
                "reason": arc.get("payoff") or arc.get("tension") or "future arc",
            }
        )
    if not options:
        options = [
            {
                "label": "Patron spotlight",
                "value": "patron",
                "reason": "Let patrons steer the next turn.",
            },
            {"label": "Chat pressure", "value": "chat", "reason": "Let chat dictate the tempo."},
            {
                "label": "Raid welcome",
                "value": "raid",
                "reason": "Turn new viewers into the next hook.",
            },
        ]
    if float(audience.get("patronage_index") or 0) >= 12:
        options.insert(
            0,
            {"label": "Patron-funded arc", "value": "patron-funded", "reason": "Reward the room."},
        )
    return options[:count]


def _focus(snapshot: dict[str, Any]) -> str:
    content_bank = snapshot.get("content_bank") or {}
    if content_bank.get("focus"):
        return str(content_bank["focus"])
    audience = snapshot.get("audience") or {}
    if float(audience.get("patronage_index") or 0) >= 12:
        return "patron-funded escalation"
    if int(audience.get("raid_waves_24h") or 0) > 0:
        return "raid aftermath"
    return "slow burn"


class ViewerSurface:
    """Compose a viewer extension / overlay prompt from the world snapshot."""

    def __init__(self, enabled: bool | None = None, dry_run: bool | None = None):
        self.enabled = _env_bool("VIEWER_ENABLED", "true") if enabled is None else enabled
        self.dry_run = _env_bool("VIEWER_DRY_RUN", "true") if dry_run is None else dry_run
        self.mode = os.getenv("VIEWER_MODE", "overlay")
        self.transport = os.getenv("VIEWER_TRANSPORT", "dry-run")

    def compose(self, snapshot: dict[str, Any]) -> ViewerState:
        stats = snapshot.get("stats") or {}
        audience = snapshot.get("audience") or {}
        content_bank = snapshot.get("content_bank") or {}
        showrunner = snapshot.get("showrunner") or {}
        world_id = str(snapshot.get("world_id") or "")
        source_epoch = int(snapshot.get("epoch") or 0)
        focus = _focus(snapshot)
        options = _take_options(snapshot, count=3)
        option_labels = [str(option["label"]) for option in options]

        prompt = (
            content_bank.get("summary")
            or audience.get("story_hook")
            or showrunner.get("audience_prompt")
            or "Watch the cast."
        )
        interaction_mode = "watch"
        poll = {
            "question": "Which actor should move the scene next?",
            "options": options[:2],
            "expires_in_s": 180,
        }
        prediction = {
            "question": "Will the next beat be a confession, clash, or turn?",
            "market": ["confession", "clash", "turn"],
            "focus": focus,
        }
        summary = "Avatar-first stage ready."
        cards = [
            {"label": "Mode", "value": interaction_mode, "tone": "cognitive"},
            {
                "label": "Speaker",
                "value": str(showrunner.get("speaker") or "Narrator"),
                "tone": "social",
            },
            {"label": "Cast", "value": int(stats.get("living_count") or 0), "tone": "life"},
            {"label": "Pressure", "value": int(audience.get("chat_pressure") or 0), "tone": "gold"},
        ]
        extension_cards = [
            {"title": "Speaker", "body": str(showrunner.get("speaker") or "Narrator")},
            {"title": "Focus", "body": focus},
            {"title": "Mood", "body": str(showrunner.get("headline") or "Watch the cast.")[:80]},
        ]
        labels = ("avatars", "drama", focus, "interactive")
        bank_seed = hashlib.sha256(
            f"{world_id}:{source_epoch}:{focus}".encode("utf-8")
        ).hexdigest()[:16]
        commands = (
            {
                "action": "publish_viewer_overlay",
                "target": "browser-source",
                "value": bank_seed,
                "reason": "viewer-interaction",
                "metadata": {
                    "question": poll["question"],
                    "options": option_labels,
                },
            },
        )
        return ViewerState(
            enabled=self.enabled,
            dry_run=self.dry_run,
            mode=self.mode,
            world_id=world_id,
            source_epoch=source_epoch,
            interaction_mode=interaction_mode,
            prompt=prompt,
            summary=summary,
            focus=focus,
            labels=labels,
            cards=tuple(cards),
            poll=poll,
            prediction=prediction,
            extension_cards=tuple(extension_cards),
            options=tuple(options),
            commands=commands,
        )

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "dry_run": self.dry_run,
            "mode": self.mode,
            "transport": self.transport,
            "supported_interactions": ["poll", "prediction", "overlay"],
        }


def build_viewer_state(snapshot: dict[str, Any]) -> dict[str, Any]:
    return ViewerSurface().compose(snapshot).to_dict()


def build_viewer_status() -> dict[str, Any]:
    return ViewerSurface().status()
