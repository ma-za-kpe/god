"""Voice planning surface for TTS and lip-sync wiring."""

from __future__ import annotations

import hashlib
import base64
import logging
import os
import re
import threading
import time
from typing import Any
from pathlib import Path

import httpx

_log = logging.getLogger(__name__)

_UUID_PREFIX_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}:\s*", re.IGNORECASE
)
_EMOJI_RE = re.compile(r"[\U00002600-\U000027BF\U0001F300-\U0001FAFF☀-⛿✀-➿✅❌⚠️🔥💀]+")
# "Name → Recipient: 'message'" — extract just the quoted message content
_ARROW_NARRATIVE_RE = re.compile(r"^.+→.+?:\s*['\"]?", re.DOTALL)
# "shortid sends a TYPE to shortid: 'message'" — messaging.py truncated-UUID narrative
_SEND_NARRATIVE_RE = re.compile(
    r"^[^\s]+\s+sends?\s+(?:a\s+)?\w+\s+to\s+[^\s:]+:\s*['\"]?", re.IGNORECASE
)
# "Name (archetype, gen N): thought" — extract just the thought
_AGENT_PREFIX_RE = re.compile(r"^[A-Za-z]+-[A-Za-z0-9]+-[A-Za-z0-9]+\s*\([^)]+\):\s*")
# "Name action..." — strip bare leading agent name (e.g. "Elder-Hook-6A4A pays rent")
_AGENT_BARE_NAME_RE = re.compile(r"^[A-Za-z]+-[A-Za-z0-9]+-[A-Za-z0-9]+\s+")

try:  # pragma: no cover - runtime package import path
    from ..health_checks import probe_url
    from ..runtime_endpoints import ollama_base_url, tts_base_url, tts_health_url
except ImportError:  # pragma: no cover - flat test path
    from health_checks import probe_url
    from runtime_endpoints import ollama_base_url, tts_base_url, tts_health_url
try:  # pragma: no cover - runtime package import path
    from ..avatar.archetype_config import ARCHETYPE_CONFIGS
except ImportError:  # pragma: no cover - flat test path
    from avatar.archetype_config import ARCHETYPE_CONFIGS
from .audio_features import analyze_audio_bytes, procedural_mouth_amplitude  # noqa: E402
from .state import VoicePlan, VoiceState  # noqa: E402


def _env_float(name: str, default: str) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return float(default)


class _CachedHealthProbe:
    """TTL-based cached health probe that avoids blocking compose() on network I/O.

    Returns a cached result if within TTL (default 5s). When the cache expires
    or there's no cached result yet, it spawns a background probe and waits up
    to a short deadline (150ms) for a result. If the probe doesn't complete in
    time, returns the stale/default result immediately, ensuring compose() never
    blocks on slow network I/O.
    """

    _INITIAL_WAIT: float = 0.15  # max 150ms wait on first probe

    def __init__(self, ttl: float = 5.0):
        self._ttl = ttl
        self._lock = threading.Lock()
        self._cached_result: dict[str, Any] = {
            "ok": False,
            "probe": "skipped",
            "reason": "not_yet_probed",
        }
        self._last_probe_time: float = 0.0
        self._last_success_time: float = 0.0
        self._failure_grace_seconds = max(
            0.0,
            _env_float("VOICE_HEALTH_FAILURE_GRACE_SECONDS", "30"),
        )
        self._probe_in_flight: bool = False
        self._initialized: bool = False

    def get(self, url: str | None, timeout: float = 1.5) -> dict[str, Any]:
        """Return cached health probe result, refreshing in the background if stale."""
        now = time.monotonic()
        with self._lock:
            if self._initialized:
                age = now - self._last_probe_time
                if age < self._ttl:
                    # Cache is fresh — return immediately
                    return self._cached_result
            # Cache is stale or uninitialized — trigger background refresh
            need_initial_wait = not self._initialized
            if not self._probe_in_flight:
                self._probe_in_flight = True
                thread = threading.Thread(target=self._refresh, args=(url, timeout), daemon=True)
                thread.start()
            else:
                thread = None

        # On first call, briefly wait for the background thread to return a result.
        # This gives fast probes (<150ms) a chance to populate the cache on the
        # first compose() call, supporting deterministic behavior under normal latency.
        if need_initial_wait and thread is not None:
            thread.join(timeout=self._INITIAL_WAIT)

        with self._lock:
            return self._cached_result

    def _refresh(self, url: str | None, timeout: float) -> None:
        """Run probe with retry in background thread and update the cache."""
        try:
            result = _probe_with_retry(url, timeout=timeout)
            now = time.monotonic()
            with self._lock:
                if result.get("ok"):
                    self._cached_result = result
                    self._last_success_time = now
                elif (
                    self._cached_result.get("ok")
                    and self._last_success_time > 0.0
                    and (now - self._last_success_time) <= self._failure_grace_seconds
                ):
                    stale_result = dict(self._cached_result)
                    stale_result["stale_after_failure"] = True
                    stale_result["last_failure"] = {
                        key: result.get(key)
                        for key in ("reason", "status_code", "error", "url")
                        if result.get(key) is not None
                    }
                    stale_result["last_failure_age_seconds"] = round(
                        now - self._last_success_time,
                        3,
                    )
                    self._cached_result = stale_result
                else:
                    self._cached_result = result
                self._last_probe_time = now
                self._initialized = True
        except Exception:
            # On unexpected error, keep stale cache and allow next cycle to retry
            pass
        finally:
            with self._lock:
                self._probe_in_flight = False


