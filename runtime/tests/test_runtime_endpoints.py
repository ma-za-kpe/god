"""Tests for runtime service endpoint resolution."""

from runtime_endpoints import (
    comfyui_base_url,
    comfyui_health_url,
    endpoint_path,
    nats_tcp_target,
    ollama_base_url,
    ollama_generate_url,
    ollama_tags_url,
    redis_tcp_target,
    tts_base_url,
    tts_health_url,
    tts_synthesis_url,
)


def test_comfyui_endpoint_prefers_configured_base(monkeypatch):
    monkeypatch.setenv("COMFYUI_ENDPOINT", "http://comfyui:8188/")
    monkeypatch.setenv("COMFYUI_HEALTH_URL", "http://override:8188/system_stats")

    assert comfyui_base_url() == "http://comfyui:8188"
    assert comfyui_health_url() == "http://override:8188/system_stats"


def test_comfyui_endpoint_is_empty_when_unconfigured(monkeypatch):
    for name in (
        "COMFYUI_ENDPOINT",
        "COMFYUI_URL",
        "COMFYUI_HEALTH_URL",
        "AVATAR_ENDPOINT",
        "AVATAR_HEALTH_URL",
    ):
        monkeypatch.delenv(name, raising=False)

    assert comfyui_base_url() == ""
    assert comfyui_health_url() == ""


def test_tts_endpoint_normalizes_health_url_to_synthesis_base(monkeypatch):
    monkeypatch.delenv("TTS_ENDPOINT", raising=False)
    monkeypatch.setenv("VOICE_HEALTH_URL", "http://fish-speech:7860/v1/health")

    assert tts_base_url() == "http://fish-speech:7860"
    assert tts_health_url() == "http://fish-speech:7860/v1/health"
    assert tts_synthesis_url() == "http://fish-speech:7860/v1/tts"


def test_tts_health_url_appends_health_path_for_base_url(monkeypatch):
    monkeypatch.delenv("TTS_ENDPOINT", raising=False)
    monkeypatch.setenv("VOICE_HEALTH_URL", "http://localhost:7860")

    assert tts_base_url() == "http://localhost:7860"
    assert tts_health_url() == "http://localhost:7860/v1/health"


def test_ollama_endpoint_uses_env_and_builds_probe_paths(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434/")

    assert ollama_base_url() == "http://host.docker.internal:11434"
    assert ollama_tags_url() == "http://host.docker.internal:11434/api/tags"
    assert ollama_generate_url() == "http://host.docker.internal:11434/api/generate"


def test_tcp_targets_parse_configured_urls(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379")
    monkeypatch.setenv("NATS_URL", "nats://nats:4222")

    assert redis_tcp_target() == ("redis", 6379)
    assert nats_tcp_target() == ("nats", 4222)


def test_endpoint_path_strips_probe_suffix_before_joining():
    assert (
        endpoint_path("http://fish-speech:7860/v1/health", "/v1/tts")
        == "http://fish-speech:7860/v1/tts"
    )
