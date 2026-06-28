"""Tests for the avatar genesis pipeline IPFS pinning flow."""

from __future__ import annotations

import pytest

from avatar.genesis_pipeline import GenesisPipeline
from ipfs_client import PinResult
from owned_graph import AgentIdentity, OwnedGraph
from avatar.voice_cloner import VoiceCloner, VoiceCloneResult


class _FakePortraitGenerator:
    def __init__(self, *args, **kwargs):
        pass

    async def health_check(self) -> bool:
        return True

    async def generate_portrait(self, archetype, style_config, **kwargs):
        return b"portrait-bytes"

    async def generate_expressions(self, portrait_ref, expressions, *, archetype_prompt, **kwargs):
        return {name: f"{name}-bytes".encode("utf-8") for name in expressions}


class _FakeVoiceCloner:
    def __init__(self, *args, **kwargs):
        pass

    async def health_check(self) -> bool:
        return True

    async def clone_voice(self, seed_utterance_path, archetype):
        return VoiceCloneResult(
            embedding_bytes=b"voice-embedding-bytes",
            voice_params={"prosody_map": {"CRACK": "wounded"}},
            verification_sample=b"verification-sample",
        )


def _make_graph(soul_id: str = "s-test") -> OwnedGraph:
    identity = AgentIdentity(
        soul_id=soul_id,
        birth_timestamp=123456,
        genesis_world_id="world-1",
        current_name="Test Elder",
    )
    return OwnedGraph(soul_id=soul_id, owner_keys=["pk1"], identity=identity)


@pytest.mark.asyncio
async def test_genesis_pipeline_pins_all_assets(monkeypatch):
    pipeline = GenesisPipeline(
        comfyui_endpoint="http://comfy", tts_endpoint="http://tts", pipeline_timeout_seconds=10
    )
    graph = _make_graph()
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr("avatar.genesis_pipeline.PortraitGenerator", _FakePortraitGenerator)
    monkeypatch.setattr("avatar.genesis_pipeline.VoiceCloner", _FakeVoiceCloner)

    async def fake_pin_bytes(data: bytes, filename: str = "payload.json", **kwargs):
        calls.append((filename, data.decode("utf-8", errors="ignore")))
        if filename.endswith("-portrait.png"):
            return PinResult(ok=True, cid="cid-portrait", pinned_nodes=3, required_nodes=3)
        if filename.endswith("-voice.bin"):
            return PinResult(ok=True, cid="cid-voice", pinned_nodes=3, required_nodes=3)
        if filename.endswith("-neutral.png"):
            return PinResult(ok=True, cid="cid-neutral", pinned_nodes=3, required_nodes=3)
        if filename.endswith("-angry.png"):
            return PinResult(ok=True, cid="cid-angry", pinned_nodes=3, required_nodes=3)
        return PinResult(ok=True, cid=f"cid-{filename}", pinned_nodes=3, required_nodes=3)

    async def fake_pin_json(data: bytes, filename: str = "death_archive.json"):
        return PinResult(ok=True, cid="cid-expressions", pinned_nodes=3, required_nodes=3)

    persist_calls: list[str] = []

    async def fake_persist_identity(self, graph, soul_id, result, correlation_id):
        persist_calls.append(soul_id)

    monkeypatch.setattr("avatar.genesis_pipeline.pin_bytes", fake_pin_bytes)
    monkeypatch.setattr("avatar.genesis_pipeline.pin_json", fake_pin_json)
    monkeypatch.setattr(GenesisPipeline, "_persist_identity", fake_persist_identity)

    result = await pipeline.execute("s-test", "trader", graph)

    assert result.status == "complete"
    assert result.portrait_cid == "cid-portrait"
    assert result.expression_sheet_cid == "cid-expressions"
    assert result.voice_embedding_cid == "cid-voice"
    assert result.assets_produced == 3
    assert graph.identity is not None
    assert graph.identity.avatar_cid == "cid-portrait"
    assert graph.identity.avatar_base_cid == "cid-portrait"
    assert graph.identity.mood_mapping["neutral"] == "cid-neutral"
    assert persist_calls == ["s-test"]


def test_genesis_pipeline_skips_unconfigured_endpoints(monkeypatch):
    monkeypatch.delenv("COMFYUI_ENDPOINT", raising=False)
    monkeypatch.delenv("COMFYUI_HEALTH_URL", raising=False)
    monkeypatch.delenv("COMFYUI_URL", raising=False)
    monkeypatch.delenv("AVATAR_ENDPOINT", raising=False)
    monkeypatch.delenv("AVATAR_HEALTH_URL", raising=False)
    monkeypatch.delenv("TTS_ENDPOINT", raising=False)
    monkeypatch.delenv("FISH_SPEECH_ENDPOINT", raising=False)
    monkeypatch.delenv("VOICE_ENDPOINT", raising=False)
    monkeypatch.delenv("VOICE_HEALTH_URL", raising=False)
    monkeypatch.delenv("TTS_HEALTH_URL", raising=False)

    pipeline = GenesisPipeline()

    assert pipeline.comfyui_endpoint == ""
    assert pipeline.tts_endpoint == ""


