"""ComfyUI video generation client skeleton."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx

try:  # pragma: no cover - runtime package import path
    from ..gpu import GPUJobQueue, GPUJobRejected, JobPriority, get_gpu_job_queue
except ImportError:  # pragma: no cover - flat test path
    from gpu import GPUJobQueue, GPUJobRejected, JobPriority, get_gpu_job_queue

try:  # pragma: no cover - runtime package import path
    from .video_manifest import VideoAsset, VideoManifest, VideoVariant
except ImportError:  # pragma: no cover - flat test path
    from avatar.video_manifest import VideoAsset, VideoManifest, VideoVariant


@dataclass(frozen=True)
class VideoGenerationResult:
    ok: bool
    video_bytes: bytes = b""
    prompt_id: str = ""
    filename: str = ""
    content_type: str = ""
    error: str = ""


@dataclass(frozen=True)
class LTXLoopRequest:
    agent_id: str
    portrait_cid: str
    motion: str
    expression: str = "neutral"
    width: int = 640
    height: int = 360
    duration_ms: int = 5000
    priority: int = 50
    source_audio_cid: str = ""
    expires_at: float | None = None
    workflow_template: str = "ltx_image_to_video_loop.json"


@dataclass(frozen=True)
class QualityClipRequest:
    agent_id: str
    portrait_cid: str
    prompt: str
    expression: str = "cinematic"
    motion: str = "cinematic"
    width: int = 1280
    height: int = 720
    duration_ms: int = 8000
    priority: int = 90
    source_audio_cid: str = ""
    expires_at: float | None = None
    workflow_template: str = "wan_cinematic_clip.json"
    model: str = "wan"
    job_priority: JobPriority = JobPriority.WAN_BACKGROUND
    variant: VideoVariant = VideoVariant.HIGH_RES_HIGHLIGHT


@dataclass(frozen=True)
class VideoAssetGeneration:
    result: VideoGenerationResult
    manifest: VideoManifest
    asset: VideoAsset | None = None
    pin_cid: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.result.ok and self.asset is not None and bool(self.pin_cid)


PinVideo = Callable[[bytes], Awaitable[Any]]


class VideoGenerator:
    """Submit ComfyUI video workflows and fetch MP4/WebM outputs."""

    def __init__(self, comfy_endpoint: str, *, timeout_s: int = 300) -> None:
        self.endpoint = (comfy_endpoint or "").rstrip("/")
        self.timeout_s = timeout_s

    async def health_check(self) -> bool:
        if not self.endpoint:
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.endpoint}/system_stats")
                return 200 <= response.status_code < 300
        except Exception:
            return False

    async def submit_workflow(
        self, workflow_template: dict[str, Any], replacements: dict[str, Any]
    ) -> bytes | None:
        result = await self.submit_workflow_result(workflow_template, replacements)
        return result.video_bytes if result.ok else None

    async def submit_workflow_result(
        self, workflow_template: dict[str, Any], replacements: dict[str, Any]
    ) -> VideoGenerationResult:
        if not self.endpoint:
            return VideoGenerationResult(ok=False, error="comfy_endpoint_not_configured")
        workflow = self._replace_tokens(workflow_template, replacements)
        workflow = {key: value for key, value in workflow.items() if key != "_meta"}

        async with httpx.AsyncClient(timeout=self.timeout_s, follow_redirects=True) as client:
            response = await client.post(f"{self.endpoint}/prompt", json={"prompt": workflow})
            if response.status_code >= 400:
                return VideoGenerationResult(
                    ok=False,
                    error=f"workflow_submit_failed:{response.status_code}",
                )
            data = response.json()
            prompt_id = data.get("prompt_id")
            if not prompt_id:
                return VideoGenerationResult(ok=False, error="missing_prompt_id")
            return await self._poll_for_video(client, str(prompt_id))

    async def generate_loop(
        self,
        *,
        template_name: str,
        portrait_cid: str,
        motion: str,
        model: str = "ltx",
        replacements: dict[str, Any] | None = None,
    ) -> bytes | None:
        template = self._load_workflow_template(template_name)
        merged = {
            "{{PORTRAIT_CID}}": portrait_cid,
            "{{MOTION_PROMPT}}": motion,
            "{{VIDEO_MODEL}}": model,
            **(replacements or {}),
        }
        return await self.submit_workflow(template, merged)

    async def generate_loop_result(
        self,
        *,
        template_name: str,
        portrait_cid: str,
        motion: str,
        model: str = "ltx",
        replacements: dict[str, Any] | None = None,
    ) -> VideoGenerationResult:
        template = self._load_workflow_template(template_name)
        merged = {
            "{{PORTRAIT_CID}}": portrait_cid,
            "{{MOTION_PROMPT}}": motion,
            "{{VIDEO_MODEL}}": model,
            **(replacements or {}),
        }
        return await self.submit_workflow_result(template, merged)

    async def generate_ltx_loop_asset(
        self,
        request: LTXLoopRequest,
        *,
        manifest: VideoManifest,
        pin_video: PinVideo,
        queue: GPUJobQueue | None = None,
        now: float | None = None,
    ) -> VideoAssetGeneration:
        queue = queue or get_gpu_job_queue()
        try:
            async with queue.acquire(JobPriority.LTX_BACKGROUND, job_name="ltx_loop_generation"):
                result = await self.generate_loop_result(
                    template_name=request.workflow_template,
                    portrait_cid=request.portrait_cid,
                    motion=request.motion,
                    model="ltx",
                    replacements={
                        "{{WIDTH}}": request.width,
                        "{{HEIGHT}}": request.height,
                        "{{DURATION_MS}}": request.duration_ms,
                    },
                )
        except GPUJobRejected as exc:
            result = VideoGenerationResult(ok=False, error=f"gpu_job_rejected:{exc}")
            return VideoAssetGeneration(result=result, manifest=manifest, error=result.error)

        if not result.ok:
            return VideoAssetGeneration(result=result, manifest=manifest, error=result.error)

        pin_result = await pin_video(result.video_bytes)
        pin_ok = bool(getattr(pin_result, "ok", pin_result))
        pin_cid = str(getattr(pin_result, "cid", "") or "")
        if not pin_ok or not pin_cid:
            error = "ipfs_pin_failed"
            return VideoAssetGeneration(
                result=VideoGenerationResult(
                    ok=False,
                    video_bytes=result.video_bytes,
                    prompt_id=result.prompt_id,
                    filename=result.filename,
                    content_type=result.content_type,
                    error=error,
                ),
                manifest=manifest,
                error=error,
            )

        created_at = time.time() if now is None else now
        asset = VideoAsset(
            asset_id=f"ltx-{request.agent_id}-{int(created_at)}",
            cid=pin_cid,
            variant=VideoVariant.LOW_RES_LIVE,
            model="ltx",
            width=request.width,
            height=request.height,
            duration_ms=request.duration_ms,
            source_image_cid=request.portrait_cid,
            source_audio_cid=request.source_audio_cid,
            expression=request.expression,
            motion=request.motion,
            priority=request.priority,
            created_at=created_at,
            expires_at=request.expires_at,
            mime_type=result.content_type or "video/mp4",
            size_bytes=len(result.video_bytes),
        )
        updated_manifest = VideoManifest(
            schema_version=manifest.schema_version,
            agent_id=manifest.agent_id or request.agent_id,
            static_portrait_cid=manifest.static_portrait_cid or request.portrait_cid,
            generated_at=manifest.generated_at or created_at,
            retention=manifest.retention,
            assets=(*manifest.assets, asset),
        )
        return VideoAssetGeneration(
            result=result,
            manifest=updated_manifest,
            asset=asset,
            pin_cid=pin_cid,
        )

    async def generate_quality_clip_asset(
        self,
        request: QualityClipRequest,
        *,
        manifest: VideoManifest,
        pin_video: PinVideo,
        queue: GPUJobQueue | None = None,
        now: float | None = None,
    ) -> VideoAssetGeneration:
        queue = queue or get_gpu_job_queue()
        try:
            async with queue.acquire(
                request.job_priority, job_name=f"{request.model}_quality_clip"
            ):
                result = await self.generate_loop_result(
                    template_name=request.workflow_template,
                    portrait_cid=request.portrait_cid,
                    motion=request.motion,
                    model=request.model,
                    replacements={
                        "{{PROMPT}}": request.prompt,
                        "{{WIDTH}}": request.width,
                        "{{HEIGHT}}": request.height,
                        "{{DURATION_MS}}": request.duration_ms,
                        "{{SOURCE_AUDIO_CID}}": request.source_audio_cid,
                    },
                )
        except GPUJobRejected as exc:
            result = VideoGenerationResult(ok=False, error=f"gpu_job_rejected:{exc}")
            return VideoAssetGeneration(result=result, manifest=manifest, error=result.error)

        if not result.ok:
            return VideoAssetGeneration(result=result, manifest=manifest, error=result.error)

        pin_result = await pin_video(result.video_bytes)
        pin_ok = bool(getattr(pin_result, "ok", pin_result))
        pin_cid = str(getattr(pin_result, "cid", "") or "")
        if not pin_ok or not pin_cid:
            error = "ipfs_pin_failed"
            return VideoAssetGeneration(
                result=VideoGenerationResult(
                    ok=False,
                    video_bytes=result.video_bytes,
                    prompt_id=result.prompt_id,
                    filename=result.filename,
                    content_type=result.content_type,
                    error=error,
                ),
                manifest=manifest,
                error=error,
            )

        created_at = time.time() if now is None else now
        asset = VideoAsset(
            asset_id=f"{request.model}-{request.agent_id}-{int(created_at)}",
            cid=pin_cid,
            variant=request.variant,
            model=request.model,
            width=request.width,
            height=request.height,
            duration_ms=request.duration_ms,
            source_image_cid=request.portrait_cid,
            source_audio_cid=request.source_audio_cid,
            expression=request.expression,
            motion=request.motion,
            priority=request.priority,
            created_at=created_at,
            expires_at=request.expires_at,
            mime_type=result.content_type or "video/mp4",
            size_bytes=len(result.video_bytes),
        )
        updated_manifest = VideoManifest(
            schema_version=manifest.schema_version,
            agent_id=manifest.agent_id or request.agent_id,
            static_portrait_cid=manifest.static_portrait_cid or request.portrait_cid,
            generated_at=manifest.generated_at or created_at,
            retention=manifest.retention,
            assets=(*manifest.assets, asset),
        )
        return VideoAssetGeneration(
            result=result,
            manifest=updated_manifest,
            asset=asset,
            pin_cid=pin_cid,
        )

    async def _poll_for_video(
        self, client: httpx.AsyncClient, prompt_id: str
    ) -> VideoGenerationResult:
        deadline = asyncio.get_running_loop().time() + self.timeout_s
        while asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(2)
            history = await client.get(f"{self.endpoint}/history/{prompt_id}")
            if history.status_code != 200:
                continue
            entry = history.json().get(prompt_id)
            if not entry:
                continue
            return await self._fetch_video_output(client, entry, prompt_id=prompt_id)
        return VideoGenerationResult(
            ok=False, prompt_id=prompt_id, error="video_generation_timeout"
        )

    async def _fetch_video_output(
        self, client: httpx.AsyncClient, history_entry: dict[str, Any], *, prompt_id: str
    ) -> VideoGenerationResult:
        for output in history_entry.get("outputs", {}).values():
            for item in (
                output.get("gifs", []) + output.get("videos", []) + output.get("images", [])
            ):
                filename = item.get("filename")
                if not filename:
                    continue
                response = await client.get(
                    f"{self.endpoint}/view",
                    params={
                        "filename": filename,
                        "subfolder": item.get("subfolder", ""),
                        "type": item.get("type", "output"),
                    },
                )
                if response.status_code == 200 and self.validate_video_bytes(response.content):
                    return VideoGenerationResult(
                        ok=True,
                        video_bytes=response.content,
                        prompt_id=prompt_id,
                        filename=filename,
                        content_type=response.headers.get("content-type", "video/mp4"),
                    )
        return VideoGenerationResult(ok=False, prompt_id=prompt_id, error="video_output_missing")

    def _load_workflow_template(self, template_name: str) -> dict[str, Any]:
        candidates = [
            Path(__file__).resolve().parents[2] / "workflows" / template_name,
            Path(__file__).resolve().parents[3] / "runtime" / "workflows" / template_name,
            Path.cwd() / "runtime" / "workflows" / template_name,
        ]
        for path in candidates:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        return {}

    def _replace_tokens(self, value: Any, replacements: dict[str, Any]) -> Any:
        if isinstance(value, dict):
            return {key: self._replace_tokens(item, replacements) for key, item in value.items()}
        if isinstance(value, list):
            return [self._replace_tokens(item, replacements) for item in value]
        if isinstance(value, str):
            result = value
            for token, replacement in replacements.items():
                result = result.replace(token, str(replacement))
            return result
        return value

    def validate_video_bytes(self, payload: bytes | None) -> bool:
        if not payload or len(payload) < 1024:
            return False
        return b"ftyp" in payload[:64] or payload.startswith(b"\x1aE\xdf\xa3")
