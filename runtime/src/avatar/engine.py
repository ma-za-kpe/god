"""Avatar planning surface for renderer and lip-sync wiring."""

from __future__ import annotations

import os
from typing import Any

try:  # pragma: no cover - runtime package import path
    from ..health_checks import probe_url
except ImportError:  # pragma: no cover - flat test path
    from health_checks import probe_url

from .state import AvatarPlan, AvatarState


def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")


def _pick_expression(snapshot: dict[str, Any]) -> str:
    showrunner = snapshot.get("showrunner") or {}
    audience = snapshot.get("audience") or {}
    scene = str(showrunner.get("scene") or "").lower()
    pressure = float(audience.get("patronage_index") or 0)
    if pressure >= 20:
        return "intense"
    if "banter" in scene or "chat" in scene:
        return "animated"
    if "economy" in scene or "market" in scene:
        return "focused"
    if "void" in scene or "silence" in scene:
        return "calm"
    return "attentive"


def _pick_pose(snapshot: dict[str, Any]) -> str:
    showrunner = snapshot.get("showrunner") or {}
    scene = str(showrunner.get("scene") or "").lower()
    if "banter" in scene:
        return "debate"
    if "economy" in scene or "market" in scene:
        return "presenting"
    if "void" in scene:
        return "still"
    return "lead"


def build_avatar_status() -> dict[str, Any]:
    endpoint = os.getenv("AVATAR_HEALTH_URL") or os.getenv("AVATAR_ENDPOINT")
    return {
        "enabled": _env_bool("AVATAR_ENABLED") or bool(os.getenv("AVATAR_ASSET")) or bool(endpoint),
        "dry_run": _env_bool("AVATAR_DRY_RUN", "true"),
        "renderer": os.getenv("AVATAR_RENDERER", "vrm"),
        "avatar_format": os.getenv("AVATAR_FORMAT", "vrm"),
        "avatar_asset": os.getenv("AVATAR_ASSET", ""),
        "lip_sync_source": os.getenv("AVATAR_LIP_SYNC_SOURCE", os.getenv("LIP_SYNC_SOURCE", "audio")),
        "render_target": os.getenv("AVATAR_RENDER_TARGET", "obs-virtual-camera"),
        "transport": os.getenv("AVATAR_TRANSPORT", "local-avatar"),
        "health": probe_url(endpoint, timeout=1.5),
    }


class AvatarSurface:
    """Compose an avatar render plan from the live world snapshot."""

    def __init__(self, enabled: bool | None = None, dry_run: bool | None = None):
        self.enabled = _env_bool("AVATAR_ENABLED") if enabled is None else enabled
        self.dry_run = _env_bool("AVATAR_DRY_RUN", "true") if dry_run is None else dry_run
        self.renderer = os.getenv("AVATAR_RENDERER", "vrm")
        self.avatar_format = os.getenv("AVATAR_FORMAT", "vrm")
        self.transport = os.getenv("AVATAR_TRANSPORT", "local-avatar")

    def compose(self, snapshot: dict[str, Any]) -> AvatarState:
        showrunner = snapshot.get("showrunner") or {}
        broadcast = snapshot.get("broadcast") or {}
        agents = snapshot.get("agents") or []
        active_name = str(showrunner.get("speaker") or broadcast.get("scene", {}).get("speaker") or "Narrator")
        active_agent = next(
            (
                a
                for a in agents
                if str(a.get("current_name") or "").lower() == active_name.lower()
            ),
            agents[0] if agents else {},
        )
        agent_id = str(active_agent.get("soul_id") or "")
        expression = _pick_expression(snapshot)
        pose = _pick_pose(snapshot)
        health = probe_url(os.getenv("AVATAR_HEALTH_URL") or os.getenv("AVATAR_ENDPOINT"), timeout=1.5)
        avatar_asset = (
            os.getenv("AVATAR_ASSET")
            or active_agent.get("avatar_cid")
            or active_agent.get("voice_model_cid")
            or ""
        )
        plan = AvatarPlan(
            speaker=active_name,
            agent_id=agent_id,
            renderer=self.renderer,
            avatar_format=self.avatar_format,
            expression=expression,
            pose=pose,
            motion="idle" if snapshot.get("resilience", {}).get("tier") == "cold-start" else "live-reactive",
            lip_sync_source=os.getenv("AVATAR_LIP_SYNC_SOURCE", os.getenv("LIP_SYNC_SOURCE", "audio")),
            render_target=os.getenv("AVATAR_RENDER_TARGET", "obs-virtual-camera"),
            notes=tuple(
                filter(
                    None,
                    [
                        f"speaker={active_name}",
                        f"agent={agent_id[:8] if agent_id else 'none'}",
                        f"expression={expression}",
                        f"pose={pose}",
                    ],
                )
            ),
        )
        return AvatarState(
            enabled=self.enabled,
            dry_run=self.dry_run,
            renderer=self.renderer,
            avatar_format=self.avatar_format,
            avatar_asset=avatar_asset,
            expression=expression,
            motion=plan.motion,
            lip_sync_source=plan.lip_sync_source,
            render_target=plan.render_target,
            health=health,
            plan=plan,
        )

    def status(self) -> dict[str, Any]:
        return build_avatar_status()


def build_avatar_state(snapshot: dict[str, Any]) -> dict[str, Any]:
    return AvatarSurface().compose(snapshot).to_dict()


def build_avatar_status_surface() -> dict[str, Any]:
    return build_avatar_status()
