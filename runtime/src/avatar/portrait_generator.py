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

    def __init__(
        self,
        comfyui_endpoint: str | None,
        semaphore: asyncio.Semaphore | None = None,
        timeout_s: int = 60,
    ) -> None:
        self.comfyui_endpoint = (comfyui_endpoint or "").rstrip("/")
        self.semaphore = semaphore or asyncio.Semaphore(int(os.getenv("COMFYUI_CONCURRENCY", "2")))
        self.timeout_s = timeout_s
        self.portrait_template = os.getenv("COMFYUI_PORTRAIT_TEMPLATE", "flux_portrait.json")
        self.expression_template = os.getenv("COMFYUI_EXPRESSION_TEMPLATE", "flux_expression.json")

    async def health_check(self) -> bool:
        if not self.comfyui_endpoint:
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
                response = await client.get(f"{self.comfyui_endpoint}/system_stats")
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
            template_name=self.portrait_template,
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
                template_name=self.expression_template,
                replacements={
                    "{{EXPRESSION_PROMPT}}": f"{archetype_prompt}, {expression} expression",
                    "{{NEGATIVE_PROMPT}}": "blurry, low-resolution, malformed, text, watermark",
                    "{{SEED}}": (seed if seed is not None else self._stable_seed(expression))
                    + index,
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

    async def _submit_workflow(self, payload: dict[str, Any]) -> bytes | None:
        # Strip metadata key before sending; wrap in ComfyUI's expected envelope
        workflow = {k: v for k, v in payload.items() if k != "_meta"}
        async with self.semaphore:
            async with httpx.AsyncClient(timeout=self.timeout_s, follow_redirects=True) as client:
                response = await client.post(
                    f"{self.comfyui_endpoint}/prompt",
                    json={"prompt": workflow},
                )
                if response.status_code >= 400:
                    return None
                content_type = response.headers.get("content-type", "")
                if "json" not in content_type:
                    return None
                try:
                    data = response.json()
                except Exception:
                    return None
                prompt_id = data.get("prompt_id")
                if not prompt_id:
                    return None
                deadline = asyncio.get_running_loop().time() + self.timeout_s
                while asyncio.get_running_loop().time() < deadline:
                    await asyncio.sleep(2)
                    hist = await client.get(f"{self.comfyui_endpoint}/history/{prompt_id}")
                    if hist.status_code != 200:
                        continue
                    entry = hist.json().get(prompt_id)
                    if entry is None:
                        continue
                    return await self._fetch_comfyui_image(client, entry)
        return None

    async def _fetch_comfyui_image(
        self, client: httpx.AsyncClient, history_entry: dict[str, Any]
    ) -> bytes | None:
        for output in history_entry.get("outputs", {}).values():
            for img in output.get("images", []):
                filename = img.get("filename")
                if not filename:
                    continue
                resp = await client.get(
                    f"{self.comfyui_endpoint}/view",
                    params={
                        "filename": filename,
                        "subfolder": img.get("subfolder", ""),
                        "type": img.get("type", "output"),
                    },
                )
                if resp.status_code == 200:
                    return resp.content
        return None

    def _build_workflow_payload(
        self, *, template_name: str, replacements: dict[str, Any]
    ) -> dict[str, Any]:
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

    def _extract_image_bytes(self, result: bytes | None) -> bytes | None:
        if not isinstance(result, bytes):
            return None
        return result if self.validate_image_bytes(result) else None

    def validate_image_bytes(self, payload: bytes) -> bool:
        if not payload or len(payload) < 1024:
            return False
        if Image is None:
            return payload.startswith(b"\x89PNG") or payload.startswith(b"\xff\xd8")
        try:
            with Image.open(__import__("io").BytesIO(payload)) as image:
                image.load()
                return (
                    image.format in {"PNG", "JPEG"} and image.width >= 512 and image.height >= 512
                )
        except Exception:
            return False
