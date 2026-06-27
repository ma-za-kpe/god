"""Versioned avatar video manifest and cache-selection policy."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


VIDEO_MANIFEST_SCHEMA_VERSION = 1


class VideoVariant(str, Enum):
    LOW_RES_LIVE = "low_res_live"
    HIGH_RES_HIGHLIGHT = "high_res_highlight"


class VideoAssetStatus(str, Enum):
    READY = "ready"
    PENDING = "pending"
    FAILED = "failed"


@dataclass(frozen=True)
class VideoRetentionPolicy:
    """Lifecycle policy for durable IPFS assets and hot local playback cache."""

    max_age_seconds: int = 7 * 24 * 60 * 60
    live_cache_ttl_seconds: int = 6 * 60 * 60
    max_cache_bytes: int = 512 * 1024 * 1024
    pin_priority_floor: int = 50
    keep_highlight_assets: bool = True

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "VideoRetentionPolicy":
        payload = payload or {}
        defaults = cls()
        return cls(
            max_age_seconds=int(payload.get("max_age_seconds") or defaults.max_age_seconds),
            live_cache_ttl_seconds=int(
                payload.get("live_cache_ttl_seconds") or defaults.live_cache_ttl_seconds
            ),
            max_cache_bytes=int(payload.get("max_cache_bytes") or defaults.max_cache_bytes),
            pin_priority_floor=int(
                payload.get("pin_priority_floor") or defaults.pin_priority_floor
            ),
            keep_highlight_assets=bool(
                payload.get("keep_highlight_assets", defaults.keep_highlight_assets)
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_age_seconds": self.max_age_seconds,
            "live_cache_ttl_seconds": self.live_cache_ttl_seconds,
            "max_cache_bytes": self.max_cache_bytes,
            "pin_priority_floor": self.pin_priority_floor,
            "keep_highlight_assets": self.keep_highlight_assets,
        }


@dataclass(frozen=True)
class VideoAsset:
    """Durable metadata for one generated or imported video asset."""

    asset_id: str
    cid: str
    variant: VideoVariant
    model: str
    width: int
    height: int
    duration_ms: int
    source_image_cid: str = ""
    source_audio_cid: str = ""
    expression: str = "neutral"
    motion: str = "idle"
    priority: int = 0
    created_at: float = 0.0
    expires_at: float | None = None
    mime_type: str = "video/mp4"
    size_bytes: int = 0
    local_cache_path: str = ""
    status: VideoAssetStatus = VideoAssetStatus.READY

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"

    @property
    def is_highlight(self) -> bool:
        return self.variant == VideoVariant.HIGH_RES_HIGHLIGHT

    def is_expired(self, now: float) -> bool:
        return self.expires_at is not None and self.expires_at <= now

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "VideoAsset":
        return cls(
            asset_id=str(payload.get("asset_id") or payload.get("id") or ""),
            cid=str(payload.get("cid") or ""),
            variant=VideoVariant(str(payload.get("variant") or VideoVariant.LOW_RES_LIVE.value)),
            model=str(payload.get("model") or ""),
            width=int(payload.get("width") or 0),
            height=int(payload.get("height") or 0),
            duration_ms=int(payload.get("duration_ms") or 0),
            source_image_cid=str(payload.get("source_image_cid") or ""),
            source_audio_cid=str(payload.get("source_audio_cid") or ""),
            expression=str(payload.get("expression") or "neutral"),
            motion=str(payload.get("motion") or "idle"),
            priority=int(payload.get("priority") or 0),
            created_at=float(payload.get("created_at") or 0.0),
            expires_at=(
                float(payload["expires_at"])
                if payload.get("expires_at") not in (None, "")
                else None
            ),
            mime_type=str(payload.get("mime_type") or "video/mp4"),
            size_bytes=int(payload.get("size_bytes") or 0),
            local_cache_path=str(payload.get("local_cache_path") or ""),
            status=VideoAssetStatus(str(payload.get("status") or VideoAssetStatus.READY.value)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "cid": self.cid,
            "variant": self.variant.value,
            "model": self.model,
            "width": self.width,
            "height": self.height,
            "resolution": self.resolution,
            "duration_ms": self.duration_ms,
            "source_image_cid": self.source_image_cid,
            "source_audio_cid": self.source_audio_cid,
            "expression": self.expression,
            "motion": self.motion,
            "priority": self.priority,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "local_cache_path": self.local_cache_path,
            "status": self.status.value,
        }


@dataclass(frozen=True)
class VideoManifest:
    """Versioned manifest for avatar video assets.

    Durable identity fields stay outside this manifest: do not overload
    avatar_cid, rigged_avatar_cid, or voice_model_cid with video assets.
    """

    agent_id: str
    assets: tuple[VideoAsset, ...] = field(default_factory=tuple)
    static_portrait_cid: str = ""
    schema_version: int = VIDEO_MANIFEST_SCHEMA_VERSION
    generated_at: float = 0.0
    retention: VideoRetentionPolicy = field(default_factory=VideoRetentionPolicy)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "VideoManifest":
        version = int(payload.get("schema_version") or 0)
        if version != VIDEO_MANIFEST_SCHEMA_VERSION:
            raise ValueError(f"unsupported_video_manifest_schema:{version}")
        return cls(
            schema_version=version,
            agent_id=str(payload.get("agent_id") or ""),
            static_portrait_cid=str(payload.get("static_portrait_cid") or ""),
            generated_at=float(payload.get("generated_at") or 0.0),
            retention=VideoRetentionPolicy.from_dict(payload.get("retention")),
            assets=tuple(VideoAsset.from_dict(item) for item in payload.get("assets", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "agent_id": self.agent_id,
            "static_portrait_cid": self.static_portrait_cid,
            "generated_at": self.generated_at,
            "retention": self.retention.to_dict(),
            "assets": [asset.to_dict() for asset in self.assets],
        }


@dataclass(frozen=True)
class VideoSelection:
    """Deterministic observer-facing selection result."""

    asset: VideoAsset | None
    source: str
    url: str
    fallback_reason: str
    fallback_order: tuple[str, ...]
    cache_action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset": self.asset.to_dict() if self.asset else None,
            "source": self.source,
            "url": self.url,
            "fallback_reason": self.fallback_reason,
            "fallback_order": list(self.fallback_order),
            "cache_action": self.cache_action,
        }


def parse_video_manifest(payload: dict[str, Any]) -> VideoManifest:
    return VideoManifest.from_dict(payload)


def select_video_asset(
    manifest: VideoManifest,
    *,
    purpose: str = "live",
    expression: str = "neutral",
    motion: str = "idle",
    now: float = 0.0,
    cached_cids: set[str] | None = None,
    failed_cids: set[str] | None = None,
) -> VideoSelection:
    cached_cids = cached_cids or set()
    failed_cids = failed_cids or set()
    fallback_order = _fallback_order(purpose)
    candidates = [
        asset
        for asset in manifest.assets
        if _asset_is_selectable(asset, purpose=purpose, now=now, failed_cids=failed_cids)
    ]
    if candidates:
        selected = sorted(
            candidates,
            key=lambda asset: _asset_rank(
                asset,
                purpose=purpose,
                expression=expression,
                motion=motion,
                cached_cids=cached_cids,
            ),
        )[0]
        source = (
            "local_cache" if selected.local_cache_path or selected.cid in cached_cids else "ipfs"
        )
        return VideoSelection(
            asset=selected,
            source=source,
            url=selected.local_cache_path or f"/ipfs/{selected.cid}",
            fallback_reason="",
            fallback_order=fallback_order,
            cache_action="keep_hot" if selected.variant == VideoVariant.LOW_RES_LIVE else "durable",
        )

    reason = _fallback_reason(manifest, purpose=purpose, now=now, failed_cids=failed_cids)
    if manifest.static_portrait_cid:
        return VideoSelection(
            asset=None,
            source="static_portrait",
            url=f"/ipfs/{manifest.static_portrait_cid}",
            fallback_reason=reason,
            fallback_order=fallback_order,
            cache_action="none",
        )
    return VideoSelection(
        asset=None,
        source="none",
        url="",
        fallback_reason=reason,
        fallback_order=fallback_order,
        cache_action="none",
    )


def gc_candidate_cids(
    manifest: VideoManifest,
    *,
    now: float,
    policy: VideoRetentionPolicy | None = None,
) -> list[str]:
    policy = policy or manifest.retention
    candidates: list[VideoAsset] = []
    for asset in manifest.assets:
        expired = asset.is_expired(now)
        old_low_priority = (
            asset.created_at > 0
            and now - asset.created_at >= policy.max_age_seconds
            and asset.priority < policy.pin_priority_floor
        )
        keep_highlight = policy.keep_highlight_assets and asset.is_highlight
        if (expired or old_low_priority) and not keep_highlight:
            candidates.append(asset)
    candidates.sort(key=lambda asset: (asset.priority, asset.created_at, asset.asset_id))
    return [asset.cid for asset in candidates if asset.cid]


def cache_plan(
    manifest: VideoManifest,
    *,
    now: float,
    cached_cids: set[str] | None = None,
    policy: VideoRetentionPolicy | None = None,
) -> dict[str, list[str]]:
    cached_cids = cached_cids or set()
    policy = policy or manifest.retention
    keep_hot: list[str] = []
    evict: list[str] = []
    durable_only: list[str] = []
    for asset in manifest.assets:
        if not asset.cid:
            continue
        if asset.cid in gc_candidate_cids(manifest, now=now, policy=policy):
            evict.append(asset.cid)
        elif asset.variant == VideoVariant.LOW_RES_LIVE and not asset.is_expired(now):
            keep_hot.append(asset.cid)
        elif asset.cid in cached_cids:
            durable_only.append(asset.cid)
    return {"keep_hot": keep_hot, "evict": evict, "durable_only": durable_only}


def _fallback_order(purpose: str) -> tuple[str, ...]:
    if purpose == "highlight":
        return (
            "matching_high_res_highlight",
            "matching_low_res_live",
            "static_portrait",
            "none",
        )
    return (
        "matching_low_res_live",
        "neutral_low_res_live",
        "any_low_res_live",
        "static_portrait",
        "none",
    )


def _purpose_variants(purpose: str) -> tuple[VideoVariant, ...]:
    if purpose == "highlight":
        return (VideoVariant.HIGH_RES_HIGHLIGHT, VideoVariant.LOW_RES_LIVE)
    return (VideoVariant.LOW_RES_LIVE,)


def _asset_is_selectable(
    asset: VideoAsset,
    *,
    purpose: str,
    now: float,
    failed_cids: set[str],
) -> bool:
    if asset.status != VideoAssetStatus.READY:
        return False
    if asset.variant not in _purpose_variants(purpose):
        return False
    if asset.is_expired(now):
        return False
    if asset.cid in failed_cids and not asset.local_cache_path:
        return False
    return bool(asset.cid or asset.local_cache_path)


def _asset_rank(
    asset: VideoAsset,
    *,
    purpose: str,
    expression: str,
    motion: str,
    cached_cids: set[str],
) -> tuple[int, int, int, int, int, str]:
    variant_rank = _purpose_variants(purpose).index(asset.variant)
    expression_rank = (
        0 if asset.expression == expression else 1 if asset.expression == "neutral" else 2
    )
    motion_rank = 0 if asset.motion == motion else 1 if asset.motion == "idle" else 2
    cache_rank = 0 if asset.local_cache_path or asset.cid in cached_cids else 1
    return (variant_rank, expression_rank, motion_rank, cache_rank, -asset.priority, asset.asset_id)


def _fallback_reason(
    manifest: VideoManifest,
    *,
    purpose: str,
    now: float,
    failed_cids: set[str],
) -> str:
    relevant = [asset for asset in manifest.assets if asset.variant in _purpose_variants(purpose)]
    if not relevant:
        return "no_video_asset"
    if all(asset.cid in failed_cids and not asset.local_cache_path for asset in relevant):
        return "ipfs_retrieval_failed"
    if all(asset.is_expired(now) for asset in relevant):
        return "video_asset_expired"
    return "video_asset_unavailable"
