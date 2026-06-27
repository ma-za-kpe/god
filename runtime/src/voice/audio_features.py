"""Audio feature extraction for live mouth driving."""

from __future__ import annotations

import io
import math
import wave
from dataclasses import asdict, dataclass


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, float(value)))


@dataclass(frozen=True)
class AudioFeatures:
    ok: bool
    reason: str
    audio_rms: float = 0.0
    audio_peak: float = 0.0
    mouth_amplitude: float = 0.0
    duration_seconds: float = 0.0
    sample_rate: int = 0
    channels: int = 0
    sample_width: int = 0

    def to_dict(self) -> dict[str, float | int | bool | str]:
        return asdict(self)


def mouth_amplitude_from_audio(
    audio_rms: float,
    audio_peak: float = 0.0,
    *,
    emotional_texture_score: int = 0,
) -> float:
    """Map normalized RMS/peak energy to a conservative mouth-open value."""
    rms = _clamp(audio_rms)
    peak = _clamp(audio_peak)
    if rms <= 0.0 and peak <= 0.0:
        return 0.0
    texture_boost = _clamp(emotional_texture_score / 3.0, 0.0, 1.0) * 0.14
    return _clamp((rms * 1.85) + (peak * 0.22) + texture_boost, 0.05, 1.0)


def procedural_mouth_amplitude(
    *,
    is_speaking: bool,
    emotional_texture_score: int = 0,
) -> float:
    """Fallback mouth motion when audio analysis is unavailable."""
    if not is_speaking:
        return 0.0
    texture_boost = _clamp(emotional_texture_score / 3.0, 0.0, 1.0) * 0.16
    return _clamp(0.32 + texture_boost, 0.0, 0.62)


def _sample_value(chunk: bytes, sample_width: int) -> float:
    if sample_width == 1:
        return (chunk[0] - 128) / 128.0
    if sample_width == 2:
        return int.from_bytes(chunk, "little", signed=True) / 32768.0
    if sample_width == 3:
        extended = chunk + (b"\xff" if chunk[-1] & 0x80 else b"\x00")
        return int.from_bytes(extended, "little", signed=True) / 8388608.0
    if sample_width == 4:
        return int.from_bytes(chunk, "little", signed=True) / 2147483648.0
    raise ValueError(f"unsupported_sample_width:{sample_width}")


def analyze_wav_bytes(
    audio_bytes: bytes,
    *,
    emotional_texture_score: int = 0,
) -> AudioFeatures:
    """Return normalized RMS/peak and mouth amplitude for PCM WAV bytes."""
    if not audio_bytes:
        return AudioFeatures(ok=False, reason="empty_audio")

    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wav:
            channels = int(wav.getnchannels())
            sample_width = int(wav.getsampwidth())
            sample_rate = int(wav.getframerate())
            frame_count = int(wav.getnframes())
            frames = wav.readframes(frame_count)
    except Exception as exc:
        return AudioFeatures(ok=False, reason=f"wav_parse_failed:{type(exc).__name__}")

    if channels <= 0 or sample_rate <= 0 or frame_count <= 0:
        return AudioFeatures(ok=False, reason="empty_wav")
    if sample_width not in {1, 2, 3, 4}:
        return AudioFeatures(ok=False, reason=f"unsupported_sample_width:{sample_width}")

    total = 0.0
    peak = 0.0
    samples = 0
    step = sample_width
    for offset in range(0, len(frames) - (len(frames) % step), step):
        value = _sample_value(frames[offset : offset + step], sample_width)
        abs_value = abs(value)
        total += value * value
        peak = max(peak, abs_value)
        samples += 1

    if samples <= 0:
        return AudioFeatures(ok=False, reason="empty_pcm")

    rms = math.sqrt(total / samples)
    duration_seconds = frame_count / sample_rate
    return AudioFeatures(
        ok=True,
        reason="pcm_wav",
        audio_rms=round(_clamp(rms), 6),
        audio_peak=round(_clamp(peak), 6),
        mouth_amplitude=round(
            mouth_amplitude_from_audio(
                rms,
                peak,
                emotional_texture_score=emotional_texture_score,
            ),
            6,
        ),
        duration_seconds=round(duration_seconds, 6),
        sample_rate=sample_rate,
        channels=channels,
        sample_width=sample_width,
    )


def analyze_audio_bytes(
    audio_bytes: bytes,
    *,
    content_type: str = "",
    emotional_texture_score: int = 0,
) -> AudioFeatures:
    """Analyze supported synthesized audio bytes without requiring model services."""
    normalized_type = str(content_type or "").lower()
    if normalized_type and "wav" not in normalized_type and not audio_bytes.startswith(b"RIFF"):
        return AudioFeatures(ok=False, reason="unsupported_content_type")
    return analyze_wav_bytes(
        audio_bytes,
        emotional_texture_score=emotional_texture_score,
    )
