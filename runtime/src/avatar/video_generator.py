"""ComfyUI video generation client skeleton."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx


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

    async def submit_workflow(self, workflow_template: dict[str, Any], replacements: dict[str, Any]) -> bytes | None:
        if not self.endpoint:
            return None
        workflow = self._replace_tokens(workflow_template, replacements)
        workflow = {key: value for key, value in workflow.items() if key != "_meta"}

        async with httpx.AsyncClient(timeout=self.timeout_s, follow_redirects=True) as client:
            response = await client.post(f"{self.endpoint}/prompt", json={"prompt": workflow})
            if response.status_code >= 400:
                return None
            data = response.json()
            prompt_id = data.get("prompt_id")
            if not prompt_id:
                return None
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

    async def _poll_for_video(self, client: httpx.AsyncClient, prompt_id: str) -> bytes | None:
        deadline = asyncio.get_running_loop().time() + self.timeout_s
        while asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(2)
            history = await client.get(f"{self.endpoint}/history/{prompt_id}")
            if history.status_code != 200:
                continue
            entry = history.json().get(prompt_id)
            if not entry:
                continue
            return await self._fetch_video_output(client, entry)
        return None

    async def _fetch_video_output(
        self, client: httpx.AsyncClient, history_entry: dict[str, Any]
    ) -> bytes | None:
        for output in history_entry.get("outputs", {}).values():
            for item in output.get("gifs", []) + output.get("videos", []) + output.get("images", []):
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
                    return response.content
        return None

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