def _probe_with_retry(
    url: str | None, timeout: float = 1.5, max_retries: int = 1
) -> dict[str, Any]:
    """Probe a URL with retry logic before marking unhealthy.

    On first failure, waits briefly and retries up to *max_retries* times.
    If a retry succeeds (ok=True), returns the successful result immediately (auto-recovery).
    If all retries fail, returns the final failed result.

    The backoff is kept short (~50ms) because this runs inside the background
    health-probe thread. The cached-probe layer already provides tolerance for
    transient failures across compose() calls (TTL ~5s).
    """
    result = probe_url(url, timeout=timeout)
    if result.get("ok"):
        return result

    for attempt in range(max_retries):
        time.sleep(0.05)  # brief backoff before retry
        result = probe_url(url, timeout=timeout)
        if result.get("ok"):
            _log.info("Health probe recovered on retry %d for %s", attempt + 1, url)
            return result

    return result


def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")


def _pick_emotion(snapshot: dict[str, Any]) -> str:
    showrunner = snapshot.get("showrunner") or {}
    audience = snapshot.get("audience") or {}
    broadcast = snapshot.get("broadcast") or {}
    scene = str(
        showrunner.get("scene") or broadcast.get("scene", {}).get("scene_name") or ""
    ).lower()
    pressure = float(audience.get("patronage_index") or 0)
    if pressure >= 20:
        return "charged"
    if (
        "banter" in scene
        or "chat" in scene
        or "ensemble" in scene
        or "stage" in scene
        or "avatar" in scene
    ):
        return "playful"
    if "economy" in scene or "market" in scene:
        return "measured"
    if "void" in scene or "silence" in scene:
        return "hushed"
    return "focused"


def _pick_voice_name() -> str:
    return (
        os.getenv("VOICE_NAME") or os.getenv("TTS_VOICE") or os.getenv("KOKORO_VOICE") or "narrator"
    )


def _pick_voice_model() -> str:
    return (
        os.getenv("TTS_MODEL") or os.getenv("VOICE_MODEL") or os.getenv("KOKORO_MODEL") or "kokoro"
    )


def _voice_synthesis_enabled() -> bool:
    """Treat live TTS as the default when a backend is configured.

    The branch's env template already documents VOICE_SYNTHESIS_ENABLED=true.
    If the operator explicitly sets the env var, respect it. Otherwise, enable
    synthesis whenever a TTS endpoint is present so the stage can speak by
    default in healthy environments.
    """
    raw = os.getenv("VOICE_SYNTHESIS_ENABLED")
    if raw is not None:
        return _env_bool("VOICE_SYNTHESIS_ENABLED", "true")
    return bool(tts_base_url())


def _dialogue_speed(snapshot: dict[str, Any], line: str) -> float:
    last_turn = snapshot.get("last_dialogue_turn") or {}
    meta = last_turn.get("metadata") or {}
    if isinstance(meta, str):
        try:
            import json as _json

            meta = _json.loads(meta)
        except Exception:
            meta = {}
    cadence = str(
        last_turn.get("cadence")
        or meta.get("cadence")
        or last_turn.get("beat_count")
        or meta.get("beat_count")
        or ""
    ).lower()
    body = str(line or "")
    if cadence == "jab":
        return 1.08
    if cadence == "short":
        return 1.03
    if cadence == "callback":
        return 0.95
    if cadence == "build":
        return 0.90
    if len(body) > 180:
        return 0.92
    return 1.0


def _utterance_id(snapshot: dict[str, Any], speaker: str, line: str) -> str:
    scene = str((snapshot.get("showrunner") or {}).get("scene") or "")
    payload = f"{scene}|{speaker}|{line}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _turn_age_seconds(snapshot: dict[str, Any], turn: dict[str, Any]) -> float | None:
    if not turn:
        return None
    try:
        epoch = int(snapshot.get("epoch") or 0)
        sent_at = int(turn.get("sent_at") or turn.get("timestamp") or 0)
    except Exception:
        return None
    if not epoch or not sent_at:
        return None
    return max(0.0, float(epoch - sent_at))


