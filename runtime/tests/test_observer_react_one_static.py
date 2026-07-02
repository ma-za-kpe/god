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


def test_react_one_page_has_alphabet_caption_and_fish_audio_gate():
    app = _read("observer/src/App.jsx")
    avatar = _read("observer/src/components/AgentAvatar.jsx")
    hook = _read("observer/src/hooks/useWorld.js")
    store = _read("observer/src/store.js")
    styles = _read("observer/src/styles.css")

    alphabet = "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z."
    assert "currentSpokenLine" in store
    assert "oneAlphabetStatus" in store
    assert 'className="one-caption"' in app
    assert "data-one-alphabet-status={oneAlphabetStatus || 'waiting'}" in app
    assert alphabet in app
    assert "new URLSearchParams(window.location.search).get('runtime')" in hook
    assert "if (oneAlphabetEnabled()) {" in hook
    assert "if (uid && synthOk && uid !== _lastPlayedUtteranceId)" in hook
    assert "const playback = playbackContextFromSnapshot(snap);" in hook
    assert "const audioUrl = resolveVoiceAudioUrl(snap?.voice?.synthesis?.audio_url, uid);" in hook
    assert "const liveVideoUrl = liveVideoUrlFromSnapshot(snap);" in hook
    assert "startOneAlphabetPlaybackWhenVideoReady({" in hook
    assert "waitForLiveVideo(liveVideoUrl)" in hook
    assert "markVoicePlayback('waiting-for-live-video', playback" in hook
    assert "transport: 'fish-audio+live-video'" in hook
    assert "} else if (!uid || !synthOk) {" in hook
    assert "waiting-for-fish-audio" in hook
    assert "waiting-for-live-video" in hook
    assert "waiting-for-alphabet-line" in hook
    assert "speechSynthesis" not in hook
    assert "ensureOneAlphabetDrill" not in hook
    assert "ensureOneAlphabetVisualLoop" not in hook
    assert "fish-audio-loop" not in hook
    assert "visual-drill" not in hook
    assert "} else if (uid && synthOk && uid !== _lastPlayedUtteranceId) {" in hook
    assert ".one-caption" in styles
    assert "const frameWidth = minimal ? 640 : 170;" in avatar
    assert "const frameHeight = minimal ? 360 : 210;" in avatar
    assert "--speak-bar-peak" in styles


def test_react_one_page_requires_live_lip_renderer_not_bundled_video():
    avatar = _read("observer/src/components/AgentAvatar.jsx")
    asset = ROOT / "observer/assets/one-avatar-loop.mp4"

    assert not asset.exists()
    assert "one-avatar-loop.mp4" not in avatar
    assert "bundledOneLoopUrl" not in avatar
    assert (
        "const videoCandidate = minimal && avatarSource.video?.kind !== 'live' ? null : avatarSource.video;"
        in avatar
    )
    assert "const liveLipRendererStatus = minimal" in avatar
    assert "data-live-lip-renderer-status={liveLipRendererStatus}" in avatar
    assert "const isLiveVideo = videoKind === 'live';" in avatar
    assert "autoPlay={!isLiveVideo}" in avatar
    assert "if (videoKind !== 'loop' && videoKind !== 'live') setVideoReady(false);" in avatar
    assert "const frameWidth = minimal ? 640 : 170;" in avatar
    assert "const frameHeight = minimal ? 360 : 210;" in avatar
    assert "const showProceduralMouth = !minimal && !showVideo;" in avatar
    assert "hidden={!showProceduralMouth}" in avatar
