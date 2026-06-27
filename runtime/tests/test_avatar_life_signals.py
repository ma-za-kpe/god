"""Procedural avatar life signal tests."""

from __future__ import annotations

import pytest

from avatar import LifeSignals, generate_life_state


def test_generate_life_state_is_deterministic_with_injected_time():
    first = generate_life_state(
        now=1.0,
        is_speaking=False,
        identity_key="beta",
        breath_speed_seconds=4.0,
        blink_interval_range=(2.0, 2.0),
        blink_duration_range=(0.2, 0.2),
    )
    second = generate_life_state(
        now=1.0,
        is_speaking=False,
        identity_key="beta",
        breath_speed_seconds=4.0,
        blink_interval_range=(2.0, 2.0),
        blink_duration_range=(0.2, 0.2),
    )

    assert first == second
    assert 0.0 <= first.breathing_phase <= 1.0
    assert -0.08 <= first.head_sway_x <= 0.08
    assert -0.05 <= first.head_sway_y <= 0.05
    assert first.mouth_amplitude == 0.0


def test_blink_state_uses_timestamp_window_without_randomness():
    blink = generate_life_state(
        now=2.05,
        is_speaking=False,
        identity_key="",
        blink_interval_range=(2.0, 2.0),
        blink_duration_range=(0.2, 0.2),
    )
    open_eye = generate_life_state(
        now=2.25,
        is_speaking=False,
        identity_key="",
        blink_interval_range=(2.0, 2.0),
        blink_duration_range=(0.2, 0.2),
    )

    assert blink.blink_state is True
    assert open_eye.blink_state is False


def test_mouth_amplitude_uses_audio_rms_and_speaking_fallback():
    driven = generate_life_state(now=10.0, is_speaking=True, audio_rms=0.25)
    clamped = generate_life_state(now=10.0, is_speaking=True, audio_rms=2.0)
    fallback = generate_life_state(now=10.0, is_speaking=True, audio_rms=0.0)
    listener = generate_life_state(now=10.0, is_speaking=False, audio_rms=0.8)

    assert driven.mouth_amplitude == pytest.approx(0.45)
    assert clamped.mouth_amplitude == 1.0
    assert fallback.mouth_amplitude > 0.0
    assert listener.mouth_amplitude == 0.0


def test_life_signals_class_keeps_last_state_for_runtime_shell():
    signals = LifeSignals(
        breath_speed_seconds=4.0,
        blink_interval_range=(2.0, 2.0),
        blink_duration_range=(0.2, 0.2),
    )

    state = signals.update(is_speaking=True, audio_rms=0.3, now=1.0, identity_key="alpha")

    assert signals.state == state
    assert state.mouth_amplitude == pytest.approx(0.54)
