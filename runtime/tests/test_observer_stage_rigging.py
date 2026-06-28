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


def test_one_page_renders_voice_speaker_not_first_sorted_agent():
    html = _stage_html()

    assert "function pickSoloAgent(snap)" in html
    assert "return voiceSpeakerAgent(snap) || pickActiveAgent(snap);" in html
    assert (
        "const active = (soloMode ? pickSoloAgent(snap) : pickActiveAgent(snap)) || "
        "agents[0] || null;"
    ) in html
    assert (
        "const visibleAgents = soloMode ? (active ? [active] : []) : ordered.slice(0, 8);" in html
    )
    assert "ordered.slice(0, soloMode ? 1 : 8)" not in html


def test_one_page_has_deterministic_alphabet_drill():
    html = _stage_html()

    alphabet = "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z."
    assert f"const ONE_ALPHABET_LINE = '{alphabet}';" in html
    assert "const ONE_ALPHABET_NORMALIZED = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';" in html
    assert "function ensureOneAlphabetDrill(snap)" in html
    assert "move: 'alphabet_drill'" in html
    assert "document.body.dataset.oneAlphabetStatus" in html
    assert "setSpokenLineText(item.body, item.sender?.soul_id || '');" in html
