"""Shared runtime service endpoint resolution.

Docker Compose, local host tools, and Vast native deployments expose the same
services through different hostnames. Keep the selection rules here so runtime
surfaces can be tested without live services.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse


_HEALTH_SUFFIXES = (
    "/v1/health",
    "/system_stats",
    "/api/tags",
    "/health",
)


def normalize_base_url(value: str | None) -> str:
    """Return a trimmed base URL, stripping known health/probe paths."""
    url = str(value or "").strip().rstrip("/")
    if not url:
        return ""
    for suffix in _HEALTH_SUFFIXES:
        if url.endswith(suffix):
            url = url[: -len(suffix)].rstrip("/")
            break
    return url


def endpoint_path(base_url: str | None, path: str) -> str:
    base = normalize_base_url(base_url)
    if not base:
        return ""
    return f"{base}/{path.lstrip('/')}"


def _first_url(*values: str | None, strip_health_path: bool = True) -> str:
    for value in values:
        url = (
            normalize_base_url(value) if strip_health_path else str(value or "").strip().rstrip("/")
        )
        if url:
            return url
    return ""


def _health_url(value: str | None, default_path: str) -> str:
    url = str(value or "").strip().rstrip("/")
    if not url:
        return ""
    parsed = urlparse(url)
    if parsed.scheme in {"http", "https"} and parsed.netloc and parsed.path in {"", "/"}:
        return endpoint_path(url, default_path)
    return url


def comfyui_base_url(explicit: str | None = None) -> str:
    return _first_url(
        explicit,
        os.getenv("COMFYUI_ENDPOINT"),
        os.getenv("COMFYUI_URL"),
        os.getenv("COMFYUI_HEALTH_URL"),
        os.getenv("AVATAR_ENDPOINT"),
        os.getenv("AVATAR_HEALTH_URL"),
    )


def comfyui_health_url(explicit: str | None = None) -> str:
    health = _health_url(explicit, "/system_stats") or _health_url(
        os.getenv("COMFYUI_HEALTH_URL"), "/system_stats"
    )
    return health or endpoint_path(comfyui_base_url(), "/system_stats")


def avatar_base_url(explicit: str | None = None) -> str:
    return _first_url(explicit, os.getenv("AVATAR_ENDPOINT"), os.getenv("AVATAR_HEALTH_URL"))


def avatar_health_url(explicit: str | None = None) -> str:
    health = _first_url(explicit, os.getenv("AVATAR_HEALTH_URL"), strip_health_path=False)
    return health or avatar_base_url()


def tts_base_url(explicit: str | None = None) -> str:
    return _first_url(
        explicit,
        os.getenv("TTS_ENDPOINT"),
        os.getenv("FISH_SPEECH_ENDPOINT"),
        os.getenv("VOICE_ENDPOINT"),
        os.getenv("VOICE_HEALTH_URL"),
        os.getenv("TTS_HEALTH_URL"),
    )


def tts_health_url(explicit: str | None = None) -> str:
    health = (
        _health_url(explicit, "/v1/health")
        or _health_url(os.getenv("VOICE_HEALTH_URL"), "/v1/health")
        or _health_url(os.getenv("TTS_HEALTH_URL"), "/v1/health")
    )
    return health or endpoint_path(tts_base_url(), "/v1/health")


def tts_synthesis_url(explicit: str | None = None) -> str:
    return endpoint_path(tts_base_url(explicit), "/v1/tts")


def ollama_base_url(explicit: str | None = None) -> str:
    # Docker Compose sets OLLAMA_BASE_URL to host.docker.internal; Vast native
    # setup scripts set it to localhost. The fallback is for direct host runs.
    return _first_url(
        explicit,
        os.getenv("OLLAMA_BASE_URL"),
        os.getenv("OLLAMA_URL"),
        "http://localhost:11434",
    )


def ollama_generate_url(explicit: str | None = None) -> str:
    return endpoint_path(ollama_base_url(explicit), "/api/generate")


def ollama_tags_url(explicit: str | None = None) -> str:
    return endpoint_path(ollama_base_url(explicit), "/api/tags")


def ipfs_api_url(explicit: str | None = None) -> str:
    return _first_url(explicit, os.getenv("IPFS_API"), "http://localhost:5001")


def tcp_target_from_url(url: str | None, default_port: int) -> tuple[str | None, int | None]:
    raw = str(url or "").strip()
    if not raw:
        return None, None
    parsed = urlparse(raw)
    if parsed.hostname:
        return parsed.hostname, parsed.port or default_port
    if ":" in raw:
        host, _, port = raw.rpartition(":")
        try:
            return host or None, int(port)
        except ValueError:
            return raw, default_port
    return raw, default_port


def redis_tcp_target() -> tuple[str | None, int | None]:
    return tcp_target_from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), 6379)


def nats_tcp_target() -> tuple[str | None, int | None]:
    return tcp_target_from_url(os.getenv("NATS_URL", "nats://localhost:4222"), 4222)
