"""Observer stage avatar rigging contract tests."""

from __future__ import annotations

import pathlib


def _stage_html() -> str:
    return (pathlib.Path(__file__).resolve().parents[2] / "observer" / "stage.html").read_text(
        encoding="utf-8"
    )


def test_stage_resolves_video_cids_through_video_proxy():
    html = _stage_html()

    assert "options.video ? 'video/' : ''" in html
    assert "ipfsUrl(source, { video: videoKind })" in html
    assert "mimeType.toLowerCase().startsWith('video/')" in html


def test_stage_marks_every_non_placeholder_avatar_as_rigged_host():
    html = _stage_html()

    assert "const isPlaceholder = agent.soul_id?.startsWith('empty-');" in html
    assert "const isRiggedHost = !isPlaceholder;" in html
    assert "data-rigged-avatar-host=\"${isRiggedHost ? '1' : '0'}\"" in html
    assert '${isRiggedHost ? \'<canvas class="rigged-avatar-canvas"' in html
