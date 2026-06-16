"""Voice planning surface for TTS and lip-sync wiring."""

from __future__ import annotations

import os
from typing import Any

try:  # pragma: no cover - runtime package import path
    from ..health_checks import probe_url
except ImportError:  # pragma: no cover - flat test path
    from health_checks import probe_url

from .state import VoicePlan, VoiceState


def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")


def _pick_emotion(snapshot: dict[str, Any]) -> str:
    showrunner = snapshot.get("showrunner") or {}
    audience = snapshot.get("audience") or {}
    broadcast = snapshot.get("broadcast") or {}
    scene = str(showrunner.get("scene") or broadcast.get("scene", {}).get("scene_name") or "").lower()
    pressure = float(audience.get("patronage_index") or 0)
    if pressure >= 20:
        return "charged"
    if "banter" in scene or "chat" in scene:
        return "playful"
    if "economy" in scene or "market" in scene:
        return "measured"
    if "void" in scene or "silence" in scene:
        return "hushed"
    return "focused"


def _pick_voice_name() -> str:
    return os.getenv("VOICE_NAME") or os.getenv("TTS_VOICE") or os.getenv("KOKORO_VOICE") or "narrator"


def _pick_voice_model() -> str:
    return os.getenv("TTS_MODEL") or os.getenv("VOICE_MODEL") or os.getenv("KOKORO_MODEL") or "kokoro"


def build_voice_status() -> dict[str, Any]:
    endpoint = os.getenv("VOICE_HEALTH_URL") or os.getenv("TTS_ENDPOINT")
    provider = os.getenv("VOICE_PROVIDER") or os.getenv("TTS_PROVIDER") or "kokoro"
    return {
        "enabled": _env_bool("VOICE_ENABLED") or bool(os.getenv("TTS_MODEL")) or bool(endpoint),
        "dry_run": _env_bool("VOICE_DRY_RUN", "true"),
        "provider": provider,
        "voice_model": _pick_voice_model(),
        "voice_name": _pick_voice_name(),
        "speech_profile": os.getenv("VOICE_PROFILE", "dramatic"),
        "lip_sync_source": os.getenv("LIP_SYNC_SOURCE", "audio"),
        "transport": os.getenv("VOICE_TRANSPORT", "local-tts"),
        "health": probe_url(endpoint, timeout=1.5),
        "render_target": os.getenv("VOICE_RENDER_TARGET", "obs-audio"),
        "sample_rate": int(os.getenv("VOICE_SAMPLE_RATE", "48000")),
    }


class VoiceSurface:
    """Compose a voice plan from the live world snapshot."""

    def __init__(self, enabled: bool | None = None, dry_run: bool | None = None):
        self.enabled = _env_bool("VOICE_ENABLED") if enabled is None else enabled
        self.dry_run = _env_bool("VOICE_DRY_RUN", "true") if dry_run is None else dry_run
        self.provider = os.getenv("VOICE_PROVIDER") or os.getenv("TTS_PROVIDER") or "kokoro"
        self.transport = os.getenv("VOICE_TRANSPORT", "local-tts")

    def compose(self, snapshot: dict[str, Any]) -> VoiceState:
        showrunner = snapshot.get("showrunner") or {}
        broadcast = snapshot.get("broadcast") or {}
        speaker = str(showrunner.get("speaker") or broadcast.get("scene", {}).get("speaker") or "Narrator")
        line = str(showrunner.get("headline") or broadcast.get("caption", {}).get("headline") or "The world keeps moving.")
        emotion = _pick_emotion(snapshot)
        voice_model = _pick_voice_model()
        voice_name = _pick_voice_name()
        health = probe_url(os.getenv("VOICE_HEALTH_URL") or os.getenv("TTS_ENDPOINT"), timeout=1.5)
        plan = VoicePlan(
            speaker=speaker,
            line=line,
            emotion=emotion,
            voice_provider=self.provider,
            voice_model=voice_model,
            voice_name=voice_name,
            pitch=float(os.getenv("VOICE_PITCH", "0.5")),
            speed=float(os.getenv("VOICE_SPEED", "1.0")),
            sample_rate=int(os.getenv("VOICE_SAMPLE_RATE", "48000")),
            lip_sync_source=os.getenv("LIP_SYNC_SOURCE", "audio"),
            transport=self.transport,
            notes=tuple(
                filter(
                    None,
                    [
                        f"scene={showrunner.get('scene') or 'world-wide'}",
                        f"speaker={speaker}",
                        f"emotion={emotion}",
                        f"voice={voice_name}",
                    ],
                )
            ),
        )
        return VoiceState(
            enabled=self.enabled,
            dry_run=self.dry_run,
            provider=self.provider,
            voice_model=voice_model,
            voice_name=voice_name,
            speech_profile=os.getenv("VOICE_PROFILE", "dramatic"),
            lip_sync_source=os.getenv("LIP_SYNC_SOURCE", "audio"),
            transport=self.transport,
            health=health,
            plan=plan,
        )

    def status(self) -> dict[str, Any]:
        return build_voice_status()


def build_voice_state(snapshot: dict[str, Any]) -> dict[str, Any]:
    return VoiceSurface().compose(snapshot).to_dict()


def build_voice_status_surface() -> dict[str, Any]:
    return build_voice_status()
