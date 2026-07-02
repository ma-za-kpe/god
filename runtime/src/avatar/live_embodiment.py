"""Live speech-driven avatar embodiment sidecar contract."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote, urlparse

try:  # pragma: no cover - runtime package import path
    from ..health_checks import probe_url
    from ..runtime_endpoints import embodiment_base_url, embodiment_health_url, endpoint_path
except ImportError:  # pragma: no cover - flat test path
    from health_checks import probe_url
    from runtime_endpoints import embodiment_base_url, embodiment_health_url, endpoint_path


def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _valid_live_url(value: str) -> bool:
    parsed = urlparse(str(value or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _ready_from_body(body: Any) -> bool:
    if not isinstance(body, dict):
        return False
    if body.get("ready") is True or body.get("live_ready") is True:
        return True
    if body.get("model_loaded") is True and body.get("status") in {"ready", "ok", "healthy"}:
        return True
    if body.get("session_ready") is True and body.get("renderer") in {
        "musetalk",
        "liveportrait",
        "wav2lip",
    }:
        return True
    return False


class LiveEmbodimentClient:
    """Resolve readiness and stream URLs for a realtime talking-head sidecar."""

    def __init__(self, *, enabled: bool | None = None, timeout: float = 1.5):
        self.enabled = _env_bool("LIVE_EMBODIMENT_ENABLED") if enabled is None else enabled
        self.timeout = timeout
        self.endpoint = embodiment_base_url()
        self.health_url = embodiment_health_url()
        self.stream_url_template = os.getenv("LIVE_EMBODIMENT_STREAM_URL_TEMPLATE", "").strip()
        self.provider = os.getenv("LIVE_EMBODIMENT_PROVIDER", "musetalk").strip() or "musetalk"

    def status(self) -> dict[str, Any]:
        if not self.enabled:
            return {
                "enabled": False,
                "ready": False,
                "provider": self.provider,
                "health": {"ok": False, "probe": "skipped", "reason": "disabled"},
            }
        health = probe_url(self.health_url, timeout=self.timeout)
        ready = bool(health.get("ok")) and _ready_from_body(health.get("body"))
        return {
            "enabled": True,
            "ready": ready,
            "provider": self.provider,
            "endpoint": self.endpoint,
            "health_url": self.health_url,
            "stream_url_template_configured": bool(self.stream_url_template),
            "health": health,
        }

    def live_video_asset(self, *, soul_id: str, utterance_id: str = "") -> dict[str, Any]:
        status = self.status()
        if not status.get("ready"):
            return {}
        url = self._stream_url(soul_id=soul_id, utterance_id=utterance_id)
        if not _valid_live_url(url):
            return {}
        return {
            "url": url,
            "kind": "live",
            "mime_type": os.getenv("LIVE_EMBODIMENT_MIME_TYPE", "application/vnd.apple.mpegurl"),
            "provider": self.provider,
            "source": "live_embodiment",
            "soul_id": soul_id,
            "utterance_id": utterance_id,
        }

    def _stream_url(self, *, soul_id: str, utterance_id: str = "") -> str:
        safe_soul = quote(str(soul_id or ""), safe="")
        safe_utterance = quote(str(utterance_id or ""), safe="")
        if self.stream_url_template:
            try:
                return self.stream_url_template.format(
                    soul_id=safe_soul,
                    utterance_id=safe_utterance,
                    provider=quote(self.provider, safe=""),
                )
            except Exception:
                return ""
        if not self.endpoint or not safe_soul:
            return ""
        path = f"/stream/{safe_soul}"
        if safe_utterance:
            path = f"{path}/{safe_utterance}"
        return endpoint_path(self.endpoint, path)
