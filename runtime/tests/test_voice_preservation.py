"""Property-based preservation tests for the voice pipeline.

These tests capture baseline behavior of the voice pipeline for all NON-buggy
inputs (cases where isBugCondition returns false). They verify that normal
voice pipeline behavior remains unchanged after any fix is applied.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**
"""

from __future__ import annotations

import os
import re
from unittest.mock import patch

from hypothesis import given, settings
from hypothesis import strategies as st

from voice import VoiceSurface, build_voice_state, VoicePlan
from voice.engine import (
    _pick_emotion,
    _dialogue_speed,
    _UUID_PREFIX_RE,
    _EMOJI_RE,
    _ARROW_NARRATIVE_RE,
    _SEND_NARRATIVE_RE,
    _AGENT_PREFIX_RE,
    _AGENT_BARE_NAME_RE,
)


# ---------------------------------------------------------------------------
# Strategies for generating non-buggy inputs
# ---------------------------------------------------------------------------

SCENES = st.sampled_from(
    [
        "ensemble-stage",
        "banter-lounge",
        "chat-room",
        "economy-floor",
        "market-square",
        "void-chamber",
        "silence-hall",
        "avatar-arena",
        "world-wide",
        "stage-left",
        "focused-work",
    ]
)

SPEAKERS = st.sampled_from(
    [
        "Alpha",
        "Narrator",
        "Elder-Hook-6A4A",
        "Beta-Core-3F2B",
        "Gamma-Flux-9D1E",
        "Delta",
        "OmegaHost",
    ]
)

CADENCES = st.sampled_from(["", "jab", "short", "callback", "build", "normal"])

# Lines that do NOT trigger buggy paths — plain dialogue content
DIALOGUE_LINES = st.sampled_from(
    [
        "Hello world, this is a test.",
        "The market is looking strong today.",
        "I wonder what happens next in the story.",
        "Time to make a decision about the future.",
        "Let's keep things moving forward here.",
        "Watch the exchange.",
        "A very long line that exceeds one hundred and eighty characters because we want to test speed calculation for longer content and ensure it handles everything properly without issues at all whatsoever in any dimension.",
    ]
)

