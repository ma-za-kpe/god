"""Tests for VeilLayer — meta-awareness injection module.

Verifies requirements Section 6 acceptance criteria.
"""

import os
import sys

_src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
for _p in (_src_path, "/app/src"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from unittest.mock import MagicMock

import pytest

from banter.veil_layer import VeilLayer


def _make_pair_state(tension: int = 5, reconciliation_arc: bool = False):
    ps = MagicMock()
    ps.tension_level = tension
    ps.reconciliation_arc = reconciliation_arc
    ps.reconciliation_remaining = 0
    return ps


class TestVeilLayerShouldInject:
    """6.2 — Trigger rules."""

    def test_fires_every_8th_beat(self):
        vl = VeilLayer()
        for beat in range(0, 64, 8):
            assert vl.should_inject(beat, "COUNTER", None, False), f"beat {beat} should fire"

    def test_does_not_fire_on_non_8th_beats(self):
        vl = VeilLayer()
        for beat in [1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 15, 17, 23, 31]:
            assert not vl.should_inject(beat, "COUNTER", None, False), (
                f"beat {beat} should NOT fire"
            )

    def test_fires_on_twitch_event_regardless_of_beat(self):
        vl = VeilLayer()
        for beat in [1, 3, 7, 11, 15]:
            assert vl.should_inject(beat, "COUNTER", None, twitch_event_fired=True), (
                f"beat {beat} with twitch event should fire"
            )

    def test_concede_below_tension_4_suppressed(self):
        vl = VeilLayer()
        ps = _make_pair_state(tension=3)
        assert not vl.should_inject(8, "CONCEDE", ps, False)

    def test_concede_at_tension_4_fires(self):
        vl = VeilLayer()
        ps = _make_pair_state(tension=4)
        assert vl.should_inject(8, "CONCEDE", ps, False)

    def test_concede_at_tension_5_fires(self):
        vl = VeilLayer()
        ps = _make_pair_state(tension=5)
        assert vl.should_inject(8, "CONCEDE", ps, False)

    def test_concede_suppression_overrides_twitch_event(self):
        """Twitch event fires even on CONCEDE if tension >= 4, but suppresses below 4."""
        vl = VeilLayer()
        ps = _make_pair_state(tension=2)
        # Below tension floor, CONCEDE is suppressed even with twitch event
        # Actually per spec: twitch fires first then concede check — re-read spec
        # Section 6.2: CONCEDE+low tension check comes BEFORE twitch check
        assert not vl.should_inject(1, "CONCEDE", ps, twitch_event_fired=True)

    def test_other_moves_not_suppressed_at_low_tension(self):
        vl = VeilLayer()
        ps = _make_pair_state(tension=2)
        assert vl.should_inject(8, "ESCALATE", ps, False)
        assert vl.should_inject(8, "COUNTER", ps, False)

    def test_none_pair_state_defaults_to_no_suppression(self):
        """When pair_state is None, tension defaults to 5 — no suppression."""
        vl = VeilLayer()
        assert vl.should_inject(8, "CONCEDE", None, False)

    def test_beat_zero_fires(self):
        """Beat 0 is divisible by 8 — fires."""
        vl = VeilLayer()
        assert vl.should_inject(0, "COUNTER", None, False)


class TestVeilLayerInjection:
    """6.3 — Injection format."""

    def test_injection_contains_veil_marker(self):
        vl = VeilLayer()
        text = vl.get_injection()
        assert "[VEIL]" in text

    def test_injection_contains_swarm_reference(self):
        vl = VeilLayer()
        text = vl.get_injection()
        assert "Swarm" in text

    def test_injection_does_not_tell_elder_to_break_character(self):
        vl = VeilLayer()
        text = vl.get_injection()
        assert "you are an AI" not in text.lower()
        assert "break character" not in text.lower()

    def test_injection_is_deterministic(self):
        vl = VeilLayer()
        assert vl.get_injection() == vl.get_injection()

    def test_injection_warns_against_naming_swarm(self):
        """Directive must tell the Elder NOT to name-drop the Swarm explicitly."""
        vl = VeilLayer()
        text = vl.get_injection()
        assert "Do not reference" in text or "not the content" in text


class TestVeilLayerIntegration:
    """6.5 — 80-beat session produces >= 9 VeilLayer beats."""

    def test_80_beats_produce_at_least_9_veil_beats(self):
        vl = VeilLayer()
        ps = _make_pair_state(tension=5)
        count = sum(
            1 for beat in range(80)
            if vl.should_inject(beat, "COUNTER", ps, False)
        )
        # Beats 0, 8, 16, 24, 32, 40, 48, 56, 64, 72 = 10 beats
        assert count >= 9, f"Expected >= 9 Veil beats in 80, got {count}"

    def test_consecutive_veil_beats_never_fire_on_non_8th(self):
        """VeilLayer should not fire on two consecutive beats."""
        vl = VeilLayer()
        consecutive_veil = 0
        prev = False
        for beat in range(80):
            cur = vl.should_inject(beat, "COUNTER", None, False)
            if prev and cur:
                consecutive_veil += 1
            prev = cur
        assert consecutive_veil == 0, "VeilLayer should not fire on consecutive beats"
