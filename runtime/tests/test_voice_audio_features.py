"""Voice audio feature extraction tests."""

from __future__ import annotations

import io
import math
import struct
import wave

import pytest

from voice.audio_features import (
    analyze_audio_bytes,
    mouth_amplitude_from_audio,
    procedural_mouth_amplitude,
)


def _wav_bytes(*, amplitude: float = 0.5, seconds: float = 0.05, sample_rate: int = 8000) -> bytes:
    frames = int(sample_rate * seconds)
    with io.BytesIO() as buf:
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            for idx in range(frames):
                sample = int(32767 * amplitude * math.sin(2 * math.pi * 440 * idx / sample_rate))
                wav.writeframesraw(struct.pack("<h", sample))
        return buf.getvalue()


def test_analyze_wav_bytes_returns_rms_peak_duration_and_mouth_amplitude():
    features = analyze_audio_bytes(
        _wav_bytes(amplitude=0.5, seconds=0.1),
        content_type="audio/wav",
    )

    assert features.ok is True
    assert features.reason == "pcm_wav"
    assert features.duration_seconds == pytest.approx(0.1)
    assert features.sample_rate == 8000
    assert features.channels == 1
    assert features.sample_width == 2
    assert features.audio_rms == pytest.approx(0.353, abs=0.02)
    assert features.audio_peak == pytest.approx(0.5, abs=0.02)
    assert features.mouth_amplitude > features.audio_rms


def test_emotional_texture_increases_audio_mouth_amplitude():
    calm = mouth_amplitude_from_audio(0.2, 0.4, emotional_texture_score=0)
    charged = mouth_amplitude_from_audio(0.2, 0.4, emotional_texture_score=3)

    assert charged > calm


def test_procedural_mouth_amplitude_only_moves_when_speaking():
    quiet = procedural_mouth_amplitude(is_speaking=False, emotional_texture_score=3)
    calm = procedural_mouth_amplitude(is_speaking=True, emotional_texture_score=0)
    charged = procedural_mouth_amplitude(is_speaking=True, emotional_texture_score=3)

    assert quiet == 0.0
    assert calm > quiet
    assert charged > calm


def test_analyze_audio_bytes_rejects_unsupported_content_type():
    features = analyze_audio_bytes(b"not an mp3", content_type="audio/mpeg")

    assert features.ok is False
    assert features.reason == "unsupported_content_type"