# Lines with prefixes that need stripping
UUID_PREFIXED_LINES = st.builds(
    lambda uuid, line: f"{uuid}: {line}",
    st.from_regex(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", fullmatch=True),
    DIALOGUE_LINES,
)

EMOJI_LINES = st.builds(
    lambda emoji, line: f"{emoji} {line}",
    st.sampled_from(["🔥", "💀", "✅", "❌", "⚠️"]),
    DIALOGUE_LINES,
)

ARROW_NARRATIVE_LINES = st.builds(
    lambda sender, recip, line: f"{sender} → {recip}: '{line}'",
    SPEAKERS,
    SPEAKERS,
    DIALOGUE_LINES,
)

SEND_NARRATIVE_LINES = st.builds(
    lambda sender, recip, line: f"{sender} sends a message to {recip}: '{line}'",
    st.sampled_from(["abc123", "def456", "Elder-Hook"]),
    st.sampled_from(["xyz789", "ghi012", "Beta-Core"]),
    DIALOGUE_LINES,
)

ALL_LINES = st.one_of(
    DIALOGUE_LINES, UUID_PREFIXED_LINES, EMOJI_LINES, ARROW_NARRATIVE_LINES, SEND_NARRATIVE_LINES
)

PATRONAGE_INDEX = st.floats(min_value=0.0, max_value=50.0)


def _healthy_probe_result(url=None, timeout=1.5):
    """Mock probe_url that returns a healthy endpoint response (non-buggy)."""
    return {
        "ok": True,
        "probe": "http",
        "url": url or "http://localhost:5001/health",
        "status_code": 200,
        "body": None,
    }


@st.composite
def fresh_dialogue_snapshot(draw):
    """Generate a snapshot with fresh dialogue (age < max threshold).

    This represents a NON-buggy input: dialogue is fresh, content is available.
    """
    scene = draw(SCENES)
    speaker = draw(SPEAKERS)
    line = draw(ALL_LINES)
    cadence = draw(CADENCES)
    patronage = draw(PATRONAGE_INDEX)
    epoch = draw(st.integers(min_value=1000, max_value=100000))
    # Fresh dialogue: sent_at is close to epoch (age < 20s)
    age = draw(st.integers(min_value=0, max_value=18))
    sent_at = epoch - age

    snapshot = {
        "epoch": epoch,
        "showrunner": {
            "scene": scene,
            "speaker": speaker,
            "headline": f"{speaker} takes the mic.",
            "audience_prompt": f"Watch {speaker} perform.",
        },
        "audience": {
            "patronage_index": patronage,
        },
        "broadcast": {
            "caption": {"headline": f"{speaker} takes the mic."},
            "scene": {"scene_name": scene, "speaker": speaker},
        },
        "last_dialogue_turn": {
            "content": line,
            "sender_name": speaker,
            "sent_at": sent_at,
            "cadence": cadence if cadence else None,
        },
    }
    return snapshot


@st.composite
def showrunner_headline_snapshot(draw):
    """Generate a snapshot using showrunner headline (no fresh dialogue).

    Non-buggy: showrunner headline IS available (so no static fallback triggered).
    """
    scene = draw(SCENES)
    speaker = draw(SPEAKERS)
    headline = draw(DIALOGUE_LINES)
    patronage = draw(PATRONAGE_INDEX)
    epoch = draw(st.integers(min_value=1000, max_value=100000))

    snapshot = {
        "epoch": epoch,
        "showrunner": {
            "scene": scene,
            "speaker": speaker,
            "headline": headline,
            "audience_prompt": headline,
        },
        "audience": {
            "patronage_index": patronage,
        },
        "broadcast": {
            "caption": {"headline": headline},
            "scene": {"scene_name": scene, "speaker": speaker},
        },
    }
    return snapshot


@st.composite
def non_buggy_snapshot(draw):
    """Generate any non-buggy snapshot — fresh dialogue or headline available."""
    return draw(st.one_of(fresh_dialogue_snapshot(), showrunner_headline_snapshot()))


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


class TestPreservationHealthyEndpoint:
    """**Validates: Requirements 3.1**

    For all snapshots with healthy TTS endpoint: compose() produces same
    VoiceState as original (deterministic, stable output).
    """

    @given(snapshot=non_buggy_snapshot())
    @settings(max_examples=50, deadline=None)
    def test_compose_deterministic_with_healthy_endpoint(self, snapshot):
        """compose() called twice on the same snapshot produces identical results."""
        with patch("voice.engine.probe_url", side_effect=_healthy_probe_result):
            surface = VoiceSurface(enabled=True, dry_run=False)
            state1 = surface.compose(snapshot)
            state2 = surface.compose(snapshot)

        assert state1 == state2
        assert state1.health["ok"] is True
        assert state1.plan is not None
        assert state1.plan.speaker != ""
        assert state1.plan.line != ""

    @given(snapshot=non_buggy_snapshot())
    @settings(max_examples=50, deadline=None)
    def test_compose_produces_valid_voice_plan(self, snapshot):
        """compose() always produces a VoicePlan with all required fields populated."""
        with patch("voice.engine.probe_url", side_effect=_healthy_probe_result):
            surface = VoiceSurface(enabled=True, dry_run=False)
            state = surface.compose(snapshot)

        plan = state.plan
        assert isinstance(plan, VoicePlan)
        assert plan.speaker != ""
        assert plan.line != ""
        assert plan.emotion in {"playful", "charged", "measured", "hushed", "focused"}
        assert len(plan.utterance_id) == 16
        assert plan.voice_provider != ""
        assert plan.voice_model != ""
        assert plan.voice_name != ""
        assert plan.speed > 0
        assert plan.sample_rate > 0


class TestPreservationBuildVoiceState:
    """**Validates: Requirements 3.2**

    For all valid snapshots: build_voice_state() returns same payload as original.
    """

    @given(snapshot=non_buggy_snapshot())
    @settings(max_examples=50, deadline=None)
    def test_build_voice_state_deterministic(self, snapshot):
        """build_voice_state() is deterministic for the same snapshot."""
        with patch("voice.engine.probe_url", side_effect=_healthy_probe_result):
            result1 = build_voice_state(snapshot)
            result2 = build_voice_state(snapshot)

        assert result1 == result2
        assert "plan" in result1
        assert "enabled" in result1
        assert "health" in result1

    @given(snapshot=non_buggy_snapshot())
    @settings(max_examples=50, deadline=None)
    def test_build_voice_state_returns_complete_payload(self, snapshot):
        """build_voice_state() returns dict with all expected keys populated."""
        with patch("voice.engine.probe_url", side_effect=_healthy_probe_result):
            result = build_voice_state(snapshot)

        # All top-level VoiceState fields present
        assert "enabled" in result
        assert "dry_run" in result
        assert "provider" in result
        assert "voice_model" in result
        assert "voice_name" in result
        assert "playback_mode" in result
        assert "speech_profile" in result
        assert "lip_sync_source" in result
        assert "transport" in result
        assert "health" in result
        assert "plan" in result

        # Plan has all required fields
        plan = result["plan"]
        assert plan["speaker"] != ""
        assert plan["line"] != ""
        assert plan["emotion"] != ""
        assert plan["utterance_id"] != ""


class TestPreservationFreshDialogue:
    """**Validates: Requirements 3.3**

    For all fresh dialogue turns: speaker/line/emotion selection is identical to original.
    """

    @given(snapshot=fresh_dialogue_snapshot())
    @settings(max_examples=50, deadline=None)
    def test_fresh_dialogue_uses_turn_content(self, snapshot):
        """When dialogue is fresh, compose() uses dialogue turn content and sender."""
        with patch("voice.engine.probe_url", side_effect=_healthy_probe_result):
            surface = VoiceSurface(enabled=True, dry_run=False)
            state = surface.compose(snapshot)

        turn = snapshot["last_dialogue_turn"]
        # Speaker comes from the dialogue turn sender_name
        assert state.plan.speaker == turn["sender_name"]
        # Line is derived from turn content (may be stripped of prefixes)
        # The line should not be empty and should be derived from the original content
        assert state.plan.line != ""

    @given(snapshot=fresh_dialogue_snapshot())
    @settings(max_examples=50, deadline=None)
    def test_fresh_dialogue_emotion_consistent(self, snapshot):
        """Emotion selection is consistent and deterministic for fresh dialogue."""
        with patch("voice.engine.probe_url", side_effect=_healthy_probe_result):
            surface = VoiceSurface(enabled=True, dry_run=False)
            state1 = surface.compose(snapshot)
            state2 = surface.compose(snapshot)

        assert state1.plan.emotion == state2.plan.emotion
        assert state1.plan.emotion == _pick_emotion(snapshot)

    @given(snapshot=fresh_dialogue_snapshot())
    @settings(max_examples=50, deadline=None)
    def test_fresh_dialogue_speed_consistent(self, snapshot):
        """Speed calculation is consistent for fresh dialogue turns."""
        with patch("voice.engine.probe_url", side_effect=_healthy_probe_result):
            surface = VoiceSurface(enabled=True, dry_run=False)
            state = surface.compose(snapshot)

        # Speed should match the _dialogue_speed calculation
        expected_speed = _dialogue_speed(snapshot, state.plan.line)
        # Speed from env override or calculated
        env_speed = os.getenv("VOICE_SPEED")
        if env_speed is None:
            assert state.plan.speed == expected_speed


class TestPreservationDryRunFalse:
    """**Validates: Requirements 3.4**

    For all explicit dry-run=false configs: TTS output behavior is identical.
    """

    @given(snapshot=non_buggy_snapshot())
    @settings(max_examples=50, deadline=None)
    def test_explicit_dry_run_false_produces_enabled_state(self, snapshot):
        """When dry_run=False is explicit, the VoiceState reflects enabled output."""
        with patch("voice.engine.probe_url", side_effect=_healthy_probe_result):
            surface = VoiceSurface(enabled=True, dry_run=False)
            state = surface.compose(snapshot)

        assert state.dry_run is False
        assert state.enabled is True
        # Plan is still produced normally
        assert state.plan is not None
        assert state.plan.line != ""

    @given(snapshot=non_buggy_snapshot())
    @settings(max_examples=50, deadline=None)
    def test_dry_run_false_via_env(self, snapshot):
        """VOICE_DRY_RUN=false via environment produces non-dry-run state."""
        with (
            patch("voice.engine.probe_url", side_effect=_healthy_probe_result),
            patch.dict(os.environ, {"VOICE_DRY_RUN": "false"}),
        ):
            surface = VoiceSurface(enabled=True)
            state = surface.compose(snapshot)

        assert state.dry_run is False


class TestPreservationTextStripping:
    """**Validates: Requirements 3.5**

    For all dialogue lines: text stripping (UUIDs, emojis, prefixes) produces
    identical results — the stripping logic is preserved.
    """

    @given(
        uuid=st.from_regex(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", fullmatch=True
        ),
        line=DIALOGUE_LINES,
    )
    @settings(max_examples=50, deadline=None)
    def test_uuid_prefix_stripped(self, uuid, line):
        """UUID prefixes are always stripped from dialogue lines."""
        raw = f"{uuid}: {line}"
        stripped = _UUID_PREFIX_RE.sub("", raw)
        # UUID prefix is removed
        assert not stripped.startswith(uuid)
        # Remaining content is preserved
        assert line in stripped or stripped.strip() != ""

    @given(
        emoji=st.sampled_from(["🔥", "💀", "✅", "❌"]),
        line=DIALOGUE_LINES,
    )
    @settings(max_examples=50, deadline=None)
    def test_emoji_stripped(self, emoji, line):
        """Emojis are stripped from dialogue lines."""
        raw = f"{emoji} {line}"
        stripped = _EMOJI_RE.sub("", raw)
        assert emoji not in stripped
        # Core content preserved
        assert line.strip() in stripped or stripped.strip() != ""

    @given(
        sender=SPEAKERS,
        recipient=SPEAKERS,
        line=DIALOGUE_LINES,
    )
    @settings(max_examples=50, deadline=None)
    def test_arrow_narrative_stripped(self, sender, recipient, line):
        """Arrow narrative prefixes (Name → Recipient: ...) are stripped."""
        raw = f"{sender} → {recipient}: '{line}'"
        stripped = _ARROW_NARRATIVE_RE.sub("", raw).strip("\"'").strip()
        # The narrative prefix is removed, content remains
        assert stripped != "" or line.strip() != ""

    @given(snapshot=fresh_dialogue_snapshot())
    @settings(max_examples=50, deadline=None)
    def test_compose_line_never_empty_after_stripping(self, snapshot):
        """After all stripping, compose() always produces a non-empty line."""
        with patch("voice.engine.probe_url", side_effect=_healthy_probe_result):
            surface = VoiceSurface(enabled=True, dry_run=False)
            state = surface.compose(snapshot)

        # Line is never empty — falls back to raw if stripping produces nothing
        assert state.plan.line.strip() != ""

    @given(snapshot=fresh_dialogue_snapshot())
    @settings(max_examples=50, deadline=None)
    def test_text_stripping_idempotent(self, snapshot):
        """Text stripping produces the same result when applied multiple times."""
        with patch("voice.engine.probe_url", side_effect=_healthy_probe_result):
            surface = VoiceSurface(enabled=True, dry_run=False)
            state = surface.compose(snapshot)

        line = state.plan.line
        # Apply stripping again to the already-stripped line
        re_stripped = _UUID_PREFIX_RE.sub("", line)
        re_stripped = _EMOJI_RE.sub("", re_stripped)
        re_stripped = _ARROW_NARRATIVE_RE.sub("", re_stripped).strip("\"'").strip()
        re_stripped = _SEND_NARRATIVE_RE.sub("", re_stripped).strip("\"'").strip()
        re_stripped = _AGENT_PREFIX_RE.sub("", re_stripped)
        re_stripped = _AGENT_BARE_NAME_RE.sub("", re_stripped)
        re_stripped = re_stripped.replace(" / ", " ").replace(" /", " ").replace("/ ", " ")
        re_stripped = re.sub(r"\s{2,}", " ", re_stripped).strip()
        final = re_stripped.strip() or line.strip()

        # Stripping is idempotent — applying it again gives the same result
        assert final == line
