"""Static contracts for the React /one observer path."""

from __future__ import annotations

import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_react_one_page_selects_voice_speaker():
    world_map = _read("observer/src/components/WorldMap.jsx")

    assert "function speakerSoulIdFromSnapshot(snapshot, voicePlayback)" in world_map
    assert (
        "function activeAgentFor(agents, snapshot, selectedSoulId, voicePlayback, mode)"
        in world_map
    )
    assert "if (mode === 'one')" in world_map
    assert (
        "return agents.find((agent) => agent.soul_id === speakerSoulId) || agents[0] || null;"
        in world_map
    )
    assert (
        "const activeAgent = activeAgentFor(agents, snapshot, selectedSoulId, voicePlayback, mode);"
        in world_map
    )


def test_react_one_page_has_alphabet_caption_and_drill():
    app = _read("observer/src/App.jsx")
    hook = _read("observer/src/hooks/useWorld.js")
    store = _read("observer/src/store.js")
    styles = _read("observer/src/styles.css")

    alphabet = "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z."
    assert "currentSpokenLine" in store
    assert "oneAlphabetStatus" in store
    assert 'className="one-caption"' in app
    assert "data-one-alphabet-status={oneAlphabetStatus || 'waiting'}" in app
    assert alphabet in app
    assert f"const ONE_ALPHABET_LINE = '{alphabet}';" in hook
    assert "new URLSearchParams(window.location.search).get('runtime')" in hook
    assert "function ensureOneAlphabetDrill(snap)" in hook
    assert "new SpeechSynthesisUtterance(ONE_ALPHABET_LINE)" in hook
    assert ".one-caption" in styles