def _pick_move(snapshot: dict[str, Any]) -> str:
    last_turn = snapshot.get("last_dialogue_turn") or {}
    meta = last_turn.get("metadata") or {}
    if isinstance(meta, str):
        try:
            import json as _json

            meta = _json.loads(meta)
        except Exception:
            meta = {}
    if not isinstance(meta, dict):
        meta = {}
    return str(
        last_turn.get("move")
        or last_turn.get("move_type")
        or meta.get("move")
        or snapshot.get("current_move")
        or ""
    ).upper()


def _voice_agent(snapshot: dict[str, Any], speaker: str) -> dict[str, Any] | None:
    agents = snapshot.get("agents") or []
    for agent in agents:
        if not isinstance(agent, dict):
            continue
        current_name = str(agent.get("current_name") or "")
        soul_id = str(agent.get("soul_id") or "")
        if current_name.lower() == speaker.lower() or soul_id.lower() == speaker.lower():
            return agent
    return None


def _reference_diagnostics(
    *,
    cid: str = "",
    source: str = "none",
    ok: bool = False,
    fallback_used: bool = False,
    failure_reason: str = "",
    path_name: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": ok,
        "source": source,
        "fallback_used": fallback_used,
        "semantics": "reference_wav",
        "legacy_field": "voice_model_cid",
    }
    if cid:
        payload["cid"] = cid
    if failure_reason:
        payload["failure_reason"] = failure_reason
    if path_name:
        payload["path_name"] = path_name
    return payload


def _reference_candidates(ref_path: str) -> list[Path]:
    return [
        Path(ref_path),
        Path.cwd() / ref_path,
        Path(__file__).resolve().parents[3] / ref_path,
        Path(__file__).resolve().parents[2] / ref_path,
    ]


def _read_reference_path(ref_path: str) -> tuple[bytes | None, str]:
    if not ref_path:
        return None, ""
    for candidate in _reference_candidates(ref_path):
        try:
            resolved = candidate.resolve()
        except Exception:
            continue
        if resolved.is_file():
            try:
                return resolved.read_bytes() or None, resolved.name
            except Exception as exc:
                _log.warning("voice reference file unavailable: %s", exc)
                return None, resolved.name
    return None, Path(ref_path).name


def _philosopher_reference_paths() -> tuple[Path, ...]:
    return (
        Path(__file__).resolve().parents[2] / "seed_utterances/philosopher.wav",
        Path(__file__).resolve().parents[3] / "runtime/seed_utterances/philosopher.wav",
    )


def _read_philosopher_reference() -> tuple[bytes | None, str]:
    for candidate in _philosopher_reference_paths():
        try:
            if candidate.is_file():
                return candidate.read_bytes() or None, candidate.name
        except Exception as exc:
            _log.warning("philosopher voice reference unavailable: %s", exc)
    return None, "philosopher.wav"


def _resolve_reference_audio(agent: dict[str, Any] | None) -> tuple[bytes | None, dict[str, Any]]:
    """Resolve Fish reference WAV bytes and explain every fallback."""
    cid = str((agent or {}).get("voice_model_cid") or "").strip()
    failure_reason = ""

    if cid:
        ipfs_api = (os.getenv("IPFS_API") or "http://localhost:5001").rstrip("/")
        try:
            response = httpx.post(
                f"{ipfs_api}/api/v0/cat",
                params={"arg": cid},
                timeout=10.0,
            )
            if response.status_code == 405:
                response = httpx.get(f"{ipfs_api}/api/v0/cat", params={"arg": cid}, timeout=10.0)
            if 200 <= response.status_code < 300 and response.content:
                return response.content, _reference_diagnostics(
                    cid=cid,
                    source="voice_model_cid",
                    ok=True,
                )
            failure_reason = f"cid_fetch_status:{response.status_code}"
            _log.warning(
                "voice reference fetch failed: cid=%s status=%s",
                cid,
                response.status_code,
            )
        except Exception as exc:
            failure_reason = f"cid_fetch_exception:{type(exc).__name__}"
            _log.warning("voice reference fetch failed: %s", exc)

    archetype = str((agent or {}).get("archetype") or "").strip()
    style_config = ARCHETYPE_CONFIGS.get(archetype)
    if style_config and style_config.seed_utterance_path:
        ref_path = style_config.seed_utterance_path
        source = "archetype_seed_wav"
    else:
        ref_path = os.getenv("VOICE_REFERENCE_AUDIO_PATH") or ""
        source = "env_reference_wav"

    reference_audio, path_name = _read_reference_path(ref_path)
    if reference_audio:
        return reference_audio, _reference_diagnostics(
            cid=cid,
            source=source,
            ok=True,
            fallback_used=bool(cid or failure_reason),
            failure_reason=failure_reason,
            path_name=path_name,
        )

    if ref_path and not failure_reason:
        failure_reason = "reference_file_unavailable"
    elif not ref_path and not failure_reason:
        failure_reason = "no_agent_reference"

    reference_audio, path_name = _read_philosopher_reference()
    if reference_audio:
        return reference_audio, _reference_diagnostics(
            cid=cid,
            source="philosopher_seed_wav",
            ok=True,
            fallback_used=True,
            failure_reason=failure_reason,
            path_name=path_name,
        )

    return None, _reference_diagnostics(
        cid=cid,
        ok=False,
        fallback_used=bool(cid or failure_reason),
        failure_reason=failure_reason or "no_reference_audio",
    )


