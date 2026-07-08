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


def test_react_one_page_has_alphabet_caption_and_tts_audio_gate():
    app = _read("observer/src/App.jsx")
    avatar = _read("observer/src/components/AgentAvatar.jsx")
    rig = _read("observer/src/components/ControlledAvatar.jsx")
    hook = _read("observer/src/hooks/useWorld.js")
    lip_sync = _read("observer/src/lipSync.js")
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
    assert "startVoicePlayback(playback, audioUrl, {" in hook
    assert "transport: 'runtime-tts+rigged-avatar'" in hook
    assert "startVoiceMeterFromAnalyser" in hook
    assert "audioRmsFromAnalyser" in hook
    assert "audio_analyser+viseme_track" in hook
    assert "startOneAlphabetPlaybackWhenVideoReady" not in hook
    assert "waitForLiveVideo" not in hook
    assert "fish-audio+live-video" not in hook
    assert "waiting-for-live-video" not in hook
    assert "} else if (!uid || !synthOk) {" in hook
    assert "waiting-for-tts-audio" in hook
    assert "waiting-for-alphabet-line" in hook
    assert "speechSynthesis" not in hook
    assert "ensureOneAlphabetDrill" not in hook
    assert "ensureOneAlphabetVisualLoop" not in hook
    assert "fish-audio-loop" not in hook
    assert "visual-drill" not in hook
    assert "} else if (uid && synthOk && uid !== _lastPlayedUtteranceId) {" in hook
    assert ".one-caption" in styles
    assert "import { ControlledAvatar } from './ControlledAvatar';" in avatar
    assert "if (props.minimal)" in avatar
    assert "return <ControlledAvatar {...props} />;" in avatar
    assert "buildAlphabetVisemeTrack" in rig
    assert "sampleVisemeTrack" in rig
    assert "const kind = vrmUrl ? 'vrm-rig' : 'procedural-rig';" in rig
    assert 'data-avatar-control-mode="speech-driven-rig"' in rig
    assert 'data-avatar-video-mode="disabled-for-one"' in rig
    assert "VRMLoaderPlugin" in rig
    assert "expressionManager" in rig
    assert "buildAlphabetVisemeTrack(line, durationSeconds = 0)" in lip_sync
    assert "while (lower <= upper)" in lip_sync
    assert "const frameWidth = 170;" in avatar
    assert "const frameHeight = 210;" in avatar
    assert "--speak-bar-peak" in styles


def test_react_one_page_uses_controllable_rig_not_bundled_video():
    avatar = _read("observer/src/components/AgentAvatar.jsx")
    rig = _read("observer/src/components/ControlledAvatar.jsx")
    hook = _read("observer/src/hooks/useWorld.js")
    asset = ROOT / "observer/assets/one-avatar-loop.mp4"

    assert not asset.exists()
    assert "one-avatar-loop.mp4" not in avatar
    assert "one-avatar-loop.mp4" not in rig
    assert "one-avatar-loop.mp4" not in hook
    assert "bundledOneLoopUrl" not in avatar
    assert "bundledOneLoopUrl" not in rig
    assert "const videoCandidate = minimal" not in avatar
    assert 'data-live-lip-renderer-status="not-required"' in rig
    assert 'data-avatar-control-mode="speech-driven-rig"' in rig
    assert 'data-avatar-video-mode="disabled-for-one"' in rig
    assert "procedural-speech-controlled" in rig
    assert "vrm-speech-controlled" in rig
    assert "createMediaElementSource(audio)" in hook
    assert "const snapshotSpeakerActive = Boolean(" in avatar
    assert "browserPlaybackActive" in avatar
    assert "if (props.minimal)" in avatar
    assert "return <ControlledAvatar {...props} />;" in avatar
    assert "const frameWidth = 170;" in avatar
    assert "const frameHeight = 210;" in avatar
    assert "const showProceduralMouth = !showVideo;" in avatar
    assert "hidden={!showProceduralMouth}" in avatar
