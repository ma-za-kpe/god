"""Focused regression tests for security hardening paths."""

from __future__ import annotations

import importlib.util
import os
import sys
import types
from pathlib import Path

import pytest

from tool_registry import _normalize_tool_cost


def _load_world_snapshot_module():
    src_dir = Path(os.getenv("RUNTIME_SRC_DIR", "/app/src"))
    if not src_dir.exists():
        src_dir = Path(__file__).resolve().parents[1] / "src"
    package = types.ModuleType("runtime_src")
    package.__path__ = [str(src_dir)]
    sys.modules.setdefault("runtime_src", package)
    spec = importlib.util.spec_from_file_location(
        "runtime_src.world_snapshot",
        src_dir / "world_snapshot.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["runtime_src.world_snapshot"] = module
    spec.loader.exec_module(module)
    return module


def test_last_dialogue_turn_uses_public_snapshot_messages():
    world_snapshot = _load_world_snapshot_module()
    private_candidate = {
        "message_id": "private",
        "body": "private direct message",
        "recipient_id": "agent-a",
    }
    public_message = {
        "message_id": "public",
        "body": "public broadcast",
        "recipient_id": "BROADCAST",
    }

    snapshot = world_snapshot._finalize_snapshot(
        agents=[],
        stats={},
        events=[],
        messages=[public_message],
        world_id="test-world",
    )

    assert snapshot["last_dialogue_turn"]["message_id"] == "public"
    assert snapshot["last_dialogue_turn"]["content"] == "public broadcast"
    assert snapshot["last_dialogue_turn"] != private_candidate


@pytest.mark.parametrize("bad_cost", [0, -0.01, float("inf"), float("nan")])
def test_tool_cost_rejects_non_positive_or_non_finite_values(bad_cost):
    with pytest.raises(ValueError):
        _normalize_tool_cost(bad_cost)


def test_tool_cost_accepts_positive_finite_value():
    assert _normalize_tool_cost(0.001234) == 0.001234