def test_genesis_pipeline_uses_configured_endpoint_aliases(monkeypatch):
    monkeypatch.setenv("COMFYUI_HEALTH_URL", "http://comfyui:8188/system_stats")
    monkeypatch.setenv("VOICE_HEALTH_URL", "http://fish-speech:7860/v1/health")

    pipeline = GenesisPipeline()

    assert pipeline.comfyui_endpoint == "http://comfyui:8188"
    assert pipeline.tts_endpoint == "http://fish-speech:7860"


def test_genesis_pipeline_defaults_allow_slow_fish_synthesis(monkeypatch):
    monkeypatch.delenv("PIPELINE_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("VOICE_CLONE_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("TTS_TIMEOUT_SECONDS", raising=False)

    pipeline = GenesisPipeline()
    cloner = VoiceCloner("http://tts")

    assert pipeline.pipeline_timeout_seconds == 600
    assert cloner.timeout_s == 180


def test_voice_cloner_uses_configured_timeout(monkeypatch):
    monkeypatch.setenv("VOICE_CLONE_TIMEOUT_SECONDS", "240")

    cloner = VoiceCloner("http://tts")

    assert cloner.timeout_s == 240


@pytest.mark.asyncio
async def test_genesis_pipeline_records_portrait_pin_failure(monkeypatch):
    pipeline = GenesisPipeline(
        comfyui_endpoint="http://comfy", tts_endpoint="http://tts", pipeline_timeout_seconds=10
    )
    graph = _make_graph()

    monkeypatch.setattr("avatar.genesis_pipeline.PortraitGenerator", _FakePortraitGenerator)
    monkeypatch.setattr("avatar.genesis_pipeline.VoiceCloner", _FakeVoiceCloner)

    async def fake_pin_bytes(data: bytes, filename: str = "payload.json", **kwargs):
        if filename.endswith("-portrait.png"):
            return PinResult(
                ok=False, cid="", pinned_nodes=0, required_nodes=3, errors=("portrait pin failed",)
            )
        if filename.endswith("-voice.bin"):
            return PinResult(ok=True, cid="cid-voice", pinned_nodes=3, required_nodes=3)
        return PinResult(ok=True, cid=f"cid-{filename}", pinned_nodes=3, required_nodes=3)

    async def fake_pin_json(data: bytes, filename: str = "death_archive.json"):
        return PinResult(ok=True, cid="cid-expressions", pinned_nodes=3, required_nodes=3)

    monkeypatch.setattr("avatar.genesis_pipeline.pin_bytes", fake_pin_bytes)
    monkeypatch.setattr("avatar.genesis_pipeline.pin_json", fake_pin_json)

    async def fake_persist_identity(self, graph, soul_id, result, correlation_id):
        return None

    monkeypatch.setattr(GenesisPipeline, "_persist_identity", fake_persist_identity)

    result = await pipeline.execute("s-test", "trader", graph)

    assert result.status == "partial"
    assert result.portrait_cid is None
    assert result.expression_sheet_cid == "cid-expressions"
    assert result.voice_embedding_cid == "cid-voice"
    assert result.assets_produced == 2
    assert any(
        err["step"] == "portrait" and err["message"] == "ipfs_pin_failed" for err in result.errors
    )
    assert graph.identity is not None
    assert graph.identity.avatar_cid == ""
    assert graph.identity.avatar_base_cid == ""


@pytest.mark.asyncio
async def test_genesis_pipeline_records_expression_manifest_failure(monkeypatch):
    pipeline = GenesisPipeline(
        comfyui_endpoint="http://comfy", tts_endpoint="http://tts", pipeline_timeout_seconds=10
    )
    graph = _make_graph()

    monkeypatch.setattr("avatar.genesis_pipeline.PortraitGenerator", _FakePortraitGenerator)
    monkeypatch.setattr("avatar.genesis_pipeline.VoiceCloner", _FakeVoiceCloner)

    async def fake_pin_bytes(data: bytes, filename: str = "payload.json", **kwargs):
        if filename.endswith("-portrait.png"):
            return PinResult(ok=True, cid="cid-portrait", pinned_nodes=3, required_nodes=3)
        if filename.endswith("-voice.bin"):
            return PinResult(ok=True, cid="cid-voice", pinned_nodes=3, required_nodes=3)
        return PinResult(ok=True, cid=f"cid-{filename}", pinned_nodes=3, required_nodes=3)

    async def fake_pin_json(data: bytes, filename: str = "death_archive.json"):
        return PinResult(
            ok=False, cid="", pinned_nodes=0, required_nodes=3, errors=("manifest pin failed",)
        )

    monkeypatch.setattr("avatar.genesis_pipeline.pin_bytes", fake_pin_bytes)
    monkeypatch.setattr("avatar.genesis_pipeline.pin_json", fake_pin_json)

    async def fake_persist_identity(self, graph, soul_id, result, correlation_id):
        return None

    monkeypatch.setattr(GenesisPipeline, "_persist_identity", fake_persist_identity)

    result = await pipeline.execute("s-test", "trader", graph)

    assert result.status == "partial"
    assert result.portrait_cid == "cid-portrait"
    assert result.expression_sheet_cid is None
    assert result.voice_embedding_cid == "cid-voice"
    assert result.assets_produced == 2
    assert any(
        err["step"] == "expression_sheet" and err["message"] == "ipfs_manifest_pin_failed"
        for err in result.errors
    )
    assert graph.identity is not None
    assert graph.identity.mood_mapping["neutral"].startswith("cid-s-test-neutral")
