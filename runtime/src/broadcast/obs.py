"""OBS surface adapter with dry-run support."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Any

try:  # pragma: no cover - runtime package import path
    from ..health_checks import probe_url
except ImportError:  # pragma: no cover - flat test path
    from health_checks import probe_url

try:  # pragma: no cover - runtime package import path
    from .captions import build_caption
    from .overlays import build_overlay
    from .scenes import select_scene
    from .state import BroadcastCaption, BroadcastOverlay, BroadcastScene, BroadcastState
except ImportError:  # pragma: no cover - flat test path
    from captions import build_caption
    from overlays import build_overlay
    from scenes import select_scene
    from state import BroadcastCaption, BroadcastOverlay, BroadcastScene, BroadcastState


def _env_bool(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class BroadcastCommand:
    action: str
    target: str
    value: str
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BroadcastSurface:
    """Compose stage state for the live broadcast surface."""

    def __init__(self, enabled: bool | None = None, dry_run: bool | None = None):
        self.enabled = _env_bool("BROADCAST_ENABLED", "true") if enabled is None else enabled
        self.dry_run = _env_bool("BROADCAST_DRY_RUN", "true") if dry_run is None else dry_run
        self.transport = os.getenv("BROADCAST_TRANSPORT", "dry-run")
        self.obs_scene_prefix = os.getenv("OBS_SCENE_PREFIX", "obs/")

    def compose(self, snapshot: dict[str, Any]) -> BroadcastState:
        scene_profile = select_scene(snapshot)
        caption = build_caption(snapshot, scene_profile)
        overlay = build_overlay(snapshot, scene_profile)
        commands = self._commands(scene_profile, caption, overlay)
        return BroadcastState(
            enabled=self.enabled,
            dry_run=self.dry_run,
            scene=BroadcastScene(
                scene_id=scene_profile["scene_id"],
                scene_name=scene_profile["scene_name"],
                layout=scene_profile["layout"],
                fallback_scene=scene_profile["fallback_scene"],
                reason=scene_profile["reason"],
                mode=self.transport,
            ),
            caption=BroadcastCaption(
                headline=caption["headline"],
                subhead=caption["subhead"],
                lower_third=caption["lower_third"],
                ticker_lines=tuple(caption["ticker_lines"]),
            ),
            overlay=BroadcastOverlay(
                title=overlay["title"],
                subtitle=overlay["subtitle"],
                cards=tuple(overlay["cards"]),
                labels=tuple(overlay["labels"]),
            ),
            commands=tuple(commands),
            summary=self._summary(scene_profile, caption),
            world_id=str(snapshot.get("world_id") or ""),
            source_epoch=int(snapshot.get("epoch") or 0),
        )

    def status(self) -> dict[str, Any]:
        health = probe_url(os.getenv("OBS_WEBSOCKET_URL"), timeout=1.5)
        return {
            "enabled": self.enabled,
            "dry_run": self.dry_run,
            "transport": self.transport,
            "obs_scene_prefix": self.obs_scene_prefix,
            "health": health,
        }

    def _summary(self, scene_profile: dict[str, Any], caption: dict[str, Any]) -> str:
        return f"{scene_profile['scene_name']} / {caption['headline'][:120]}"

    def _commands(
        self,
        scene_profile: dict[str, Any],
        caption: dict[str, Any],
        overlay: dict[str, Any],
    ) -> list[dict[str, Any]]:
        commands = [
            BroadcastCommand(
                action="set_scene",
                target="obs",
                value=scene_profile["scene_id"],
                reason=scene_profile["reason"],
                metadata={"fallback": scene_profile["fallback_scene"]},
            ).to_dict(),
            BroadcastCommand(
                action="set_caption",
                target="overlay",
                value=caption["headline"],
                reason="headline",
                metadata={"subhead": caption["subhead"], "lower_third": caption["lower_third"]},
            ).to_dict(),
            BroadcastCommand(
                action="set_overlay",
                target="overlay",
                value=overlay["title"],
                reason="stage overlay",
                metadata={"labels": overlay["labels"], "cards": overlay["cards"]},
            ).to_dict(),
        ]
        if self.dry_run or not self.enabled:
            for command in commands:
                command["dry_run"] = True
                command["transport"] = self.transport
        return commands


def build_broadcast_status() -> dict[str, Any]:
    return BroadcastSurface().status()
