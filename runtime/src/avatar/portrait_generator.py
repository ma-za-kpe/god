"""ComfyUI portrait and expression generation helpers."""

from __future__ import annotations

import asyncio
import base64
import json
import os
from pathlib import Path
from typing import Any

import httpx

try:  # pragma: no cover - optional dependency
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

try:  # pragma: no cover - runtime package import path
    from .archetype_config import ArchetypeStyleConfig
except ImportError:  # pragma: no cover - flat test path
    from avatar.archetype_config import ArchetypeStyleConfig


class PortraitGenerator:
    """Submit Flux/IP-Adapter workflows to ComfyUI."""

    def __init__(self, comfyui_endpoint: str | None, semaphore: asyncio.Semaphore | None = None, timeout_s: int = 60) -> None:
        self.comfyui_endpoint = (comfyui_endpoint or "").rstrip("/")
        self.semaphore = semaphore or asyncio.Semaphore(int(os.getenv("COMFYUI_CONCURRENCY", "2")))
        self.timeout_s = timeout_s

    async def health_check(self) -> bool:
        if not self.comfyui_endpoint:
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.comfyui_endpoint)
                return 200 <= response.status_code < 300
        except Exception:
            return False

    async def generate_portrait(
        self,
        archetype: str,
        style_config: ArchetypeStyleConfig,
        *,
        seed: int | None = None,
        width: int = 1024,
        height: int = 1024,
    ) -> bytes | None:
        if not self.comfyui_endpoint:
            return None
        if not await self.health_check():
            return None
        payload = self._build_workflow_payload(
            template_name="flux_portrait.json",
            replacements={
                "{{STYLE_PROMPT}}": style_config.style_prompt_template,
                "{{NEGATIVE_PROMPT}}": "blurry, low-resolution, malformed, text, watermark",
                "{{SEED}}": seed if seed is not None else self._stable_seed(archetype),
                "{{WIDTH}}": max(512, int(width)),
                "{{HEIGHT}}": max(512, int(height)),
                "{{BATCH_SIZE}}": 1,
            },
        )
        result = await self._submit_workflow(payload)
        return self._extract_image_bytes(result)

    async def generate_expressions(
        self,
        portrait_ref: bytes,
        expressions: list[str],
        *,
        archetype_prompt: str,
        seed: int | None = None,
        width: int = 1024,
        height: int = 1024,
    ) -> dict[str, bytes]:
        outputs: dict[str, bytes] = {}
        if not self.comfyui_endpoint or not await self.health_check():
            return outputs
        for index, expression in enumerate(expressions):
            payload = self._build_workflow_payload(
                template_name="flux_expression.json",
                replacements={
                    "{{EXPRESSION_PROMPT}}": f"{archetype_prompt}, {expression} expression",
                    "{{NEGATIVE_PROMPT}}": "blurry, low-resolution, malformed, text, watermark",
                    "{{SEED}}": (seed if seed is not None else self._stable_seed(expression)) + index,
                    "{{WIDTH}}": max(512, int(width)),
                    "{{HEIGHT}}": max(512, int(height)),
                    "{{REFERENCE_IMAGE_PATH}}": self._inline_image_reference(portrait_ref),
                    "{{IP_ADAPTER_WEIGHT}}": 0.85,
                    "{{EXPRESSION_NAME}}": expression,
                },
            )
            try:
                result = await self._submit_workflow(payload)
                image_bytes = self._extract_image_bytes(result)
                if image_bytes:
                    outputs[expression] = image_bytes
            except Exception:
                continue
        return outputs

    async def _submit_workflow(self, payload: dict[str, Any]) -> dict[str, Any] | bytes | None:
        async with self.semaphore:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                response = await client.post(f"{self.comfyui_endpoint}/prompt", json=payload)
                response.raise_for_status()
                if response.headers.get("content-type", "").startswith("application/json"):
                    try:
                        return response.json()
                    except Exception:
                        return {"raw": response.text}
                return response.content

    def _build_workflow_payload(self, *, template_name: str, replacements: dict[str, Any]) -> dict[str, Any]:
        template = self._load_workflow_template(template_name)
        return self._replace_tokens(template, replacements)

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

    def _stable_seed(self, text: str) -> int:
        return abs(hash(text)) % 2_147_483_647

    def _inline_image_reference(self, portrait_ref: bytes) -> str:
        return f"data:image/png;base64,{base64.b64encode(portrait_ref).decode('ascii')}"

    def _extract_image_bytes(self, result: dict[str, Any] | bytes | None) -> bytes | None:
        if result is None:
            return None
        if isinstance(result, bytes):
            return result if self.validate_image_bytes(result) else None
        for key in ("image_bytes", "image", "output_bytes"):
            value = result.get(key)
            if isinstance(value, bytes) and self.validate_image_bytes(value):
                return value
        if "images" in result and isinstance(result["images"], list):
            for item in result["images"]:
                if isinstance(item, bytes) and self.validate_image_bytes(item):
                    return item
        return None

    def validate_image_bytes(self, payload: bytes) -> bool:
        if not payload or len(payload) < 1024:
            return False
        if Image is None:
            return payload.startswith(b"\x89PNG") or payload.startswith(b"\xff\xd8")
        try:
            with Image.open(__import__("io").BytesIO(payload)) as image:
                image.load()
                return image.format in {"PNG", "JPEG"} and image.width >= 512 and image.height >= 512
        except Exception:
            return False
