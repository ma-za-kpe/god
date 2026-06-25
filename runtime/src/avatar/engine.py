"""Avatar planning surface for renderer, lip-sync, and scene wiring."""

from __future__ import annotations

import os
import time
from typing import Any

try:  # pragma: no cover - runtime package import path
    from ..health_checks import probe_url
except ImportError:  # pragma: no cover - flat test path
    from health_checks import probe_url

try:  # pragma: no cover - runtime package import path
    from ..banter.types import Beat, PairState, SceneContextData
except ImportError:  # pragma: no cover - flat test path
    from banter.types import Beat, PairState, SceneContextData

try:  # pragma: no cover - runtime package import path
    from .scene_composer import SceneComposer
    from .state import AvatarPlan, AvatarState
    from .visual_reactor import VisualReactor
except ImportError:  # pragma: no cover - flat test path
    from avatar.scene_composer import SceneComposer
    from avatar.state import AvatarPlan, AvatarState
    from avatar.visual_reactor import VisualReactor


def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")


def _pick_expression(snapshot: dict[str, Any]) -> str:
    showrunner = snapshot.get("showrunner") or {}
    audience = snapshot.get("audience") or {}
    scene = str(showrunner.get("scene") or "").lower()
    pressure = float(audience.get("patronage_index") or 0)
    if pressure >= 20:
        return "intense"
    if (
        "banter" in scene
        or "chat" in scene
        or "ensemble" in scene
        or "stage" in scene
        or "avatar" in scene
    ):
        return "animated"
    if "economy" in scene or "market" in scene:
        return "focused"
    if "void" in scene or "silence" in scene:
        return "calm"
    return "attentive"


def _pick_pose(snapshot: dict[str, Any]) -> str:
    showrunner = snapshot.get("showrunner") or {}
    scene = str(showrunner.get("scene") or "").lower()
    if "banter" in scene or "ensemble" in scene or "stage" in scene or "avatar" in scene:
        return "debate"
    if "economy" in scene or "market" in scene:
        return "presenting"
    if "void" in scene:
        return "still"
    return "lead"


def _default_visual_state() -> dict[str, Any]:
    return {
        "current_expression": "neutral",
        "expression_override": "",
        "override_expiry_epoch": 0,
        "scar_layers": [],
        "presentation_mode": "standard",
        "mouth_open": 0.0,
    }


def _agent_identity(agent: Any) -> Any:
    if isinstance(agent, dict):
        return agent
    return getattr(agent, "identity", agent)


def _visual_state(agent: Any) -> dict[str, Any]:
    identity = _agent_identity(agent)
    if isinstance(identity, dict):
        return identity.setdefault("visual_state", _default_visual_state())
    visual_state = getattr(identity, "visual_state", None)
    if not isinstance(visual_state, dict):
        visual_state = _default_visual_state()
        setattr(identity, "visual_state", visual_state)
    else:
        visual_state.setdefault("current_expression", "neutral")
        visual_state.setdefault("expression_override", "")
        visual_state.setdefault("override_expiry_epoch", 0)
        visual_state.setdefault("scar_layers", [])
        visual_state.setdefault("presentation_mode", "standard")
        visual_state.setdefault("mouth_open", 0.0)
    return visual_state


def _agent_key(agent: Any) -> str:
    if isinstance(agent, dict):
        return str(
            agent.get("soul_id")
            or agent.get("identity", {}).get("soul_id")
            or agent.get("current_name")
            or ""
        )
    identity = getattr(agent, "identity", None)
    if identity is not None:
        return str(getattr(identity, "soul_id", "") or getattr(identity, "current_name", "") or "")
    return str(getattr(agent, "soul_id", "") or getattr(agent, "current_name", "") or "")


def _beat_speaker(beat: Any) -> str:
    if isinstance(beat, dict):
        return str(beat.get("speaker") or beat.get("sender_name") or "")
    return str(getattr(beat, "speaker", "") or "")


def _beat_quality(beat: Any) -> int:
    if isinstance(beat, dict):
        return int(beat.get("quality_score") or 0)
    return int(getattr(beat, "quality_score", 0) or 0)


def _voice_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    voice = snapshot.get("voice") or {}
    return voice if isinstance(voice, dict) else {}