def _reference_audio_for_agent(agent: dict[str, Any] | None) -> bytes | None:
    reference_audio, _diagnostics = _resolve_reference_audio(agent)
    return reference_audio


def _prosody_supports_tags(agent: dict[str, Any] | None, snapshot: dict[str, Any]) -> bool:
    if agent is not None:
        voice_params = agent.get("voice_params") or {}
        if isinstance(voice_params, dict):
            if "supports_prosody_tags" in voice_params:
                return bool(voice_params.get("supports_prosody_tags"))
            if "prosody_supported" in voice_params:
                return bool(voice_params.get("prosody_supported"))
    status = snapshot.get("voice_status") or {}
    if isinstance(status, dict):
        return bool(status.get("supports_prosody_tags") or status.get("prosody_tags"))
    return False


def _current_quality_score(snapshot: dict[str, Any]) -> int:
    last_turn = snapshot.get("last_dialogue_turn") or {}
    if isinstance(last_turn.get("quality_score"), int):
        return int(last_turn.get("quality_score"))
    if isinstance(snapshot.get("quality_score"), int):
        return int(snapshot.get("quality_score"))
    return 0


def _voice_modifiers(snapshot: dict[str, Any]) -> tuple[float, float]:
    pair_state = snapshot.get("pair_state") or {}
    if not isinstance(pair_state, dict):
        tension = int(getattr(pair_state, "tension_level", 5) or 5)
        reconciliation = bool(getattr(pair_state, "reconciliation_arc", False))
    else:
        tension = int(pair_state.get("tension_level") or 5)
        reconciliation = bool(pair_state.get("reconciliation_arc") or False)
    speed = 1.0
    pitch = 1.0
    if tension > 7:
        speed *= 1.08
        pitch *= 1.05
    if reconciliation:
        speed *= 0.95
    return speed, pitch


def _select_prosody_tag(
    agent: dict[str, Any] | None, move: str, quality_score: int, supports_tags: bool
) -> str:
    if not supports_tags:
        return ""
    voice_params = (agent or {}).get("voice_params") or {}
    prosody_map = voice_params.get("prosody_map") if isinstance(voice_params, dict) else {}
    mapped = str((prosody_map or {}).get(move, "")).strip()
    mapped = mapped.strip("[]")
    if quality_score > 12 and mapped:
        return f"[emphasis][{mapped}]"
    if quality_score > 12:
        return "[emphasis]"
    if mapped:
        return f"[{mapped}]"
    return ""


def build_voice_status() -> dict[str, Any]:
    endpoint = tts_health_url()
    provider = os.getenv("VOICE_PROVIDER") or os.getenv("TTS_PROVIDER") or "kokoro"
    lip_sync_source = os.getenv("LIP_SYNC_SOURCE", "audio_rms")
    return {
        "enabled": _env_bool("VOICE_ENABLED") or bool(os.getenv("TTS_MODEL")) or bool(endpoint),
        "dry_run": _env_bool("VOICE_DRY_RUN", "false"),
        "synthesis_enabled": _voice_synthesis_enabled(),
        "provider": provider,
        "voice_model": _pick_voice_model(),
        "voice_name": _pick_voice_name(),
        "playback_mode": os.getenv("VOICE_PLAYBACK_MODE", "browser+sink"),
        "speech_profile": os.getenv("VOICE_PROFILE", "dramatic"),
        "lip_sync_source": lip_sync_source,
        "lip_sync": {
            "source": lip_sync_source,
            "phoneme_output": False,
            "limitation": "Fish Speech currently returns audio, not phoneme timings.",
            "latency_target_ms": 300,
        },
        "phoneme_output": False,
        "voice_reference_field": "voice_model_cid",
        "voice_reference_semantics": "fish_reference_wav_cid",
        "voice_model_semantics": "tts_backend_model_name",
        "transport": os.getenv("VOICE_TRANSPORT", "local-tts"),
        "health": probe_url(endpoint, timeout=1.5),
        "render_target": os.getenv("VOICE_RENDER_TARGET", "obs-audio"),
        "sample_rate": int(os.getenv("VOICE_SAMPLE_RATE", "48000")),
    }


