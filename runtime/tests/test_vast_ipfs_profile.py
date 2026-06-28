"""Vast native deployment IPFS profile tests."""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "scripts" / "vast-restart-services.sh").is_file():
            return candidate
    raise FileNotFoundError("repo root not found")


def test_vast_native_setup_uses_single_node_ipfs_profile():
    script = (_repo_root() / "scripts" / "vast-setup-native.sh").read_text(encoding="utf-8")

    assert "IPFS_API_ENDPOINTS=http://localhost:5001" in script
    assert "MIN_IPFS_PINS=1" in script
    assert "not Law-2" in script


def test_vast_restart_self_heals_single_node_ipfs_profile():
    script = (_repo_root() / "scripts" / "vast-restart-services.sh").read_text(encoding="utf-8")

    assert '"IPFS_API_ENDPOINTS": "http://localhost:5001"' in script
    assert '"MIN_IPFS_PINS": "1"' in script
    assert "not Law-2 durable replication" in script
    assert "write_vast_ipfs_env" in script
