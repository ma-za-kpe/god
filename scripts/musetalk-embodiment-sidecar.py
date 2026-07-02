#!/usr/bin/env python3
"""MuseTalk live embodiment sidecar.

This service is intentionally separate from runtime. Runtime keeps Fish audio as
the source of truth, then asks this sidecar to render the current utterance into
a live video asset. The sidecar binds to localhost by default and only loads
trusted local MuseTalk model files.
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import types
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response


def env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def safe_component(value: str, fallback: str = "item") -> str:
    text = str(value or "").strip()
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in text)
    cleaned = cleaned.strip("-_")
    return (cleaned or fallback)[:80]


def utc_ms() -> int:
    return int(time.time() * 1000)


def decode_b64(value: str, *, max_bytes: int) -> bytes:
    raw = base64.b64decode(str(value or ""), validate=True)
    if len(raw) > max_bytes:
        raise ValueError(f"payload_too_large:{len(raw)}>{max_bytes}")
    return raw


def download_limited(url: str, *, max_bytes: int, timeout: float) -> bytes:
    parsed = urllib.parse.urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("unsupported_url")
    request = urllib.request.Request(url, headers={"User-Agent": "god-musetalk-sidecar/1"})
    chunks: list[bytes] = []
    total = 0
    with urllib.request.urlopen(request, timeout=timeout) as response:
        while True:
            chunk = response.read(min(1024 * 1024, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"download_too_large:{total}>{max_bytes}")
    return b"".join(chunks)


@dataclass
class JobState:
    job_id: str
    soul_id: str
    utterance_id: str
    status: str = "queued"
    created_at_ms: int = field(default_factory=utc_ms)
    updated_at_ms: int = field(default_factory=utc_ms)
    latency_ms: float | None = None
    peak_vram_mb: int | None = None
    output_path: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "soul_id": self.soul_id,
            "utterance_id": self.utterance_id,
            "status": self.status,
            "created_at_ms": self.created_at_ms,
            "updated_at_ms": self.updated_at_ms,
            "latency_ms": self.latency_ms,
            "peak_vram_mb": self.peak_vram_mb,
            "output_path": self.output_path,
            "error": self.error,
        }


class MuseTalkRenderer:
    def __init__(self) -> None:
        self.root = Path(os.getenv("MUSETALK_ROOT", "/opt/MuseTalk")).resolve()
        self.out_dir = Path(os.getenv("MUSETALK_OUTPUT_DIR", "/tmp/god-musetalk-sidecar"))
        self.default_source_video = Path(
            os.getenv("MUSETALK_SOURCE_VIDEO", str(self.root / "data/video/yongen.mp4"))
        )
        self.version = os.getenv("MUSETALK_VERSION", "v15")
        self.fps = env_int("MUSETALK_FPS", 25)
        self.batch_size = env_int("MUSETALK_BATCH_SIZE", 20)
        self.max_audio_bytes = env_int("MUSETALK_MAX_AUDIO_BYTES", 16 * 1024 * 1024)
        self.max_portrait_bytes = env_int("MUSETALK_MAX_PORTRAIT_BYTES", 12 * 1024 * 1024)
        self.download_timeout_s = env_float("MUSETALK_DOWNLOAD_TIMEOUT_S", 20.0)
        self.stream_wait_s = env_float("MUSETALK_STREAM_WAIT_S", 120.0)
        self.source_seconds = env_float("MUSETALK_SOURCE_SECONDS", 3.0)

        self._load_lock = threading.Lock()
        self._render_lock = threading.Lock()
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._futures: dict[str, concurrent.futures.Future[Path]] = {}
        self._jobs: dict[str, JobState] = {}
        self._avatars: dict[str, Any] = {}
        self._loading = False
        self._loaded = False
        self._last_error = ""
        self._rt: Any = None
        self._torch: Any = None

    def start_loading(self) -> None:
        if self._loaded or self._loading:
            return
        thread = threading.Thread(target=self.load, name="musetalk-load", daemon=True)
        thread.start()

    def load(self) -> None:
        with self._load_lock:
            if self._loaded:
                return
            self._loading = True
            self._last_error = ""
            try:
                self.out_dir.mkdir(parents=True, exist_ok=True)
                os.chdir(self.root)
                sys.path.insert(0, str(self.root))
                sys.path.insert(0, str(self.root / "musetalk" / "utils"))
                self._install_preprocessing_module()

                import torch
                from transformers import WhisperModel
                from scripts import realtime_inference as rt

                self._torch = torch
                self._patch_torch_load(torch)

                args = SimpleNamespace(
                    version=self.version,
                    ffmpeg_path="./ffmpeg-4.4-amd64-static/",
                    gpu_id=env_int("MUSETALK_GPU_ID", 0),
                    vae_type=os.getenv("MUSETALK_VAE_TYPE", "sd-vae"),
                    unet_config=os.getenv(
                        "MUSETALK_UNET_CONFIG",
                        str(self.root / "models/musetalkV15/musetalk.json"),
                    ),
                    unet_model_path=os.getenv(
                        "MUSETALK_UNET_MODEL",
                        str(self.root / "models/musetalkV15/unet.pth"),
                    ),
                    whisper_dir=os.getenv(
                        "MUSETALK_WHISPER_DIR",
                        str(self.root / "models/whisper"),
                    ),
                    inference_config="",
                    bbox_shift=0,
                    result_dir="./results",
                    extra_margin=env_int("MUSETALK_EXTRA_MARGIN", 10),
                    fps=self.fps,
                    audio_padding_length_left=env_int("MUSETALK_AUDIO_PAD_LEFT", 2),
                    audio_padding_length_right=env_int("MUSETALK_AUDIO_PAD_RIGHT", 2),
                    batch_size=self.batch_size,
                    output_vid_name=None,
                    use_saved_coord=False,
                    saved_coord=False,
                    parsing_mode=os.getenv("MUSETALK_PARSING_MODE", "jaw"),
                    left_cheek_width=env_int("MUSETALK_LEFT_CHEEK_WIDTH", 90),
                    right_cheek_width=env_int("MUSETALK_RIGHT_CHEEK_WIDTH", 90),
                    skip_save_images=False,
                )
                device = torch.device(
                    f"cuda:{args.gpu_id}" if torch.cuda.is_available() else "cpu"
                )
                rt.args = args
                rt.device = device
                rt.vae, rt.unet, rt.pe = rt.load_all_model(
                    unet_model_path=args.unet_model_path,
                    vae_type=args.vae_type,
                    unet_config=args.unet_config,
                    device=device,
                )
                rt.timesteps = torch.tensor([0], device=device)
                rt.pe = rt.pe.half().to(device)
                rt.vae.vae = rt.vae.vae.half().to(device)
                rt.unet.model = rt.unet.model.half().to(device)
                rt.audio_processor = rt.AudioProcessor(feature_extractor_path=args.whisper_dir)
                rt.weight_dtype = rt.unet.model.dtype
                rt.whisper = WhisperModel.from_pretrained(args.whisper_dir)
                rt.whisper = rt.whisper.to(device=device, dtype=rt.weight_dtype).eval()
                rt.whisper.requires_grad_(False)
                rt.fp = rt.FaceParsing(
                    left_cheek_width=args.left_cheek_width,
                    right_cheek_width=args.right_cheek_width,
                )
                self._rt = rt
                self._loaded = True
            except Exception as exc:
                self._last_error = str(exc)
                raise
            finally:
                self._loading = False

    def health(self) -> dict[str, Any]:
        gpu_name = ""
        vram_mb = 0
        if self._torch is not None and self._torch.cuda.is_available():
            gpu_name = self._torch.cuda.get_device_name(0)
            vram_mb = int(self._torch.cuda.memory_allocated(0) / (1024 * 1024))
        return {
            "ready": self._loaded,
            "model_loaded": self._loaded,
            "status": "ready" if self._loaded else ("loading" if self._loading else "warming"),
            "renderer": "musetalk",
            "device": gpu_name or "unknown",
            "vram_allocated_mb": vram_mb,
            "queue_depth": sum(1 for item in self._jobs.values() if item.status in {"queued", "running"}),
            "last_error": self._last_error,
            "output_dir": str(self.out_dir),
        }

    def start_job(self, payload: dict[str, Any]) -> JobState:
        soul_id, utterance_id = self._payload_ids(payload)
        job_id = self.job_id(soul_id, utterance_id)
        output = self.output_path(soul_id, utterance_id)
        state = self._jobs.get(job_id) or JobState(
            job_id=job_id,
            soul_id=soul_id,
            utterance_id=utterance_id,
        )
        if output.exists():
            state.status = "complete"
            state.output_path = str(output)
            state.updated_at_ms = utc_ms()
            self._jobs[job_id] = state
            return state
        future = self._futures.get(job_id)
        if future and not future.done():
            return state
        self._jobs[job_id] = state
        self._futures[job_id] = self._executor.submit(self.render_payload, payload)
        return state

    def render_payload(self, payload: dict[str, Any]) -> Path:
        if not self._loaded:
            self.load()
        soul_id, utterance_id = self._payload_ids(payload)
        job_id = self.job_id(soul_id, utterance_id)
        state = self._jobs.get(job_id) or JobState(job_id, soul_id, utterance_id)
        state.status = "running"
        state.updated_at_ms = utc_ms()
        self._jobs[job_id] = state
        started = time.perf_counter()
        try:
            with self._render_lock:
                output = self._render_locked(payload, soul_id=soul_id, utterance_id=utterance_id)
            state.status = "complete"
            state.output_path = str(output)
            state.latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
            state.peak_vram_mb = self._peak_vram_mb()
            state.updated_at_ms = utc_ms()
            self._jobs[job_id] = state
            return output
        except Exception as exc:
            state.status = "failed"
            state.error = str(exc)[:500]
            state.updated_at_ms = utc_ms()
            self._jobs[job_id] = state
            self._last_error = state.error
            raise

    def job(self, soul_id: str, utterance_id: str) -> JobState | None:
        return self._jobs.get(self.job_id(soul_id, utterance_id))

    def output_path(self, soul_id: str, utterance_id: str) -> Path:
        return self.out_dir / "streams" / safe_component(soul_id) / f"{safe_component(utterance_id)}.mp4"

    def job_id(self, soul_id: str, utterance_id: str) -> str:
        return f"{safe_component(soul_id)}:{safe_component(utterance_id)}"

    def wait_for_output(self, soul_id: str, utterance_id: str, timeout_s: float | None = None) -> Path | None:
        output = self.output_path(soul_id, utterance_id)
        deadline = time.time() + (self.stream_wait_s if timeout_s is None else timeout_s)
        while time.time() < deadline:
            if output.exists() and output.stat().st_size > 0:
                return output
            state = self.job(soul_id, utterance_id)
            if state and state.status == "failed":
                return None
            time.sleep(0.25)
        return output if output.exists() and output.stat().st_size > 0 else None

    def _payload_ids(self, payload: dict[str, Any]) -> tuple[str, str]:
        soul_id = safe_component(str(payload.get("soul_id") or "one"))
        utterance_id = safe_component(str(payload.get("utterance_id") or payload.get("id") or "utterance"))
        return soul_id, utterance_id

    def _render_locked(self, payload: dict[str, Any], *, soul_id: str, utterance_id: str) -> Path:
        assert self._rt is not None
        self._reset_peak_vram()
        audio_path = self._write_audio(payload, soul_id=soul_id, utterance_id=utterance_id)
        source_video = self._source_video(payload, soul_id=soul_id)
        avatar = self._avatar(soul_id=soul_id, source_video=source_video)
        output_name = f"god_{safe_component(utterance_id)}"
        avatar.inference(str(audio_path), output_name, self.fps, False)
        produced = Path(avatar.video_out_path) / f"{output_name}.mp4"
        if not produced.exists() or produced.stat().st_size <= 0:
            raise RuntimeError(f"musetalk_output_missing:{produced}")
        target = self.output_path(soul_id, utterance_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp.mp4")
        shutil.copy2(produced, tmp)
        tmp.replace(target)
        return target

    def _write_audio(self, payload: dict[str, Any], *, soul_id: str, utterance_id: str) -> Path:
        audio_b64 = str(payload.get("audio_bytes") or "")
        if audio_b64:
            data = decode_b64(audio_b64, max_bytes=self.max_audio_bytes)
        else:
            data = download_limited(
                str(payload.get("audio_url") or ""),
                max_bytes=self.max_audio_bytes,
                timeout=self.download_timeout_s,
            )
        if len(data) < 44:
            raise ValueError("audio_payload_too_small")
        path = self.out_dir / "audio" / safe_component(soul_id) / f"{safe_component(utterance_id)}.wav"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def _source_video(self, payload: dict[str, Any], *, soul_id: str) -> Path:
        if not payload.get("portrait_bytes") and not payload.get("portrait_url"):
            return self.default_source_video
        portrait_hash = hashlib.sha256(
            str(payload.get("portrait_url") or payload.get("portrait_cid") or "bytes").encode()
        ).hexdigest()[:12]
        source_dir = self.out_dir / "sources" / safe_component(soul_id)
        source_dir.mkdir(parents=True, exist_ok=True)
        source_video = source_dir / f"{portrait_hash}.mp4"
        if source_video.exists() and source_video.stat().st_size > 0:
            return source_video
        if payload.get("portrait_bytes"):
            portrait = decode_b64(str(payload.get("portrait_bytes")), max_bytes=self.max_portrait_bytes)
        else:
            portrait = download_limited(
                str(payload.get("portrait_url") or ""),
                max_bytes=self.max_portrait_bytes,
                timeout=self.download_timeout_s,
            )
        image_path = source_dir / f"{portrait_hash}.png"
        self._normalize_image(portrait, image_path)
        cmd = [
            "ffmpeg",
            "-y",
            "-v",
            "warning",
            "-loop",
            "1",
            "-framerate",
            str(self.fps),
            "-i",
            str(image_path),
            "-t",
            str(self.source_seconds),
            "-vf",
            "scale=512:-2,format=yuv420p",
            "-r",
            str(self.fps),
            "-pix_fmt",
            "yuv420p",
            str(source_video),
        ]
        subprocess.run(cmd, check=True, timeout=60)
        return source_video

    def _normalize_image(self, data: bytes, out_path: Path) -> None:
        import cv2
        import numpy as np

        arr = np.frombuffer(data, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("portrait_decode_failed")
        cv2.imwrite(str(out_path), frame)

    def _avatar(self, *, soul_id: str, source_video: Path) -> Any:
        assert self._rt is not None
        avatar_id = f"god_{safe_component(soul_id, 'one')}"
        base = self.root / "results" / self.version / "avatars" / avatar_id
        latents = base / "latents.pt"
        info = base / "avator_info.json"
        existing = self._avatars.get(avatar_id)
        if existing is not None and latents.exists():
            return existing
        preparation = not (latents.exists() and info.exists())
        if preparation and base.exists():
            shutil.rmtree(base)
        avatar = self._rt.Avatar(
            avatar_id=avatar_id,
            video_path=str(source_video),
            bbox_shift=0,
            batch_size=self.batch_size,
            preparation=preparation,
        )
        self._avatars[avatar_id] = avatar
        return avatar

    def _install_preprocessing_module(self) -> None:
        if "musetalk.utils.preprocessing" in sys.modules:
            return
        import cv2
        import numpy as np
        import torch
        from face_detection import FaceAlignment, LandmarksType
        from tqdm import tqdm

        device = "cuda" if torch.cuda.is_available() else "cpu"
        face_alignment = FaceAlignment(LandmarksType._2D, flip_input=False, device=device)
        coord_placeholder = (0.0, 0.0, 0.0, 0.0)

        def read_imgs(img_list: list[str]) -> list[Any]:
            frames = []
            print("reading images...")
            for img_path in tqdm(img_list):
                frame = cv2.imread(str(img_path))
                frames.append(frame)
            return frames

        def get_landmark_and_bbox(img_list: list[str], upperbondrange: int = 0) -> tuple[list[Any], list[Any]]:
            frames = read_imgs(img_list)
            coords_list = []
            valid_count = 0
            for frame in tqdm(frames):
                bbox = face_alignment.get_detections_for_batch(np.asarray([frame]))
                for detected in bbox:
                    if detected is None:
                        coords_list.append(coord_placeholder)
                        continue
                    x1, y1, x2, y2 = [int(v) for v in detected]
                    if upperbondrange:
                        y1 = max(0, y1 + int(upperbondrange))
                        y2 = max(y1 + 1, y2 + int(upperbondrange))
                    if y2 - y1 <= 0 or x2 - x1 <= 0 or x1 < 0:
                        coords_list.append(coord_placeholder)
                    else:
                        coords_list.append((x1, y1, x2, y2))
                        valid_count += 1
            print(f"SFD face boxes active. valid boxes: {valid_count}/{len(frames)}")
            return coords_list, frames

        def get_bbox_range(img_list: list[str], upperbondrange: int = 0) -> str:
            coords, _frames = get_landmark_and_bbox(img_list, upperbondrange)
            valid = [item for item in coords if item != coord_placeholder]
            return f"SFD face boxes active. valid boxes: {len(valid)}/{len(coords)}"

        module = types.ModuleType("musetalk.utils.preprocessing")
        module.read_imgs = read_imgs
        module.get_landmark_and_bbox = get_landmark_and_bbox
        module.get_bbox_range = get_bbox_range
        module.coord_placeholder = coord_placeholder
        sys.modules["musetalk.utils.preprocessing"] = module

    def _patch_torch_load(self, torch: Any) -> None:
        if getattr(torch.load, "_god_musetalk_patched", False):
            return
        original = torch.load

        def compat_load(*args: Any, **kwargs: Any) -> Any:
            if "weights_only" not in kwargs and env_bool("MUSETALK_TRUST_LOCAL_WEIGHTS", "true"):
                kwargs["weights_only"] = False
            return original(*args, **kwargs)

        compat_load._god_musetalk_patched = True  # type: ignore[attr-defined]
        torch.load = compat_load

    def _reset_peak_vram(self) -> None:
        if self._torch is not None and self._torch.cuda.is_available():
            self._torch.cuda.reset_peak_memory_stats(0)

    def _peak_vram_mb(self) -> int | None:
        if self._torch is None or not self._torch.cuda.is_available():
            return None
        return int(self._torch.cuda.max_memory_allocated(0) / (1024 * 1024))


renderer = MuseTalkRenderer()
app = FastAPI(title="GOD MuseTalk Embodiment Sidecar")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv(
            "MUSETALK_CORS_ORIGINS",
            "http://localhost:10517,http://127.0.0.1:10517,http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if origin.strip()
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    if env_bool("MUSETALK_LOAD_ON_START", "true"):
        renderer.start_loading()


@app.get("/health")
def health() -> dict[str, Any]:
    if env_bool("MUSETALK_LOAD_ON_HEALTH", "true") and not renderer.health()["model_loaded"]:
        renderer.start_loading()
    return renderer.health()


@app.post("/embody")
async def embody(
    request: Request,
    accept: str | None = Header(None),
) -> Response:
    payload = await request.json()
    blocking = bool(payload.get("blocking")) or "application/octet-stream" in str(accept or "")
    if blocking:
        try:
            output = renderer.render_payload(payload)
            state = renderer.job(*renderer._payload_ids(payload))
            headers = {}
            if state and state.latency_ms is not None:
                headers["X-Latency-Ms"] = str(state.latency_ms)
            if state and state.peak_vram_mb is not None:
                headers["X-Peak-Vram-Mb"] = str(state.peak_vram_mb)
            return FileResponse(output, media_type="video/mp4", headers=headers)
        except Exception as exc:
            return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)[:500]})

    try:
        state = renderer.start_job(payload)
        status_code = 200 if state.status == "complete" else 202
        return JSONResponse(
            status_code=status_code,
            content={"ok": True, "job": state.to_dict(), "stream_url": stream_url_for(state)},
        )
    except Exception as exc:
        return JSONResponse(status_code=400, content={"ok": False, "error": str(exc)[:500]})


@app.get("/jobs/{job_id:path}")
def job_status(job_id: str) -> JSONResponse:
    state = renderer._jobs.get(job_id)
    if not state:
        return JSONResponse(status_code=404, content={"ok": False, "error": "unknown_job"})
    return JSONResponse(content={"ok": True, "job": state.to_dict(), "stream_url": stream_url_for(state)})


@app.get("/stream/{soul_id}/{utterance_id:path}")
def stream(soul_id: str, utterance_id: str) -> Response:
    if utterance_id.endswith(".mp4"):
        utterance_id = utterance_id[:-4]
    output = renderer.wait_for_output(soul_id, utterance_id)
    if not output:
        state = renderer.job(soul_id, utterance_id)
        return JSONResponse(
            status_code=404,
            content={"ok": False, "error": "stream_not_ready", "job": state.to_dict() if state else None},
        )
    return FileResponse(
        output,
        media_type="video/mp4",
        headers={"Cache-Control": "no-store"},
    )


def stream_url_for(state: JobState) -> str:
    return f"/stream/{urllib.parse.quote(state.soul_id)}/{urllib.parse.quote(state.utterance_id)}.mp4"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.getenv("MUSETALK_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=env_int("MUSETALK_PORT", 7861))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port, log_level=os.getenv("LOG_LEVEL", "info").lower())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