class AvatarSurface:
    """Compose an avatar render plan from the live world snapshot."""

    def __init__(self, enabled: bool | None = None, dry_run: bool | None = None):
        self.enabled = _env_bool("AVATAR_ENABLED") if enabled is None else enabled
        self.dry_run = _env_bool("AVATAR_DRY_RUN", "true") if dry_run is None else dry_run
        self.renderer = os.getenv("AVATAR_RENDERER", "vrm")
        self.avatar_format = os.getenv("AVATAR_FORMAT", "vrm")
        self.transport = os.getenv("AVATAR_TRANSPORT", "local-avatar")
        self._visual_reactor = VisualReactor()
        self._scene_composer = SceneComposer()
        self._last_scene_layout: dict[str, Any] | None = None

    def compose(self, snapshot: dict[str, Any]) -> AvatarState:
        showrunner = snapshot.get("showrunner") or {}
        broadcast = snapshot.get("broadcast") or {}
        agents = snapshot.get("agents") or []
        current_epoch = int(snapshot.get("epoch") or time.time())
        active_name = str(
            showrunner.get("speaker") or broadcast.get("scene", {}).get("speaker") or "Narrator"
        )
        if agents and isinstance(agents[0], dict):
            active_agent = next(
                (
                    a
                    for a in agents
                    if str(
                        a.get("current_name") or a.get("identity", {}).get("current_name") or ""
                    ).lower()
                    == active_name.lower()
                ),
                None,
            )
        else:
            active_agent = next(
                (a for a in agents if _agent_key(a).lower() == active_name.lower()),
                None,
            )
        if active_agent is None:
            active_agent = agents[0] if agents else {}
        agent_id = _agent_key(active_agent)
        visual_state = _visual_state(active_agent) if active_agent else _default_visual_state()
        voice_state = _voice_snapshot(snapshot)
        voice_plan = voice_state.get("plan") or {}
        last_turn = snapshot.get("last_dialogue_turn") or {}
        last_turn_speaker = str(last_turn.get("sender_name") or last_turn.get("sender_id") or "")
        speaking = bool(last_turn.get("content")) and (
            last_turn_speaker.lower() == active_name.lower()
            or str(voice_plan.get("speaker") or "").lower() == active_name.lower()
        )

        override = str(visual_state.get("expression_override") or "")
        override_expiry = int(visual_state.get("override_expiry_epoch") or 0)
        if override and override_expiry > current_epoch:
            expression = override
        else:
            if override and override_expiry <= current_epoch:
                visual_state["expression_override"] = ""
                visual_state["override_expiry_epoch"] = 0
            expression = _pick_expression(snapshot)
        visual_state["current_expression"] = expression

        pose = _pick_pose(snapshot)
        health = probe_url(
            os.getenv("AVATAR_HEALTH_URL") or os.getenv("AVATAR_ENDPOINT"), timeout=1.5
        )
        avatar_asset = (
            os.getenv("AVATAR_ASSET")
            or (
                active_agent.get("avatar_cid")
                if isinstance(active_agent, dict)
                else getattr(active_agent, "avatar_cid", "")
            )
            or (
                active_agent.get("rigged_avatar_cid")
                if isinstance(active_agent, dict)
                else getattr(active_agent, "rigged_avatar_cid", "")
            )
            or (
                active_agent.get("voice_model_cid")
                if isinstance(active_agent, dict)
                else getattr(active_agent, "voice_model_cid", "")
            )
            or ""
        )
        rigged_avatar_cid = (
            os.getenv("AVATAR_RIGGED_ASSET")
            or (
                active_agent.get("rigged_avatar_cid")
                if isinstance(active_agent, dict)
                else getattr(active_agent, "rigged_avatar_cid", "")
            )
            or avatar_asset
        )
        vrm_avatar_url = (
            os.getenv("AVATAR_VRM_URL")
            or (
                active_agent.get("vrm_avatar_url")
                if isinstance(active_agent, dict)
                else getattr(active_agent, "vrm_avatar_url", "")
            )
            or ""
        )

        beat = snapshot.get("last_beat") or snapshot.get("beat")
        pair_state = snapshot.get("pair_state")
        if beat is not None:
            self._visual_reactor.on_beat_delivered(
                beat,
                pair_state if isinstance(pair_state, PairState) else pair_state,
                agents,
                current_epoch=current_epoch,
            )
            if _beat_quality(beat) > 12 and _beat_speaker(beat):
                receiver_id = str(
                    snapshot.get("receiver_soul_id") or snapshot.get("receiver") or ""
                )
                if receiver_id:
                    self._visual_reactor.on_landed_hit(
                        beat, receiver_id, agents, current_epoch=current_epoch
                    )

        if len(agents) > 1:
            scene_ctx = self._build_scene_context(snapshot)
            pair_states = snapshot.get("pair_states") or {}
            visual_states = self._agent_visual_state_map(agents)
            scene_layout = self._scene_composer.compose_scene(scene_ctx, pair_states, visual_states)
            self._last_scene_layout = scene_layout.to_dict()
        else:
            self._last_scene_layout = None

        motion = (
            "idle"
            if snapshot.get("resilience", {}).get("tier") == "cold-start"
            else ("talking" if speaking else "live-reactive")
        )
        mouth_open = float(voice_plan.get("mouth_open") or 0.0)
        if speaking and mouth_open <= 0.0:
            mouth_open = 0.42 if expression not in {"calm", "neutral"} else 0.28
        presentation_mode = "speaking" if speaking else "listening"
        plan = AvatarPlan(
            speaker=active_name,
            agent_id=agent_id,
            renderer=self.renderer,
            avatar_format=self.avatar_format,
            expression=expression,
            pose=pose,
            motion=motion,
            lip_sync_source=os.getenv(
                "AVATAR_LIP_SYNC_SOURCE", os.getenv("LIP_SYNC_SOURCE", "audio")
            ),
            render_target=os.getenv("AVATAR_RENDER_TARGET", "obs-virtual-camera"),
            speaker_soul_id=agent_id,
            speaking=speaking,
            mouth_open=mouth_open,
            presentation_mode=presentation_mode,
            rigged_avatar_cid=rigged_avatar_cid,
            vrm_avatar_url=vrm_avatar_url,
            notes=tuple(
                filter(
                    None,
                    [
                        f"speaker={active_name}",
                        f"agent={agent_id[:8] if agent_id else 'none'}",
                        f"expression={expression}",
                        f"pose={pose}",
                        f"scene_layout={self._last_scene_layout['composition_type']}"
                        if self._last_scene_layout
                        else "",
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
            speaker_soul_id=agent_id,
            speaking=speaking,
            mouth_open=mouth_open,
            presentation_mode=presentation_mode,
            rigged_avatar_cid=rigged_avatar_cid,
            vrm_avatar_url=vrm_avatar_url,
        )

    def _build_scene_context(self, snapshot: dict[str, Any]) -> SceneContextData:
        context = snapshot.get("scene_context")
        if isinstance(context, SceneContextData):
            return context
        scene_ctx = SceneContextData()
        recent_beats = snapshot.get("recent_beats") or []
        if isinstance(recent_beats, list):
            for beat in recent_beats[-3:]:
                if isinstance(beat, Beat):
                    scene_ctx.recent_beats.append(beat)
                elif isinstance(beat, dict):
                    try:
                        scene_ctx.recent_beats.append(Beat(**beat))
                    except Exception:
                        continue
        scene_ctx.has_the_room = snapshot.get("has_the_room")
        scene_ctx.scene_energy = str(snapshot.get("scene_energy") or "neutral")
        landed_hit = snapshot.get("landed_hit")
        if isinstance(landed_hit, Beat):
            scene_ctx.landed_hit = landed_hit
        elif isinstance(landed_hit, dict):
            try:
                scene_ctx.landed_hit = Beat(**landed_hit)
            except Exception:
                scene_ctx.landed_hit = None
        scene_ctx.landed_hit_remaining = int(snapshot.get("landed_hit_remaining") or 0)
        return scene_ctx

    def _agent_visual_state_map(self, agents: list[Any]) -> dict[str, Any]:
        mapping: dict[str, Any] = {}
        for agent in agents:
            key = _agent_key(agent)
            if not key:
                continue
            mapping[key] = _visual_state(agent)
        return mapping

    def status(self) -> dict[str, Any]:
        return build_avatar_status()


def build_avatar_status() -> dict[str, Any]:
    endpoint = os.getenv("AVATAR_HEALTH_URL") or os.getenv("AVATAR_ENDPOINT")
    return {
        "enabled": _env_bool("AVATAR_ENABLED") or bool(os.getenv("AVATAR_ASSET")) or bool(endpoint),
        "dry_run": _env_bool("AVATAR_DRY_RUN", "true"),
        "renderer": os.getenv("AVATAR_RENDERER", "vrm"),
        "avatar_format": os.getenv("AVATAR_FORMAT", "vrm"),
        "avatar_asset": os.getenv("AVATAR_ASSET", ""),
        "rigged_avatar_cid": os.getenv("AVATAR_RIGGED_ASSET", ""),
        "vrm_avatar_url": os.getenv("AVATAR_VRM_URL", ""),
        "lip_sync_source": os.getenv(
            "AVATAR_LIP_SYNC_SOURCE", os.getenv("LIP_SYNC_SOURCE", "audio")
        ),
        "render_target": os.getenv("AVATAR_RENDER_TARGET", "obs-virtual-camera"),
        "transport": os.getenv("AVATAR_TRANSPORT", "local-avatar"),
        "health": probe_url(endpoint, timeout=1.5),
    }


def build_avatar_state(snapshot: dict[str, Any]) -> dict[str, Any]:
    return AvatarSurface().compose(snapshot).to_dict()


def build_avatar_status_surface() -> dict[str, Any]:
    return build_avatar_status()
