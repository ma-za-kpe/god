"""Live speech-driven avatar embodiment sidecar contract."""

from __future__ import annotations

import os
import json
import threading
import time
from typing import Any
import urllib.error
import urllib.request
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


_ENSURE_LOCK = threading.Lock()
_ENSURE_CACHE: dict[str, dict[str, Any]] = {}


def post_json(url: str, payload: dict[str, Any], *, timeout: float) -> dict[str, Any]:
    """POST JSON and return a small status payload.

    Kept as a module helper so tests can patch the network boundary without
    exercising threads or a live sidecar.
    """
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(4096)
        try:
            parsed = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            parsed = {}
        return {
            "ok": 200 <= int(getattr(response, "status", 200)) < 300,
            "status": int(getattr(response, "status", 200)),
            "body": parsed,
        }


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
            "last_ensure": self._last_ensure_status(),
            "health": health,
        }

    def live_video_asset(
        self,
        *,
        soul_id: str,
        utterance_id: str = "",
        status: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        status = status or self.status()
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

    def ensure_stream(
        self,
        *,
        soul_id: str,
        utterance_id: str,
        audio_url: str,
        portrait_url: str = "",
        portrait_cid: str = "",
        status: dict[str, Any] | None = None,
        inline: bool | None = None,
    ) -> dict[str, Any]:
        """Queue the sidecar to render the current live Fish utterance.

        The call is nonblocking by default because snapshot composition must
        stay responsive. The sidecar owns serialization and model scheduling.
        """
        if not self.enabled:
            return {"queued": False, "reason": "disabled"}
        if not soul_id or not utterance_id or not _valid_live_url(audio_url):
            return {"queued": False, "reason": "missing_required_fields"}
        status = status or self.status()
        if not status.get("ready"):
            return {"queued": False, "reason": "sidecar_not_ready"}

        endpoint = endpoint_path(self.endpoint, "/embody")
        if not _valid_live_url(endpoint):
            return {"queued": False, "reason": "missing_endpoint"}

        key = f"{self.provider}:{soul_id}:{utterance_id}"
        ttl_s = float(os.getenv("LIVE_EMBODIMENT_ENSURE_TTL_S", "120"))
        now = time.time()
        with _ENSURE_LOCK:
            cached = _ENSURE_CACHE.get(key)
            if cached and now - float(cached.get("at", 0.0)) < ttl_s:
                return {"queued": False, "reason": "recently_ensured", **cached}
            _ENSURE_CACHE[key] = {"at": now, "state": "inflight"}

        payload = {
            "soul_id": soul_id,
            "utterance_id": utterance_id,
            "audio_url": audio_url,
            "portrait_url": portrait_url,
            "portrait_cid": portrait_cid,
            "blocking": False,
        }
        timeout = float(os.getenv("LIVE_EMBODIMENT_ENSURE_TIMEOUT_S", "1.5"))
        run_inline = _env_bool("LIVE_EMBODIMENT_ENSURE_INLINE") if inline is None else inline

        def worker() -> None:
            try:
                result = post_json(endpoint, payload, timeout=timeout)
                state = "queued" if result.get("ok") else "failed"
                with _ENSURE_LOCK:
                    _ENSURE_CACHE[key] = {
                        "at": time.time(),
                        "state": state,
                        "status": result.get("status"),
                    }
            except (OSError, urllib.error.URLError, TimeoutError) as exc:
                with _ENSURE_LOCK:
                    _ENSURE_CACHE[key] = {
                        "at": time.time(),
                        "state": "failed",
                        "error": str(exc)[:240],
                    }

        if run_inline:
            worker()
        else:
            thread = threading.Thread(target=worker, name="live-embodiment-ensure", daemon=True)
            thread.start()
        return {"queued": True, "state": "inflight", "key": key}

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

    def _last_ensure_status(self) -> dict[str, Any]:
        with _ENSURE_LOCK:
            if not _ENSURE_CACHE:
                return {}
            key, value = max(
                _ENSURE_CACHE.items(),
                key=lambda item: float(item[1].get("at", 0.0)),
            )
            return {"key": key, **value}