def _lip_sync_metadata(source: str) -> dict[str, Any]:
    return {
        "source": source,
        "phoneme_output": False,
        "limitation": "Fish Speech currently returns audio, not phoneme timings.",
        "latency_target_ms": 300,
    }


def _mouth_fallback(plan: VoicePlan) -> float:
    return round(
        procedural_mouth_amplitude(
            is_speaking=True,
            emotional_texture_score=plan.emotional_texture_score,
        ),
        6,
    )


def _fallback_synthesis(
    plan: VoicePlan,
    reason: str,
    *,
    endpoint: str | None = None,
    reference_audio: dict[str, Any] | None = None,
    error: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "reason": reason,
        "audio_rms": 0.0,
        "audio_peak": 0.0,
        "mouth_amplitude": _mouth_fallback(plan),
        "audio_analysis": {"ok": False, "reason": reason},
        "lip_sync": _lip_sync_metadata("procedural"),
        "latency_target_ms": 300,
    }
    if endpoint:
        payload["endpoint"] = endpoint
    if reference_audio is not None:
        payload["reference_audio"] = reference_audio
    if error:
        payload["error"] = error
    return payload


def _decode_inline_audio(body: dict[str, Any]) -> tuple[bytes | None, str]:
    for key in ("audio", "audio_base64", "wav", "audio_data"):
        value = body.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        encoded = value.strip()
        if encoded.startswith("data:") and "," in encoded:
            encoded = encoded.split(",", 1)[1]
        try:
            return base64.b64decode(encoded, validate=True), key
        except Exception:
            return None, f"{key}_decode_failed"
    return None, "no_inline_audio"


def _attach_audio_analysis(
    synthesis: dict[str, Any],
    plan: VoicePlan,
    audio_bytes: bytes | None,
    *,
    content_type: str,
    reason_when_missing: str,
) -> None:
    if audio_bytes:
        features = analyze_audio_bytes(
            audio_bytes,
            content_type=content_type,
            emotional_texture_score=plan.emotional_texture_score,
        )
        synthesis["audio_analysis"] = features.to_dict()
        if features.ok:
            synthesis["audio_rms"] = features.audio_rms
            synthesis["audio_peak"] = features.audio_peak
            synthesis["mouth_amplitude"] = features.mouth_amplitude
            if not synthesis.get("duration_seconds"):
                synthesis["duration_seconds"] = features.duration_seconds
            synthesis["lip_sync"] = _lip_sync_metadata("audio_rms")
            return
    else:
        synthesis["audio_analysis"] = {"ok": False, "reason": reason_when_missing}

    synthesis["audio_rms"] = 0.0
    synthesis["audio_peak"] = 0.0
    synthesis["mouth_amplitude"] = _mouth_fallback(plan)
    synthesis["lip_sync"] = _lip_sync_metadata("procedural")


