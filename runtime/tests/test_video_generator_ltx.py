"""LTX video generator tests with mocked ComfyUI responses."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

import avatar.video_generator as video_generator
from avatar import LTXLoopRequest, VideoGenerator, VideoManifest
from gpu import GPUJobQueue


MP4_BYTES = b"\x00\x00\x00\x18ftypmp42" + (b"0" * 2048)


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
    def __init__(self, *, empty_history: bool = False, object_info: dict | None = None) -> None:
        self.empty_history = empty_history
        self.object_info = object_info
        self.posts: list[dict] = []
        self.view_params: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, url, json=None, data=None, files=None, params=None):
        self.posts.append(
            {"url": url, "json": json, "data": data, "files": files, "params": params}
        )
        if url.endswith("/api/v0/cat"):
            return _Response(content=b"\x89PNG\r\n\x1a\n" + (b"0" * 2048))
        if url.endswith("/upload/image"):
            filename = files["image"][0] if files and "image" in files else "upload.png"
            return _Response(payload={"name": filename, "type": "input"})
        return _Response(payload={"prompt_id": "prompt-1"})

    async def get(self, url, params=None):
        if url.endswith("/object_info") and self.object_info is not None:
            return _Response(payload=self.object_info)
        if "/history/" in url:
            if self.empty_history:
                return _Response(payload={})
            return _Response(
                payload={
                    "prompt-1": {
                        "outputs": {
                            "3": {
                                "videos": [
                                    {
                                        "filename": "loop.mp4",
                                        "subfolder": "ltx",
                                        "type": "output",
                                    }
                                ]
                            }
                        }
                    }
                }
            )
        if url.endswith("/view"):
            self.view_params.append(params or {})
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


@pytest.mark.asyncio
async def test_submit_workflow_result_posts_polls_and_fetches_video(monkeypatch):
    client = _FakeComfyClient()
    _patch_comfy(monkeypatch, client)
    generator = VideoGenerator("http://comfy:8188", timeout_s=1)

    result = await generator.submit_workflow_result(
        {
            "_meta": {"name": "test"},
            "1": {"inputs": {"prompt": "{{MOTION_PROMPT}}", "width": "{{WIDTH}}"}},
        },
        {"{{MOTION_PROMPT}}": "idle breathing", "{{WIDTH}}": 640},
    )

    assert result.ok is True
    assert result.video_bytes == MP4_BYTES
    assert result.prompt_id == "prompt-1"
    assert result.filename == "loop.mp4"
    assert client.posts[0]["json"]["prompt"] == {
        "1": {"inputs": {"prompt": "idle breathing", "width": 640}}
    }
    assert client.view_params[0]["filename"] == "loop.mp4"


@pytest.mark.asyncio
async def test_submit_workflow_result_blocks_missing_comfy_nodes_before_prompt(monkeypatch):
    client = _FakeComfyClient(object_info={"LoadImage": {}, "SaveVideo": {}})
    _patch_comfy(monkeypatch, client)
    generator = VideoGenerator("http://comfy:8188", timeout_s=1, stage_ipfs_media=False)

    result = await generator.submit_workflow_result(
        {
            "1": {"class_type": "LoadImageFromIPFS", "inputs": {"cid": "portrait-cid"}},
            "2": {"class_type": "LTXImageToVideo", "inputs": {"image": ["1", 0]}},
        },
        {},
    )

    assert result.ok is False
    assert result.error == "missing_comfy_nodes:LoadImageFromIPFS,LTXImageToVideo"
    assert client.posts == []


@pytest.mark.asyncio
async def test_submit_workflow_result_stages_ipfs_image_before_prompt(monkeypatch):
    client = _FakeComfyClient(object_info={"LoadImage": {}, "SaveVideo": {}})
    _patch_comfy(monkeypatch, client)
    generator = VideoGenerator("http://comfy:8188", timeout_s=1, ipfs_api="http://ipfs:5001")

    result = await generator.submit_workflow_result(
        {
            "1": {"class_type": "LoadImageFromIPFS", "inputs": {"cid": "portrait-cid"}},
            "2": {"class_type": "SaveVideo", "inputs": {"video": ["1", 0]}},
        },
        {},
    )

    assert result.ok is True
    assert client.posts[0]["url"] == "http://ipfs:5001/api/v0/cat"
    assert client.posts[0]["params"] == {"arg": "portrait-cid"}
    assert client.posts[1]["url"] == "http://comfy:8188/upload/image"
    posted_prompt = client.posts[2]["json"]["prompt"]
    assert posted_prompt["1"]["class_type"] == "LoadImage"
    assert posted_prompt["1"]["inputs"]["image"] == "god_image_portrait-cid.png"


@pytest.mark.asyncio
async def test_submit_workflow_result_reports_timeout(monkeypatch):
    client = _FakeComfyClient(empty_history=True)
    _patch_comfy(monkeypatch, client)
    generator = VideoGenerator("http://comfy:8188", timeout_s=0)

    result = await generator.submit_workflow_result({"1": {"inputs": {}}}, {})

    assert result.ok is False
    assert result.error == "video_generation_timeout"


@pytest.mark.asyncio
async def test_submit_workflow_result_interrupts_comfy_when_cancel_requested(monkeypatch):
    client = _FakeComfyClient(empty_history=True)
    _patch_comfy(monkeypatch, client)
    generator = VideoGenerator("http://comfy:8188", timeout_s=1)
    checks = 0

    def cancel_check() -> bool:
        nonlocal checks
        checks += 1
        return checks >= 2

    result = await generator.submit_workflow_result(
        {"1": {"inputs": {}}},
        {},
        cancel_check=cancel_check,
        cancel_reason=lambda: "live_voice_requested",
    )

    assert result.ok is False
    assert result.prompt_id == "prompt-1"
    assert result.error == "video_generation_cancelled:live_voice_requested"
    assert client.posts[0]["url"] == "http://comfy:8188/prompt"
    assert client.posts[1]["url"] == "http://comfy:8188/interrupt"
    assert client.posts[1]["json"] == {"prompt_id": "prompt-1"}


@pytest.mark.asyncio
async def test_generate_ltx_loop_asset_pins_and_registers_manifest_asset(monkeypatch):
    client = _FakeComfyClient()
    _patch_comfy(monkeypatch, client)
    queue = GPUJobQueue()
    generator = VideoGenerator("http://comfy:8188", timeout_s=1)
    manifest = VideoManifest(agent_id="soul-1", static_portrait_cid="portrait-cid")

    async def pin_video(payload: bytes):
        assert payload == MP4_BYTES
        return _Pin(ok=True, cid="cid-ltx-loop")

    generation = await generator.generate_ltx_loop_asset(
        LTXLoopRequest(
            agent_id="soul-1",
            portrait_cid="portrait-cid",
            motion="idle breathing loop",
            expression="calm",
            source_audio_cid="fish-audio-cid",
            expires_at=1000.0,
        ),
        manifest=manifest,
        pin_video=pin_video,
        queue=queue,
        now=200.0,
    )

    assert generation.ok is True
    assert generation.pin_cid == "cid-ltx-loop"
    assert generation.asset is not None
    assert generation.asset.cid == "cid-ltx-loop"
    assert generation.asset.model == "ltx"
    assert generation.asset.source_image_cid == "portrait-cid"
    assert generation.asset.source_audio_cid == "fish-audio-cid"
    assert generation.asset.motion == "idle breathing loop"
    assert generation.manifest.assets == (generation.asset,)
    assert queue.diagnostics()["total_completed"] == 1


@pytest.mark.asyncio
async def test_generate_ltx_loop_asset_is_rejected_when_background_jobs_disabled(monkeypatch):
    client = _FakeComfyClient()
    _patch_comfy(monkeypatch, client)
    queue = GPUJobQueue(background_jobs_allowed=False)
    generator = VideoGenerator("http://comfy:8188", timeout_s=1)
    manifest = VideoManifest(agent_id="soul-1", static_portrait_cid="portrait-cid")
    pin_called = False

    async def pin_video(_payload: bytes):
        nonlocal pin_called
        pin_called = True
        return _Pin(ok=True, cid="cid-ltx-loop")

    generation = await generator.generate_ltx_loop_asset(
        LTXLoopRequest(agent_id="soul-1", portrait_cid="portrait-cid", motion="idle"),
        manifest=manifest,
        pin_video=pin_video,
        queue=queue,
        now=200.0,
    )

    assert generation.ok is False
    assert generation.asset is None
    assert generation.error.startswith("gpu_job_rejected")
    assert generation.manifest.assets == ()
    assert pin_called is False
    assert client.posts == []
