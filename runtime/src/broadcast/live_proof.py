"""YouTube live proof readiness report for the OBS/browser stage."""

from __future__ import annotations

from typing import Any

YOUTUBE_LIVE_PROOF_SCHEMA_VERSION = 1


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _positive_float(value: Any) -> float:
    try:
        number = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return number if number > 0.0 else 0.0


def _value_at(root: dict[str, Any], path: tuple[str, ...]) -> Any:
    cursor: Any = root
    for key in path:
        if not isinstance(cursor, dict):
            return None
        cursor = cursor.get(key)
    return cursor


def _ref_present(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        for key in (
            "url",
            "src",
            "href",
            "cid",
            "ipfs_cid",
            "asset_cid",
            "local_cache_path",
        ):
            if _text(value.get(key)):
                return True
        if isinstance(value.get("sources"), (dict, list)):
            return _ref_present(value["sources"])
    if isinstance(value, list):
        return any(_ref_present(item) for item in value)
    return False


def _active_agent(snapshot: dict[str, Any], speaker: str) -> dict[str, Any]:
    agents = [item for item in _as_list(snapshot.get("agents")) if isinstance(item, dict)]
    if not agents:
        return {}
    speaker_lc = speaker.lower()
    for agent in agents:
        names = (
            agent.get("current_name"),
            agent.get("name"),
            _as_dict(agent.get("identity")).get("current_name"),
            agent.get("soul_id"),
        )
        if speaker_lc and any(_text(name).lower() == speaker_lc for name in names):
            return agent
    return agents[0]


def _speaker(snapshot: dict[str, Any], avatar: dict[str, Any]) -> str:
    plan = _as_dict(avatar.get("plan"))
    showrunner = _as_dict(snapshot.get("showrunner"))
    broadcast = _as_dict(snapshot.get("broadcast"))
    scene = _as_dict(broadcast.get("scene"))
    return (
        _text(plan.get("speaker"))
        or _text(showrunner.get("speaker"))
        or _text(scene.get("speaker"))
        or "Narrator"
    )


def _voice_path(voice: dict[str, Any]) -> dict[str, Any]:
    plan = _as_dict(voice.get("plan"))
    synthesis = _as_dict(voice.get("synthesis"))
    endpoint = _text(synthesis.get("endpoint"))
    provider_blob = " ".join(
        filter(
            None,
            [
                _text(voice.get("provider")),
                _text(plan.get("voice_provider")),
                _text(voice.get("voice_model")),
                _text(plan.get("voice_model")),
                endpoint,
            ],
        )
    ).lower()
    endpoint_lc = endpoint.lower()
    endpoint_base = endpoint_lc.rstrip("/")
    fish_configured = (
        "fish" in provider_blob
        or endpoint_base
        in {
            "http://localhost:7860",
            "http://127.0.0.1:7860",
            "http://fish-speech:7860",
        }
        or endpoint_lc.startswith("http://localhost:7860/")
        or endpoint_lc.startswith("http://127.0.0.1:7860/")
        or endpoint_lc.startswith("http://fish-speech:7860/")
    )
    audio_present = bool(
        synthesis.get("ok")
        and (
            synthesis.get("audio_present")
            or _text(synthesis.get("audio_url"))
            or _positive_float(synthesis.get("audio_byte_count")) > 0.0
            or _positive_float(synthesis.get("byte_count")) > 0.0
            or _text(synthesis.get("content_type")).startswith("audio/")
        )
    )
    mouth_amplitude = max(
        _positive_float(synthesis.get("mouth_amplitude")),
        _positive_float(plan.get("mouth_open")),
    )
    if audio_present and fish_configured:
        mode = "fish_audio"
    elif audio_present:
        mode = "tts_audio"
    elif synthesis.get("reason"):
        mode = "voice_fallback"
    else:
        mode = "silent_or_text"
    return {
        "mode": mode,
        "fish_configured": fish_configured,
        "audio_present": audio_present,
        "silence_risk": not (audio_present and fish_configured),
        "mouth_amplitude": round(mouth_amplitude, 4),
        "reason": _text(synthesis.get("reason")),
        "utterance_id": _text(plan.get("utterance_id")),
        "line": _text(plan.get("line")),
        "speaker": _text(plan.get("speaker")),
        "provider": _text(voice.get("provider") or plan.get("voice_provider")),
        "endpoint": endpoint,
    }


def _ready_video_label(container: dict[str, Any], prefix: str) -> str:
    manifest_paths = (
        ("video_manifest",),
        ("avatar_manifest",),
        ("manifest",),
        ("plan", "video_manifest"),
        ("plan", "avatar_manifest"),
    )
    direct_paths = (
        ("speaking_loop",),
        ("talking_loop",),
        ("loop",),
        ("idle_loop",),
        ("video_loop",),
        ("cinematic_clip",),
        ("assets", "speaking_loop"),
        ("assets", "loop"),
        ("assets", "cinematic"),
        ("loops", "speaking"),
        ("loops", "idle"),
        ("videos", "speaking"),
        ("videos", "loop"),
        ("videos", "cinematic"),
        ("sources", "loop"),
    )
    for path in direct_paths:
        if _ref_present(_value_at(container, path)):
            return f"{prefix}.{'.'.join(path)}"
    for path in manifest_paths:
        manifest = _as_dict(_value_at(container, path))
        if not manifest:
            continue
        assets = _as_list(manifest.get("assets"))
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            if _text(asset.get("status") or "ready") == "failed":
                continue
            if _text(asset.get("variant")) in ("", "low_res_live") and _ref_present(asset):
                return f"{prefix}.{'.'.join(path)}.assets"
        for direct_path in direct_paths:
            if _ref_present(_value_at(manifest, direct_path)):
                return f"{prefix}.{'.'.join(path)}.{'.'.join(direct_path)}"
    return ""


def _portrait_label(avatar: dict[str, Any], agent: dict[str, Any]) -> str:
    avatar_plan = _as_dict(avatar.get("plan"))
    candidates = (
        ("avatar.avatar_asset", avatar.get("avatar_asset")),
        ("avatar.rigged_avatar_cid", avatar.get("rigged_avatar_cid")),
        ("avatar.vrm_avatar_url", avatar.get("vrm_avatar_url")),
        ("avatar.plan.rigged_avatar_cid", avatar_plan.get("rigged_avatar_cid")),
        ("avatar.plan.vrm_avatar_url", avatar_plan.get("vrm_avatar_url")),
        ("agent.avatar_cid", agent.get("avatar_cid")),
        ("agent.rigged_avatar_cid", agent.get("rigged_avatar_cid")),
        ("agent.vrm_avatar_url", agent.get("vrm_avatar_url")),
        ("agent.portrait_url", agent.get("portrait_url")),
    )
    for label, value in candidates:
        if _ref_present(value):
            return label
    return ""


def _life_visible(avatar: dict[str, Any]) -> bool:
    life = _as_dict(avatar.get("life")) or _as_dict(_as_dict(avatar.get("plan")).get("life"))
    return any(
        key in life
        for key in (
            "breathing_phase",
            "blink_state",
            "head_sway_x",
            "head_sway_y",
            "mouth_amplitude",
        )
    )


def _visual_path(
    snapshot: dict[str, Any], avatar: dict[str, Any], voice: dict[str, Any]
) -> dict[str, Any]:
    speaker = _speaker(snapshot, avatar)
    agent = _active_agent(snapshot, speaker)
    video_label = _ready_video_label(avatar, "avatar") or _ready_video_label(agent, "agent")
    portrait_label = _portrait_label(avatar, agent)
    generated_fallback = bool(
        speaker or _text(agent.get("current_name")) or _text(agent.get("name"))
    )

    if video_label:
        mode = "video_loop"
        source = video_label
    elif portrait_label:
        mode = "portrait_fallback"
        source = portrait_label
    elif generated_fallback:
        mode = "generated_fallback"
        source = "observer.generated_initial"
    else:
        mode = "missing"
        source = ""

    life_visible = _life_visible(avatar)
    voice_path = _voice_path(voice)
    mouth_open = max(
        _positive_float(avatar.get("mouth_open")),
        _positive_float(_as_dict(avatar.get("plan")).get("mouth_open")),
        _positive_float(_as_dict(avatar.get("life")).get("mouth_amplitude")),
        voice_path["mouth_amplitude"],
    )
    speaking = bool(avatar.get("speaking") or _as_dict(avatar.get("plan")).get("speaking"))
    voice_audio_present = bool(
        voice_path["audio_present"] and voice_path["mode"] in {"fish_audio", "tts_audio"}
    )
    return {
        "mode": mode,
        "source": source,
        "fallback_active": mode in {"portrait_fallback", "generated_fallback"},
        "has_visual": mode != "missing",
        "black_screen_risk": mode == "missing",
        "procedural_life_visible": life_visible,
        "speaking": speaking,
        "mouth_reacts_to_voice": bool(voice_audio_present and mouth_open > 0.0),
        "mouth_open": round(mouth_open, 4),
        "speaker": speaker,
        "agent_id": _text(agent.get("soul_id")),
    }


def _caption_path(broadcast: dict[str, Any]) -> dict[str, Any]:
    caption = _as_dict(broadcast.get("caption"))
    ticker_lines = _as_list(caption.get("ticker_lines"))
    fields = (
        _text(caption.get("headline")),
        _text(caption.get("subhead")),
        _text(caption.get("lower_third")),
        *[_text(line) for line in ticker_lines],
    )
    present = any(fields)
    return {
        "mode": "captioned" if present else "missing",
        "present": present,
        "headline": _text(caption.get("headline")),
        "lower_third": _text(caption.get("lower_third")),
        "ticker_count": len([line for line in ticker_lines if _text(line)]),
    }


def _runtime_comfy_path(
    runtime_ready: dict[str, Any] | None, visual: dict[str, Any]
) -> dict[str, Any]:
    ready = _as_dict(runtime_ready)
    comfy = _as_dict(_as_dict(ready.get("checks")).get("comfyui"))
    if not comfy:
        return {
            "mode": "not_probed",
            "ok": True,
            "optional": True,
            "reason": "not_supplied",
        }
    return {
        "mode": "available" if comfy.get("ok") else "fallback_only",
        "ok": bool(comfy.get("ok") or visual["has_visual"]),
        "optional": True,
        "reason": _text(comfy.get("reason"))
        or ("ok" if comfy.get("ok") else "visual_fallback_ready"),
    }


def _gpu_path(gpu_diagnostics: dict[str, Any] | None) -> dict[str, Any]:
    diagnostics = _as_dict(gpu_diagnostics)
    if not diagnostics:
        return {
            "mode": "not_probed",
            "background_jobs_allowed": None,
            "queue_depth": None,
            "current_job": None,
        }
    background_allowed = bool(diagnostics.get("background_jobs_allowed", True))
    return {
        "mode": "live_safe" if not background_allowed else "background_allowed",
        "background_jobs_allowed": background_allowed,
        "queue_depth": int(diagnostics.get("queue_depth") or 0),
        "current_job": diagnostics.get("current_job"),
    }


def _check(name: str, ok: bool, severity: str, evidence: str) -> dict[str, Any]:
    return {
        "name": name,
        "ok": bool(ok),
        "severity": severity,
        "evidence": evidence,
    }


def _required_actions(checks: list[dict[str, Any]]) -> list[str]:
    actions = [
        f"Fix required check: {check['name']} ({check['evidence']})."
        for check in checks
        if check["severity"] == "required" and not check["ok"]
    ]
    actions.append(
        "Run a 5-10 minute private YouTube/OBS stream and attach VOD plus benchmark JSON/notes."
    )
    return actions


def build_youtube_live_proof_report(
    snapshot: dict[str, Any],
    *,
    runtime_ready: dict[str, Any] | None = None,
    gpu_diagnostics: dict[str, Any] | None = None,
    observed_at: float | None = None,
) -> dict[str, Any]:
    """Return the operator-facing readiness proof for issue #101.

    The report is a pure projection over supplied state. It does not contact
    OBS, YouTube, Fish, ComfyUI, IPFS, or the GPU queue by itself.
    """

    snapshot = _as_dict(snapshot)
    avatar = _as_dict(snapshot.get("avatar"))
    voice = _as_dict(snapshot.get("voice"))
    broadcast = _as_dict(snapshot.get("broadcast"))

    voice_path = _voice_path(voice)
    visual_path = _visual_path(snapshot, avatar, voice)
    caption_path = _caption_path(broadcast)
    comfy_path = _runtime_comfy_path(runtime_ready, visual_path)
    gpu_path = _gpu_path(gpu_diagnostics)

    checks = [
        _check(
            "fish_voice_audio",
            voice_path["fish_configured"] and voice_path["audio_present"],
            "required",
            f"mode={voice_path['mode']} provider={voice_path['provider'] or 'unknown'}",
        ),
        _check(
            "avatar_visual_available",
            visual_path["has_visual"],
            "required",
            f"mode={visual_path['mode']} source={visual_path['source'] or 'none'}",
        ),
        _check(
            "procedural_life_visible",
            visual_path["procedural_life_visible"],
            "required",
            f"speaking={visual_path['speaking']} mouth_open={visual_path['mouth_open']}",
        ),
        _check(
            "mouth_reacts_to_voice",
            visual_path["mouth_reacts_to_voice"],
            "required",
            f"mouth_open={visual_path['mouth_open']} voice_mode={voice_path['mode']}",
        ),
        _check(
            "captions_visible",
            caption_path["present"],
            "required",
            f"mode={caption_path['mode']} headline={caption_path['headline'][:60]}",
        ),
        _check(
            "comfy_video_optional",
            comfy_path["ok"],
            "required",
            f"mode={comfy_path['mode']} visual_mode={visual_path['mode']}",
        ),
        _check(
            "background_video_jobs_disabled_for_live",
            gpu_path["background_jobs_allowed"] is not True,
            "advisory",
            f"mode={gpu_path['mode']} queue_depth={gpu_path['queue_depth']}",
        ),
    ]

    blocking_failures = [
        check for check in checks if check["severity"] == "required" and not check["ok"]
    ]
    if blocking_failures:
        status = "blocked"
    elif visual_path["fallback_active"] or comfy_path["mode"] == "fallback_only":
        status = "degraded_private_test_ready"
    else:
        status = "ready_for_private_test"

    proof_links = _as_dict(snapshot.get("youtube_proof") or snapshot.get("live_proof"))
    vod_linked = bool(_text(proof_links.get("vod_url") or proof_links.get("vod")))
    benchmark_linked = bool(
        _text(proof_links.get("benchmark_url") or proof_links.get("benchmark_report"))
    )

    return {
        "schema_version": YOUTUBE_LIVE_PROOF_SCHEMA_VERSION,
        "platform": "youtube",
        "status": status,
        "ready_for_private_stream": status != "blocked",
        "acceptance_complete": bool(status != "blocked" and vod_linked and benchmark_linked),
        "observed_at": observed_at if observed_at is not None else snapshot.get("epoch"),
        "world_id": _text(snapshot.get("world_id")),
        "operator_state": {
            "visual_mode": visual_path["mode"],
            "voice_mode": voice_path["mode"],
            "caption_mode": caption_path["mode"],
            "fallback_active": bool(visual_path["fallback_active"]),
            "black_screen_risk": bool(visual_path["black_screen_risk"]),
            "silence_risk": bool(voice_path["silence_risk"]),
        },
        "checks": checks,
        "evidence": {
            "voice": voice_path,
            "avatar": visual_path,
            "captions": caption_path,
            "comfy": comfy_path,
            "gpu": gpu_path,
        },
        "acceptance": {
            "vod_required": True,
            "vod_linked": vod_linked,
            "benchmark_notes_linked": benchmark_linked,
            "vod_duration_minutes": "5-10",
        },
        "required_actions": _required_actions(checks),
    }