class VoiceSurface:
    """Compose a voice plan from the live world snapshot."""

    def __init__(self, enabled: bool | None = None, dry_run: bool | None = None):
        self.enabled = _env_bool("VOICE_ENABLED") if enabled is None else enabled
        if dry_run is None:
            self.dry_run = _env_bool("VOICE_DRY_RUN", "false")
            _voice_dry_run_raw = os.getenv("VOICE_DRY_RUN")
            if _voice_dry_run_raw is not None and self.dry_run:
                _log.debug(
                    "VOICE_DRY_RUN explicitly set to '%s'; dry-run mode active", _voice_dry_run_raw
                )
        else:
            self.dry_run = dry_run
        self.provider = os.getenv("VOICE_PROVIDER") or os.getenv("TTS_PROVIDER") or "kokoro"
        self.transport = os.getenv("VOICE_TRANSPORT", "local-tts")
        self.synthesis_enabled = _voice_synthesis_enabled()
        self._cached_health = _CachedHealthProbe(ttl=5.0)
        self._last_plan: VoicePlan | None = None

    def compose(self, snapshot: dict[str, Any]) -> VoiceState:
        self.synthesis_enabled = _voice_synthesis_enabled()
        showrunner = snapshot.get("showrunner") or {}
        broadcast = snapshot.get("broadcast") or {}
        # Prefer most recent live dialogue turn over showrunner headline
        last_turn = snapshot.get("last_dialogue_turn") or {}
        max_dialogue_age = float(os.getenv("VOICE_DIALOGUE_MAX_AGE_SECONDS", "20"))
        dialogue_age = _turn_age_seconds(snapshot, last_turn)
        if last_turn.get("content") and (dialogue_age is None or dialogue_age <= max_dialogue_age):
            speaker = str(last_turn.get("sender_name") or showrunner.get("speaker") or "Narrator")
            raw_line = str(last_turn["content"])
        else:
            speaker = str(
                showrunner.get("speaker") or broadcast.get("scene", {}).get("speaker") or "Narrator"
            )
            raw_line = str(
                showrunner.get("audience_prompt")
                or showrunner.get("headline")
                or broadcast.get("caption", {}).get("headline")
                or "The world keeps moving."
            )
            # Graceful fallback: avoid abrupt switch to static string
            if raw_line == "The world keeps moving.":
                if self._last_plan is not None:
                    # Reuse the last successful voice plan's content
                    speaker = self._last_plan.speaker
                    raw_line = self._last_plan.line
                elif last_turn.get("content"):
                    # Dialogue is stale but has content — reuse it for continuity
                    speaker = str(
                        last_turn.get("sender_name") or showrunner.get("speaker") or "Narrator"
                    )
                    raw_line = str(last_turn["content"])
                else:
                    _log.info("No previous plan available for graceful fallback; using static line")
        stripped = _UUID_PREFIX_RE.sub("", raw_line)
        stripped = _EMOJI_RE.sub("", stripped)
        stripped = _ARROW_NARRATIVE_RE.sub("", stripped).strip("\"'").strip()
        stripped = _SEND_NARRATIVE_RE.sub("", stripped).strip("\"'").strip()
        stripped = _AGENT_PREFIX_RE.sub("", stripped)
        stripped = _AGENT_BARE_NAME_RE.sub("", stripped)
        stripped = stripped.replace(" / ", " ").replace(" /", " ").replace("/ ", " ")
        stripped = re.sub(r"\s{2,}", " ", stripped).strip()
        line = stripped.strip() or raw_line.strip()
        emotion = _pick_emotion(snapshot)
        voice_model = _pick_voice_model()
        voice_name = _pick_voice_name()
        utterance_id = _utterance_id(snapshot, speaker, line)
        health = self._cached_health.get(tts_health_url(), timeout=1.5)
        move = _pick_move(snapshot)
        quality_score = _current_quality_score(snapshot)
        emotional_texture_score = min(3, max(0, quality_score // 5))
        selected_agent = _voice_agent(snapshot, speaker)
        supports_tags = _prosody_supports_tags(selected_agent, snapshot)
        prosody_tag = _select_prosody_tag(selected_agent, move, quality_score, supports_tags)
        speed_modifier, pitch_modifier = _voice_modifiers(snapshot)
        speed = _dialogue_speed(snapshot, line)
        last_meta = last_turn.get("metadata") or {}
        if isinstance(last_meta, str):
            try:
                import json as _json

                last_meta = _json.loads(last_meta)
            except Exception:
                last_meta = {}
        cadence = str(
            last_turn.get("cadence")
            or last_meta.get("cadence")
            or last_turn.get("beat_count")
            or last_meta.get("beat_count")
            or ""
        ).strip()
        tagged_line = line
        if prosody_tag:
            if prosody_tag == "[emphasis]":
                tagged_line = f"[emphasis]{line}[/emphasis]"
            elif prosody_tag.startswith("[emphasis]"):
                inner = prosody_tag.removeprefix("[emphasis]")
                tag_name = inner.strip("[]")
                if tag_name:
                    tagged_line = f"[emphasis]{inner}{line}[/{tag_name}][/emphasis]"
                else:
                    tagged_line = f"[emphasis]{line}[/emphasis]"
            else:
                tag_name = prosody_tag.strip("[]")
                tagged_line = f"{prosody_tag}{line}[/{tag_name}]"
        plan = VoicePlan(
            speaker=speaker,
            line=tagged_line,
            emotion=emotion,
            utterance_id=utterance_id,
            voice_provider=self.provider,
            voice_model=voice_model,
            voice_name=voice_name,
            pitch=float(os.getenv("VOICE_PITCH", "0.5")) * pitch_modifier,
            speed=float(os.getenv("VOICE_SPEED", str(speed))) * speed_modifier,
            sample_rate=int(os.getenv("VOICE_SAMPLE_RATE", "48000")),
            lip_sync_source=os.getenv("LIP_SYNC_SOURCE", "audio_rms"),
            transport=self.transport,
            notes=tuple(
                filter(
                    None,
                    [
                        f"scene={showrunner.get('scene') or 'world-wide'}",
                        f"speaker={speaker}",
                        f"emotion={emotion}",
                        f"cadence={cadence}" if cadence else "",
                        f"utterance={utterance_id}",
                        f"voice={voice_name}",
                        f"move={move}" if move else "",
                        f"prosody={prosody_tag}" if prosody_tag else "",
                        f"emotional_texture={emotional_texture_score}",
                    ],
                )
            ),
            prosody_tag=prosody_tag,
            emotional_texture_score=emotional_texture_score,
            tension_speed_modifier=speed_modifier,
            tension_pitch_modifier=pitch_modifier,
        )
        self._last_plan = plan
        synthesis = self._maybe_synthesize(plan, health, selected_agent)
        return VoiceState(
            enabled=self.enabled,
            dry_run=self.dry_run,
            provider=self.provider,
            voice_model=voice_model,
            voice_name=voice_name,
            playback_mode=os.getenv("VOICE_PLAYBACK_MODE", "browser+sink"),
            speech_profile=os.getenv("VOICE_PROFILE", "dramatic"),
            lip_sync_source=os.getenv("LIP_SYNC_SOURCE", "audio_rms"),
            transport=self.transport,
            health=health,
            plan=plan,
            synthesis=synthesis,
        )

    def status(self) -> dict[str, Any]:
        return build_voice_status()

    def _maybe_synthesize(
        self,
        plan: VoicePlan,
        health: dict[str, Any],
        agent: dict[str, Any] | None,
    ) -> dict[str, Any]:
        endpoint = tts_base_url()
        if not self.enabled:
            return _fallback_synthesis(plan, "disabled")
        if self.dry_run:
            return _fallback_synthesis(plan, "dry_run")
        if not self.synthesis_enabled:
            return _fallback_synthesis(plan, "synthesis_disabled")
        if not endpoint:
            return _fallback_synthesis(plan, "missing_tts_endpoint")

        cached = _synthesis_cache.get(plan.utterance_id)
        if cached is not None:
            return cached

        if not health.get("ok"):
            return _fallback_synthesis(plan, "unhealthy_endpoint", endpoint=endpoint)

        if not _synthesis_lock.acquire(blocking=False):
            return _fallback_synthesis(plan, "synthesis_in_progress", endpoint=endpoint)

        try:
            cached = _synthesis_cache.get(plan.utterance_id)
            if cached is not None:
                return cached

            reference_audio, reference_info = _resolve_reference_audio(agent)
            if reference_audio is None:
                return _fallback_synthesis(
                    plan,
                    "no_reference_audio",
                    reference_audio=reference_info,
                )
            synth_url = f"{endpoint.rstrip('/')}/v1/tts"
            payload = {
                "text": plan.line,
                "references": [
                    {
                        "audio": base64.b64encode(reference_audio).decode(),
                        "text": "",
                    }
                ],
                "format": "wav",
                "streaming": False,
            }

            # Unload Ollama from GPU so fish-speech has full VRAM bandwidth
            try:
                _ollama = ollama_base_url()
                _model = os.getenv("LLM_MODEL", "llama3.1:8b")
                httpx.post(
                    f"{_ollama}/api/generate", json={"model": _model, "keep_alive": 0}, timeout=8.0
                )
                import time as _time

                _time.sleep(1)
            except Exception:
                pass

            try:
                response = httpx.post(synth_url, json=payload, timeout=120.0)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                synthesis: dict[str, Any] = {
                    "ok": True,
                    "endpoint": synth_url,
                    "content_type": content_type,
                    "byte_count": len(response.content or b""),
                    "reference_audio": reference_info,
                    "latency_target_ms": 300,
                }
                audio_bytes: bytes | None = None
                analysis_content_type = content_type
                analysis_missing_reason = "audio_bytes_unavailable"
                if content_type.startswith("application/json"):
                    try:
                        body = response.json()
                    except Exception:
                        body = {}
                    if isinstance(body, dict):
                        synthesis["response_keys"] = sorted(body.keys())
                        if body.get("audio_url"):
                            synthesis["audio_url"] = str(body["audio_url"])
                            analysis_missing_reason = "external_audio_url"
                        if body.get("audio") is not None:
                            synthesis["audio_present"] = True
                        if body.get("content_type") or body.get("mime_type"):
                            analysis_content_type = str(
                                body.get("content_type") or body.get("mime_type") or content_type
                            )
                        if body.get("duration_seconds") is not None:
                            synthesis["duration_seconds"] = body["duration_seconds"]
                        audio_bytes, decode_reason = _decode_inline_audio(body)
                        if audio_bytes:
                            synthesis["audio_present"] = True
                            synthesis["audio_byte_count"] = len(audio_bytes)
                        elif decode_reason != "no_inline_audio":
                            analysis_missing_reason = decode_reason
                elif content_type.startswith("audio/"):
                    synthesis["audio_present"] = True
                    audio_bytes = response.content or None
                    synthesis["audio_byte_count"] = len(audio_bytes or b"")
                elif response.content and response.content.startswith(b"RIFF"):
                    synthesis["audio_present"] = True
                    audio_bytes = response.content
                    analysis_content_type = "audio/wav"
                    synthesis["audio_byte_count"] = len(audio_bytes)
                _attach_audio_analysis(
                    synthesis,
                    plan,
                    audio_bytes,
                    content_type=analysis_content_type,
                    reason_when_missing=analysis_missing_reason,
                )
                if len(_synthesis_cache) >= _SYNTHESIS_CACHE_MAX:
                    try:
                        oldest = next(iter(_synthesis_cache))
                        _synthesis_cache.pop(oldest)
                        _audio_cache.pop(oldest, None)
                    except StopIteration:
                        pass
                _synthesis_cache[plan.utterance_id] = synthesis
                if audio_bytes:
                    _audio_cache[plan.utterance_id] = audio_bytes
                    _play_to_pulse_sink_async(audio_bytes)
                return synthesis
            except Exception as exc:
                _log.warning("voice synthesis failed: %s", exc)
                return _fallback_synthesis(
                    plan,
                    "synthesis_failed",
                    endpoint=synth_url,
                    reference_audio=reference_info,
                    error=str(exc),
                )
        finally:
            _synthesis_lock.release()


def _play_to_pulse_sink_async(audio_bytes: bytes) -> None:
    sink = os.getenv("VOICE_PULSE_SINK", "")
    if not sink:
        return

    def _play() -> None:
        import subprocess
        import tempfile

        try:
            runtime_dir = os.getenv(
                "VOICE_XDG_RUNTIME_DIR",
                os.path.join(tempfile.gettempdir(), "runtime-stream"),
            )
            env = {
                **os.environ,
                "HOME": "/home/stream",
                "XDG_RUNTIME_DIR": runtime_dir,
                "PULSE_SERVER": f"unix:{runtime_dir}/pulse/native",
            }
            proc = subprocess.Popen(
                ["paplay", "-d", sink],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
            )
            proc.stdin.write(audio_bytes)
            proc.stdin.close()
            proc.wait(timeout=60)
        except Exception as exc:
            _log.debug("pulse sink play failed: %s", exc)

    threading.Thread(target=_play, daemon=True).start()


_voice_surface_singleton: VoiceSurface | None = None
_synthesis_cache: dict[str, dict[str, Any]] = {}
_audio_cache: dict[str, bytes] = {}
_SYNTHESIS_CACHE_MAX = 32
_synthesis_lock = threading.Lock()


def _get_voice_surface() -> VoiceSurface:
    global _voice_surface_singleton
    if _voice_surface_singleton is None:
        _voice_surface_singleton = VoiceSurface()
    return _voice_surface_singleton


def build_voice_state(snapshot: dict[str, Any]) -> dict[str, Any]:
    try:
        result = _get_voice_surface().compose(snapshot)
        state = result.to_dict()
        # Log warning if health probe failed (exception swallowed in background thread)
        health = state.get("health") or {}
        if not health.get("ok"):
            _log.warning(
                "build_voice_state degraded health: reason=%s | snapshot_keys=%s",
                health.get("reason", "unknown"),
                list(snapshot.keys()) if snapshot else [],
            )
        return state
    except Exception as exc:
        _log.warning(
            "build_voice_state failed: %s: %s | snapshot_keys=%s",
            type(exc).__name__,
            exc,
            list(snapshot.keys()) if snapshot else [],
        )
        return {
            "enabled": False,
            "dry_run": True,
            "provider": os.getenv("VOICE_PROVIDER") or os.getenv("TTS_PROVIDER") or "kokoro",
            "voice_model": _pick_voice_model(),
            "voice_name": _pick_voice_name(),
            "playback_mode": os.getenv("VOICE_PLAYBACK_MODE", "browser+sink"),
            "speech_profile": os.getenv("VOICE_PROFILE", "dramatic"),
            "lip_sync_source": os.getenv("LIP_SYNC_SOURCE", "audio_rms"),
            "transport": os.getenv("VOICE_TRANSPORT", "local-tts"),
            "health": {"ok": False, "reason": "compose_failed"},
            "plan": None,
            "synthesis": {
                "ok": False,
                "reason": "compose_failed",
                "lip_sync": _lip_sync_metadata("procedural"),
            },
        }


def get_cached_audio(utterance_id: str) -> bytes | None:
    return _audio_cache.get(utterance_id)


def build_voice_status_surface() -> dict[str, Any]:
    return build_voice_status()
