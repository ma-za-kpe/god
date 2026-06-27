"""Offline quality video generator tests with mocked ComfyUI responses."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

import avatar.video_generator as video_generator
from avatar import QualityClipRequest, VideoGenerator, VideoManifest, VideoVariant
from gpu import GPUJobQueue, JobPriority


MP4_BYTES = b"\x00\x00\x00\x18ftypmp42" + (b"1" * 2048)


class _Response:
    def __init__(
        self,
        *,
        status_code: int = 200,
        payload: dict | None = None,
        content: bytes = b"",
        headers: dict | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.content = content
        self.headers = headers or {}

    def json(self):
        return self._payload


class _FakeComfyClient:
    def __init__(self) -> None:
        self.posts: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, url, json):
        self.posts.append({"url": url, "json": json})
        return _Response(payload={"prompt_id": "quality-1"})

    async def get(self, url, params=None):
        if "/history/" in url:
            return _Response(
                payload={
                    "quality-1": {
                        "outputs": {
                            "3": {
                                "videos": [
                                    {
                                        "filename": "quality.mp4",
                                        "subfolder": "quality",
                                        "type": "output",
                                    }
                                ]
                            },
                            "4": {
                                "videos": [
                                    {
                                        "filename": "lipdub.mp4",
                                        "subfolder": "quality",
                                        "type": "output",
                                    }
                                ]
                            },
                        }
                    }
                }
            )
        if url.endswith("/view"):
            return _Response(content=MP4_BYTES, headers={"content-type": "video/mp4"})
        return _Response(status_code=404)


async def _no_sleep(_seconds: float) -> None:
    return None


@dataclass(frozen=True)
class _Pin:
    ok: bool
    cid: str


def _patch_comfy(monkeypatch, client: _FakeComfyClient) -> None:
    monkeypatch.setattr(video_generator.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr(video_generator.httpx, "AsyncClient", lambda **_kwargs: client)


def _wan_template() -> dict:
    return {
        "_meta": {"name": "wan"},
        "1": {"class_type": "LoadImageFromIPFS", "inputs": {"cid": "{{PORTRAIT_CID}}"}},
        "2": {
            "class_type": "WanImageToVideo",
            "inputs": {
                "image": ["1", 0],
                "prompt": "{{PROMPT}} {{MOTION_PROMPT}}",
                "model": "{{VIDEO_MODEL}}",
                "width": "{{WIDTH}}",
                "height": "{{HEIGHT}}",
                "duration_ms": "{{DURATION_MS}}",
            },
        },
    }


def _lipdub_template() -> dict:
    return {
        "_meta": {"name": "ltx_lipdub"},
        "1": {"class_type": "LoadImageFromIPFS", "inputs": {"cid": "{{PORTRAIT_CID}}"}},
        "2": {"class_type": "LoadAudioFromIPFS", "inputs": {"cid": "{{SOURCE_AUDIO_CID}}"}},
        "3": {
            "class_type": "LTXLipDub",
            "inputs": {
                "image": ["1", 0],
                "audio": ["2", 0],
                "prompt": "{{PROMPT}} {{MOTION_PROMPT}}",
                "model": "{{VIDEO_MODEL}}",
                "width": "{{WIDTH}}",
                "height": "{{HEIGHT}}",
                "duration_ms": "{{DURATION_MS}}",
            },
        },
    }


@pytest.mark.asyncio
async def test_wan_quality_clip_registers_highlight_manifest_asset(monkeypatch):
    client = _FakeComfyClient()
    _patch_comfy(monkeypatch, client)
    generator = VideoGenerator("http://comfy:8188", timeout_s=1)
    monkeypatch.setattr(generator, "_load_workflow_template", lambda _name: _wan_template())
    manifest = VideoManifest(agent_id="soul-1", static_portrait_cid="portrait-cid")
    queue = GPUJobQueue()

    async def pin_video(payload: bytes):
        assert payload == MP4_BYTES
        return _Pin(ok=True, cid="cid-wan")

    generation = await generator.generate_quality_clip_asset(
        QualityClipRequest(
            agent_id="soul-1",
            portrait_cid="portrait-cid",
            prompt="cinematic temple reveal",
            motion="slow camera push",
            width=1280,
            height=720,
        ),
        manifest=manifest,
        pin_video=pin_video,
        queue=queue,
        now=300.0,
    )

    assert generation.ok is True
    assert generation.asset is not None
    assert generation.asset.cid == "cid-wan"
    assert generation.asset.variant == VideoVariant.HIGH_RES_HIGHLIGHT
    assert generation.asset.model == "wan"
    assert generation.asset.resolution == "1280x720"
    posted_prompt = client.posts[0]["json"]["prompt"]
    assert posted_prompt["2"]["inputs"]["model"] == "wan"
    assert "cinematic temple reveal" in posted_prompt["2"]["inputs"]["prompt"]


@pytest.mark.asyncio
async def test_ltx_lipdub_highlight_records_audio_source_and_offline_priority(monkeypatch):
    client = _FakeComfyClient()
    _patch_comfy(monkeypatch, client)
    generator = VideoGenerator("http://comfy:8188", timeout_s=1)
    monkeypatch.setattr(generator, "_load_workflow_template", lambda _name: _lipdub_template())
    manifest = VideoManifest(agent_id="soul-1", static_portrait_cid="portrait-cid")
    queue = GPUJobQueue()

    async def pin_video(_payload: bytes):
        return _Pin(ok=True, cid="cid-lipdub")

    generation = await generator.generate_quality_clip_asset(
        QualityClipRequest(
            agent_id="soul-1",
            portrait_cid="portrait-cid",
            prompt="highlight line delivery",
            motion="clear lip sync",
            source_audio_cid="fish-audio-cid",
            workflow_template="ltx_lipdub_highlight.json",
            model="ltx_lipdub",
            job_priority=JobPriority.OFFLINE_HIGHLIGHT,
        ),
        manifest=manifest,
        pin_video=pin_video,
        queue=queue,
        now=300.0,
    )

    assert generation.ok is True
    assert generation.asset is not None
    assert generation.asset.cid == "cid-lipdub"
    assert generation.asset.model == "ltx_lipdub"
    assert generation.asset.source_audio_cid == "fish-audio-cid"
    posted_prompt = client.posts[0]["json"]["prompt"]
    assert posted_prompt["2"]["inputs"]["cid"] == "fish-audio-cid"
    assert posted_prompt["3"]["inputs"]["model"] == "ltx_lipdub"


@pytest.mark.asyncio
async def test_quality_clip_rejected_when_background_jobs_disabled(monkeypatch):
    client = _FakeComfyClient()
    _patch_comfy(monkeypatch, client)
    generator = VideoGenerator("http://comfy:8188", timeout_s=1)
    manifest = VideoManifest(agent_id="soul-1", static_portrait_cid="portrait-cid")
    queue = GPUJobQueue(background_jobs_allowed=False)
    pin_called = False

    async def pin_video(_payload: bytes):
        nonlocal pin_called
        pin_called = True
        return _Pin(ok=True, cid="cid-wan")

    generation = await generator.generate_quality_clip_asset(
        QualityClipRequest(
            agent_id="soul-1",
            portrait_cid="portrait-cid",
            prompt="cinematic temple reveal",
        ),
        manifest=manifest,
        pin_video=pin_video,
        queue=queue,
        now=300.0,
    )

    assert generation.ok is False
    assert generation.asset is None
    assert generation.error.startswith("gpu_job_rejected")
    assert client.posts == []
    assert pin_called is False
