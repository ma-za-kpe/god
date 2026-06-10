"""
wallet_store.py — Local-dev wallet key vault (never commit).

Stores agent private keys for on-chain actions during local development.
Production: replace with HSM / MPC / agent-owned key management.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

log = logging.getLogger("god.wallet_store")

STORE_PATH = Path(os.getenv("WALLET_STORE_PATH", "data/agent_wallets.json"))


def _load() -> dict:
    if not STORE_PATH.exists():
        return {}
    try:
        return json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning(f"wallet store read failed: {e}")
        return {}


def _save(data: dict) -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        os.chmod(STORE_PATH, 0o600)
    except OSError:
        pass


def store_wallet(soul_id: str, address: str, private_key: str) -> None:
    data = _load()
    data[soul_id] = {"address": address, "private_key": private_key}
    _save(data)


def get_agent_private_key(soul_id: str) -> str | None:
    entry = _load().get(soul_id)
    if not entry:
        return None
    return entry.get("private_key")
