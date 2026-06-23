"""Async orchestrator for avatar genesis and registration."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


try:  # pragma: no cover - runtime package import path
    from ..owned_graph import OwnedGraph
except ImportError:  # pragma: no cover - flat test path
    from owned_graph import OwnedGraph

try:  # pragma: no cover - runtime package import path
    from .archetype_config import ARCHETYPE_CONFIGS, validate_archetype_configs
    from ..ipfs_client import pin_bytes, pin_json
    from .portrait_generator import PortraitGenerator
    from .voice_cloner import VoiceCloner
except ImportError:  # pragma: no cover - flat test path
    from avatar.archetype_config import ARCHETYPE_CONFIGS, validate_archetype_configs
    from ipfs_client import pin_bytes, pin_json
    from avatar.portrait_generator import PortraitGenerator
    from avatar.voice_cloner import VoiceCloner

log = logging.getLogger(__name__)


def _resolve_endpoint(*candidates: str | None) -> str:
    for candidate in candidates:
        value = str(candidate or "").strip().rstrip("/")
        if value:
            return value
    return ""


@dataclass
class PipelineResult:
    soul_id: str
    correlation_id: str
    status: str
    portrait_cid: str | None = None
    rigged_avatar_cid: str | None = None
    vrm_avatar_url: str | None = None
    expression_sheet_cid: str | None = None
    voice_embedding_cid: str | None = None
    assets_produced: int = 0
    duration_ms: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GenesisPipeline:
    """Coordinate portrait, expression, voice, and identity registration."""

    def __init__(
        self,
        *,
        comfyui_endpoint: str | None = None,
        tts_endpoint: str | None = None,
        pipeline_timeout_seconds: int | None = None,
        comfyui_concurrency: int | None = None,
        tts_concurrency: int | None = None,
    ) -> None:
        validate_archetype_configs()
        self.comfyui_endpoint = _resolve_endpoint(
            comfyui_endpoint,
            os.getenv("COMFYUI_ENDPOINT"),
            os.getenv("COMFYUI_HEALTH_URL"),
            os.getenv("COMFYUI_URL"),
            "http://localhost:8188",
            "http://comfyui:8188",
        )
        self.tts_endpoint = _resolve_endpoint(
            tts_endpoint,
            os.getenv("TTS_ENDPOINT"),
            os.getenv("VOICE_HEALTH_URL"),
            os.getenv("TTS_HEALTH_URL"),
            "http://localhost:7860",
            "http://fish-speech:7860",
        )
        self.pipeline_timeout_seconds = pipeline_timeout_seconds or int(
            os.getenv("PIPELINE_TIMEOUT_SECONDS", "300")
        )
        self.comfyui_concurrency = comfyui_concurrency or int(os.getenv("COMFYUI_CONCURRENCY", "2"))
        self.tts_concurrency = tts_concurrency or int(os.getenv("TTS_CONCURRENCY", "4"))
        self._comfyui_semaphore = asyncio.Semaphore(self.comfyui_concurrency)
        self._tts_semaphore = asyncio.Semaphore(self.tts_concurrency)
        self._status_registry: dict[str, PipelineResult] = {}
        self._started_at: dict[str, float] = {}

    def get_status(self, soul_id: str) -> PipelineResult | None:
        return self._status_registry.get(soul_id)

    async def execute(self, soul_id: str, archetype: str, graph: OwnedGraph) -> PipelineResult:
        correlation_id = uuid.uuid4().hex
        result = PipelineResult(soul_id=soul_id, correlation_id=correlation_id, status="running")
        self._status_registry[soul_id] = result
        self._started_at[soul_id] = time.time()
        start = time.perf_counter()
        self._log_event(
            "pipeline_start", soul_id=soul_id, archetype=archetype, correlation_id=correlation_id
        )

        try:
            completed = await asyncio.wait_for(
                self._execute_inner(
                    soul_id=soul_id,
                    archetype=archetype,
                    graph=graph,
                    result=result,
                    correlation_id=correlation_id,
                ),
                timeout=self.pipeline_timeout_seconds,
            )
            return completed
        except asyncio.TimeoutError:
            result.status = "failed" if result.assets_produced == 0 else "partial"
            result.errors.append({"step": "pipeline", "message": "timeout"})
            self._log_event(
                "pipeline_timeout",
                soul_id=soul_id,
                correlation_id=correlation_id,
                skipped_steps=self._skipped_steps(result),
            )
            return result
        except Exception as exc:
            result.status = "failed"
            result.errors.append({"step": "pipeline", "message": str(exc)})
            return result
        finally:
            result.duration_ms = int((time.perf_counter() - start) * 1000)
            self._status_registry[soul_id] = result
            self._log_event(
                "pipeline_summary",
                soul_id=soul_id,
                correlation_id=correlation_id,
                status=result.status,
                assets_produced=result.assets_produced,
                duration_ms=result.duration_ms,
                produced=self._produced_assets(result),
                skipped=self._skipped_steps(result),
            )

    async def _execute_inner(
        self,
        *,
        soul_id: str,
        archetype: str,
        graph: OwnedGraph,
        result: PipelineResult,
        correlation_id: str,
    ) -> PipelineResult:
        identity = graph.identity
        if identity is None:
            result.status = "failed"
            result.errors.append({"step": "identity", "message": "missing_identity"})
            return result
        style_config = ARCHETYPE_CONFIGS.get(archetype)
        if style_config is None:
            result.status = "failed"
            result.errors.append({"step": "config", "message": f"unknown archetype: {archetype}"})
            return result

        portrait_generator = PortraitGenerator(self.comfyui_endpoint, self._comfyui_semaphore)
        voice_cloner = VoiceCloner(self.tts_endpoint, self._tts_semaphore)

        portrait_bytes = None
        expression_bytes: dict[str, bytes] = {}
        voice_result = None

        if await portrait_generator.health_check():
            portrait_bytes = await portrait_generator.generate_portrait(archetype, style_config)
            if portrait_bytes:
                portrait_pin = await pin_bytes(portrait_bytes, filename=f"{soul_id}-portrait.png")
                if not portrait_pin.ok:
                    self._record_failure(result, "portrait", "ipfs_pin_failed")
                    self._log_step(
                        correlation_id,
                        soul_id,
                        "portrait",
                        False,
                        {"pin_errors": portrait_pin.errors},
                    )
                    portrait_pin = None
                if portrait_pin:
                    identity.avatar_cid = portrait_pin.cid
                    identity.rigged_avatar_cid = portrait_pin.cid
                    result.portrait_cid = portrait_pin.cid
                    result.rigged_avatar_cid = portrait_pin.cid
                    result.assets_produced += 1
                    self._log_step(
                        correlation_id,
                        soul_id,
                        "portrait",
                        True,
                        {"bytes": len(portrait_bytes), "cid": portrait_pin.cid},
                    )
                if result.portrait_cid and not identity.avatar_base_cid:
                    identity.avatar_base_cid = identity.avatar_cid
                identity.avatar_style_prompt = style_config.style_prompt_template
                expression_bytes = await portrait_generator.generate_expressions(
                    portrait_bytes,
                    ["neutral", "angry", "playful", "calm", "intense", "vulnerable", "flinch"],
                    archetype_prompt=style_config.style_prompt_template,
                )
                if expression_bytes:
                    pinned_expressions: dict[str, str] = {}
                    for expression_name, expression_data in expression_bytes.items():
                        pin_result = await pin_bytes(
                            expression_data,
                            filename=f"{soul_id}-{expression_name}.png",
                        )
                        if pin_result.ok:
                            pinned_expressions[expression_name] = pin_result.cid
                    if pinned_expressions:
                        identity.mood_mapping = pinned_expressions
                        manifest_pin = await pin_json(
                            json.dumps(
                                {
                                    "soul_id": soul_id,
                                    "archetype": archetype,
                                    "expressions": pinned_expressions,
                                },
                                sort_keys=True,
                            ).encode("utf-8"),
                            filename=f"{soul_id}-expressions.json",
                        )
                        if manifest_pin.ok:
                            result.expression_sheet_cid = manifest_pin.cid
                            result.assets_produced += 1
                        else:
                            self._record_failure(
                                result, "expression_sheet", "ipfs_manifest_pin_failed"
                            )
                    else:
                        self._record_failure(result, "expression_sheet", "ipfs_pin_failed")
                    self._log_step(
                        correlation_id,
                        soul_id,
                        "expression_sheet",
                        bool(result.expression_sheet_cid),
                        {"count": len(pinned_expressions), "cid": result.expression_sheet_cid},
                    )
            else:
                self._record_failure(result, "portrait", "generation_failed")
                self._log_step(correlation_id, soul_id, "portrait", False, {})
        else:
            self._record_failure(result, "portrait", "service_unavailable")
            self._log_step(correlation_id, soul_id, "portrait", False, {"skipped": True})

        if await voice_cloner.health_check():
            voice_result = await voice_cloner.clone_voice(
                style_config.seed_utterance_path, archetype
            )
            if voice_result:
                voice_pin = await pin_bytes(
                    voice_result.embedding_bytes, filename=f"{soul_id}-voice.bin"
                )
                if voice_pin.ok:
                    identity.voice_model_cid = voice_pin.cid
                    identity.voice_params = voice_result.voice_params
                    result.voice_embedding_cid = voice_pin.cid
                    result.assets_produced += 1
                else:
                    self._record_failure(result, "voice_embedding", "ipfs_pin_failed")
                self._log_step(
                    correlation_id,
                    soul_id,
                    "voice_embedding",
                    bool(result.voice_embedding_cid),
                    {"bytes": len(voice_result.embedding_bytes), "cid": result.voice_embedding_cid},
                )
            else:
                self._record_failure(result, "voice_embedding", "generation_failed")
                self._log_step(correlation_id, soul_id, "voice_embedding", False, {})
        else:
            self._record_failure(result, "voice_embedding", "service_unavailable")
            self._log_step(correlation_id, soul_id, "voice_embedding", False, {"skipped": True})

        if result.assets_produced > 0:
            await self._persist_identity(graph, soul_id, result, correlation_id)

        result.status = (
            "complete"
            if result.errors == []
            else "partial"
            if result.assets_produced > 0
            else "failed"
        )
        return result

    async def _persist_identity(
        self,
        graph: OwnedGraph,
        soul_id: str,
        result: PipelineResult,
        correlation_id: str,
    ) -> None:
        attempts = 0
        last_error = None
        while attempts < 3:
            attempts += 1
            try:
                graph_cid = await asyncio.to_thread(graph.pin_to_ipfs)
                self._update_postgres_graph_cid(
                    soul_id,
                    graph_cid,
                    avatar_cid=result.portrait_cid or "",
                    rigged_avatar_cid=result.rigged_avatar_cid or result.portrait_cid or "",
                    vrm_avatar_url=result.vrm_avatar_url or "",
                    voice_model_cid=result.voice_embedding_cid or "",
                )
                self._log_step(
                    correlation_id, soul_id, "identity_registration", True, {"graph_cid": graph_cid}
                )
                return
            except Exception as exc:
                last_error = exc
                await asyncio.sleep(min(8, 2**attempts))
        result.errors.append(
            {
                "step": "identity_registration",
                "message": str(last_error) if last_error else "pin_failed",
            }
        )
        self._log_step(
            correlation_id,
            soul_id,
            "identity_registration",
            False,
            {"error": str(last_error) if last_error else "pin_failed"},
        )

    def _update_postgres_graph_cid(
        self,
        soul_id: str,
        graph_cid: str,
        avatar_cid: str = "",
        rigged_avatar_cid: str = "",
        vrm_avatar_url: str = "",
        voice_model_cid: str = "",
    ) -> None:
        database_url = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
        try:
            import psycopg2

            with psycopg2.connect(database_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """UPDATE agents
                           SET graph_cid = %s,
                               avatar_cid = CASE WHEN %s != '' THEN %s ELSE avatar_cid END,
                               rigged_avatar_cid = CASE WHEN %s != '' THEN %s ELSE rigged_avatar_cid END,
                               vrm_avatar_url = CASE WHEN %s != '' THEN %s ELSE vrm_avatar_url END,
                               voice_model_cid = CASE WHEN %s != '' THEN %s ELSE voice_model_cid END
                           WHERE soul_id = %s""",
                        (
                            graph_cid,
                            avatar_cid,
                            avatar_cid,
                            rigged_avatar_cid,
                            rigged_avatar_cid,
                            vrm_avatar_url,
                            vrm_avatar_url,
                            voice_model_cid,
                            voice_model_cid,
                            soul_id,
                        ),
                    )
                conn.commit()
                if cur.rowcount != 1:
                    log.warning(
                        "postgres_update_rowcount soul_id=%s rowcount=%s",
                        soul_id,
                        cur.rowcount,
                    )
        except Exception as exc:
            log.warning("postgres_update_failed soul_id=%s error=%s", soul_id, exc)

    def _record_failure(self, result: PipelineResult, step: str, message: str) -> None:
        result.errors.append({"step": step, "message": message})

    def _log_event(self, event: str, **payload: Any) -> None:
        log.info(json.dumps({"event": event, **payload}, sort_keys=True))

    def _log_step(
        self, correlation_id: str, soul_id: str, step: str, success: bool, payload: dict[str, Any]
    ) -> None:
        log.info(
            json.dumps(
                {
                    "event": "pipeline_step",
                    "correlation_id": correlation_id,
                    "soul_id": soul_id,
                    "step": step,
                    "success": success,
                    **payload,
                },
                sort_keys=True,
            )
        )

    def _produced_assets(self, result: PipelineResult) -> list[str]:
        assets = []
        if result.portrait_cid:
            assets.append("portrait")
        if result.rigged_avatar_cid:
            assets.append("rigged_avatar")
        if result.expression_sheet_cid:
            assets.append("expression_sheet")
        if result.voice_embedding_cid:
            assets.append("voice_embedding")
        return assets

    def _skipped_steps(self, result: PipelineResult) -> list[str]:
        skipped = []
        if not result.portrait_cid:
            skipped.append("portrait")
        if not result.rigged_avatar_cid:
            skipped.append("rigged_avatar")
        if not result.expression_sheet_cid:
            skipped.append("expression_sheet")
        if not result.voice_embedding_cid:
            skipped.append("voice_embedding")
        return skipped
