"""Avatar video manifest and cache policy tests."""

from __future__ import annotations

import pytest

from avatar import (
    VIDEO_MANIFEST_SCHEMA_VERSION,
    VideoAsset,
    VideoManifest,
    VideoRetentionPolicy,
    VideoVariant,
    cache_plan,
    gc_candidate_cids,
    parse_video_manifest,
    select_video_asset,
)


def _asset(
    asset_id: str,
    cid: str,
    *,
    variant: VideoVariant = VideoVariant.LOW_RES_LIVE,
    expression: str = "neutral",
    motion: str = "idle",
    priority: int = 0,
    width: int = 640,
    height: int = 360,
    created_at: float = 100.0,
    expires_at: float | None = 1000.0,
    local_cache_path: str = "",
) -> VideoAsset:
    return VideoAsset(
        asset_id=asset_id,
        cid=cid,
        variant=variant,
        model="ltx" if variant == VideoVariant.LOW_RES_LIVE else "wan",
        width=width,
        height=height,
        duration_ms=5000,
        source_image_cid="portrait-cid",
        source_audio_cid="fish-audio-cid",
        expression=expression,
        motion=motion,
        priority=priority,
        created_at=created_at,
        expires_at=expires_at,
        local_cache_path=local_cache_path,
    )


def test_manifest_schema_represents_live_and_highlight_variants_without_legacy_overload():
    manifest = VideoManifest(
        agent_id="soul-1",
        static_portrait_cid="portrait-cid",
        assets=(
            _asset("talk-live", "cid-live", expression="animated", motion="talking"),
            _asset(
                "highlight",
                "cid-highlight",
                variant=VideoVariant.HIGH_RES_HIGHLIGHT,
                width=1920,
                height=1080,
                priority=90,
                expires_at=None,
            ),
        ),
    )

    payload = manifest.to_dict()
    parsed = parse_video_manifest(payload)

    assert payload["schema_version"] == VIDEO_MANIFEST_SCHEMA_VERSION
    assert {asset.variant for asset in parsed.assets} == {
        VideoVariant.LOW_RES_LIVE,
        VideoVariant.HIGH_RES_HIGHLIGHT,
    }
    assert parsed.assets[0].resolution == "640x360"
    assert parsed.assets[1].resolution == "1920x1080"
    assert "avatar_cid" not in payload
    assert "rigged_avatar_cid" not in payload
    assert "voice_model_cid" not in payload


def test_manifest_rejects_unknown_schema_version():
    with pytest.raises(ValueError, match="unsupported_video_manifest_schema"):
        parse_video_manifest({"schema_version": 99, "assets": []})


def test_live_selection_is_deterministic_and_prefers_cached_matching_loop():
    manifest = VideoManifest(
        agent_id="soul-1",
        static_portrait_cid="portrait-cid",
        assets=(
            _asset("neutral", "cid-neutral", priority=50),
            _asset(
                "talking-ipfs",
                "cid-talk-ipfs",
                expression="animated",
                motion="talking",
                priority=70,
            ),
            _asset(
                "talking-cache",
                "cid-talk-cache",
                expression="animated",
                motion="talking",
                priority=60,
                local_cache_path="/cache/talking.mp4",
            ),
            _asset(
                "highlight",
                "cid-highlight",
                variant=VideoVariant.HIGH_RES_HIGHLIGHT,
                width=1920,
                height=1080,
                priority=100,
            ),
        ),
    )

    selection = select_video_asset(
        manifest,
        purpose="live",
        expression="animated",
        motion="talking",
        now=200.0,
    )

    assert selection.asset is not None
    assert selection.asset.asset_id == "talking-cache"
    assert selection.source == "local_cache"
    assert selection.url == "/cache/talking.mp4"
    assert selection.fallback_order == (
        "matching_low_res_live",
        "neutral_low_res_live",
        "any_low_res_live",
        "static_portrait",
        "none",
    )


def test_ipfs_retrieval_failure_falls_back_to_static_portrait():
    manifest = VideoManifest(
        agent_id="soul-1",
        static_portrait_cid="portrait-cid",
        assets=(_asset("talking", "cid-talk", expression="animated", motion="talking"),),
    )

    selection = select_video_asset(
        manifest,
        purpose="live",
        expression="animated",
        motion="talking",
        now=200.0,
        failed_cids={"cid-talk"},
    )

    assert selection.asset is None
    assert selection.source == "static_portrait"
    assert selection.url == "/ipfs/portrait-cid"
    assert selection.fallback_reason == "ipfs_retrieval_failed"
    assert selection.cache_action == "none"


def test_ipfs_video_selection_uses_video_proxy_route():
    manifest = VideoManifest(
        agent_id="soul-1",
        static_portrait_cid="portrait-cid",
        assets=(
            _asset(
                "talking-ipfs",
                "cid-talk-ipfs",
                expression="animated",
                motion="talking",
                priority=70,
            ),
        ),
    )

    selection = select_video_asset(
        manifest,
        purpose="live",
        expression="animated",
        motion="talking",
        now=200.0,
    )

    assert selection.asset is not None
    assert selection.source == "ipfs"
    assert selection.url == "/ipfs/video/cid-talk-ipfs"


def test_expired_assets_are_skipped_with_static_fallback():
    manifest = VideoManifest(
        agent_id="soul-1",
        static_portrait_cid="portrait-cid",
        assets=(_asset("expired", "cid-expired", expires_at=150.0),),
    )

    selection = select_video_asset(manifest, purpose="live", now=200.0)

    assert selection.asset is None
    assert selection.source == "static_portrait"
    assert selection.fallback_reason == "video_asset_expired"


def test_retention_policy_marks_old_low_priority_cids_for_gc_but_keeps_highlights():
    policy = VideoRetentionPolicy(max_age_seconds=100, pin_priority_floor=50)
    manifest = VideoManifest(
        agent_id="soul-1",
        retention=policy,
        assets=(
            _asset("old-low", "cid-old-low", priority=10, created_at=0.0, expires_at=150.0),
            _asset("fresh", "cid-fresh", priority=10, created_at=180.0, expires_at=500.0),
            _asset(
                "highlight",
                "cid-highlight",
                variant=VideoVariant.HIGH_RES_HIGHLIGHT,
                priority=10,
                created_at=0.0,
                expires_at=150.0,
            ),
        ),
    )

    assert gc_candidate_cids(manifest, now=200.0) == ["cid-old-low"]
    assert cache_plan(manifest, now=200.0, cached_cids={"cid-highlight"}) == {
        "keep_hot": ["cid-fresh"],
        "evict": ["cid-old-low"],
        "durable_only": ["cid-highlight"],
    }
