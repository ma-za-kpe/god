"""Fish Speech voice cloning helpers (fish-speech 2.0 / s2-pro)."""

from __future__ import annotations

import asyncio
import base64
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

try:  # pragma: no cover - runtime package import path
    from .archetype_config import ARCHETYPE_CONFIGS, ArchetypeStyleConfig
except ImportError:  # pragma: no cover - flat test path
    from avatar.archetype_config import ARCHETYPE_CONFIGS, ArchetypeStyleConfig


@dataclass(frozen=True)
class VoiceCloneResult:
    embedding_bytes: bytes
    voice_params: dict[str, Any]
    verification_sample: bytes


class VoiceCloner:
    """Submit zero-shot cloning requests to the TTS service."""

    def __init__(
        self,
        tts_endpoint: str | None,
        semaphore: asyncio.Semaphore | None = None,
        timeout_s: int = 60,
    ) -> None:
        self.tts_endpoint = (tts_endpoint or "").rstrip("/")
        self.semaphore = semaphore or asyncio.Semaphore(int(os.getenv("TTS_CONCURRENCY", "4")))
        self.timeout_s = timeout_s

    async def health_check(self) -> bool:
        if not self.tts_endpoint:
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.tts_endpoint}/v1/health")
                if not 200 <= response.status_code < 300:
                    return False
                try:
                    return response.json().get("status") == "ok"
                except Exception:
                    return True
        except Exception:
            return False

    async def clone_voice(
        self,
        seed_utterance_path: str,
        archetype: str,
    ) -> VoiceCloneResult | None:
        if not self.tts_endpoint:
            return None
        if not await self.health_check():
            return None
        style_config = ARCHETYPE_CONFIGS.get(archetype)
        if style_config is None:
            return None
        utterance = self._read_seed_utterance(seed_utterance_path)
        if utterance is None:
            return None
        embedding = await self._submit_clone(utterance, archetype)
        if not embedding:
            return None
        voice_params = self._derive_voice_params(style_config)
        verification_sample = await self._submit_verification_sample(embedding, voice_params)
        if not verification_sample:
            return None
        return VoiceCloneResult(
            embedding_bytes=embedding,
            voice_params=voice_params,
            verification_sample=verification_sample,
        )

    async def detect_prosody_support(self) -> bool:
        if not self.tts_endpoint:
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.tts_endpoint}/capabilities")
                if not 200 <= response.status_code < 300:
                    return False
                payload = response.json()
                return bool(
                    payload.get("prosody_tags")
                    or payload.get("supports_prosody_tags")
                    or payload.get("prosody")
                )
        except Exception:
            return False

    def _derive_voice_params(self, style_config: ArchetypeStyleConfig) -> dict[str, Any]:
        return {
            "timbre": style_config.voice_timbre,
            "pitch": {
                "min_hz": style_config.voice_pitch_range[0],
                "max_hz": style_config.voice_pitch_range[1],
            },
            "speed": style_config.voice_cadence_wpm,
            "prosody_map": dict(style_config.prosody_map),
        }

    async def _submit_clone(self, seed_utterance: bytes, archetype: str) -> bytes | None:
        # fish-speech 2.0 has no persistent embedding step; reference audio is
        # passed inline with each /v1/tts call. We do a test synthesis to confirm
        # the service accepts the voice, then return the seed WAV itself as the
        # "embedding" so _submit_verification_sample can use it as reference.
        async with self.semaphore:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                payload = {
                    "text": f"I am the {archetype}. I emerge from the void.",
                    "references": [
                        {"audio": base64.b64encode(seed_utterance).decode(), "text": ""},
                    ],
                    "format": "wav",
                    "streaming": False,
                }
                response = await client.post(f"{self.tts_endpoint}/v1/tts", json=payload)
                if not 200 <= response.status_code < 300:
                    return None
                # The seed WAV itself is the voice identity for future /v1/tts calls.
                return seed_utterance

    async def _submit_verification_sample(
        self,
        embedding: bytes,
        voice_params: dict[str, Any],
    ) -> bytes | None:
        # embedding here is the seed WAV returned by _submit_clone.
        async with self.semaphore:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                payload = {
                    "text": "The world tests those who dare to persist. I endure.",
                    "references": [
                        {"audio": base64.b64encode(embedding).decode(), "text": ""},
                    ],
                    "format": "wav",
                    "streaming": False,
                }
                response = await client.post(f"{self.tts_endpoint}/v1/tts", json=payload)
                if not 200 <= response.status_code < 300:
                    return None
                return response.content or None

    def _read_seed_utterance(self, path: str) -> bytes | None:
        if not path:
            return None
        # archetype_config paths are like "runtime/seed_utterances/trader.wav".
        # parents[2] = runtime/, parents[3] = project root.
        # "project_root / path" resolves correctly regardless of CWD.
        candidates = [
            Path(path),
            Path(__file__).resolve().parents[3] / path,
            Path(__file__).resolve().parents[2] / path,
            Path(__file__).resolve().parents[3] / "runtime" / path,
            Path.cwd() / path,
        ]
        utterance_path = next((candidate for candidate in candidates if candidate.is_file()), None)
        if utterance_path is None:
            return None
        data = utterance_path.read_bytes()
        return data or None
