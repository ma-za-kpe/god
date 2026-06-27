"""Service route payment binding tests."""

from __future__ import annotations

import importlib
import os
import sys
import types
from pathlib import Path


def _load_routes_module():
    src_dir = Path(os.getenv("RUNTIME_SRC_DIR", "/app/src"))
    if not src_dir.exists():
        src_dir = Path(__file__).resolve().parents[1] / "src"
    package = types.ModuleType("runtime_src")
    package.__path__ = [str(src_dir)]
    sys.modules.setdefault("runtime_src", package)
    return importlib.import_module("runtime_src.services.routes")


def _result(**overrides):
    payment_module = importlib.import_module("runtime_src.services.payment")
    data = {
        "is_valid": True,
        "transaction_hash": "0xabc",
        "amount_paid": "1000",
        "resource": "http://runtime/services/s1/world_stats",
        "pay_to": "0xpayee",
        "network": "base-sepolia",
        "asset": "0xasset",
    }
    data.update(overrides)
    return payment_module.PaymentResult(**data)


def test_payment_match_requires_bound_network_and_asset(monkeypatch):
    routes_module = _load_routes_module()
    monkeypatch.setattr(routes_module, "MOCK_PAYMENTS", False)
    config = {
        "maxAmountRequired": "1000",
        "resource": "http://runtime/services/s1/world_stats",
        "payTo": "0xpayee",
        "network": "base-sepolia",
        "asset": "0xasset",
    }

    assert routes_module._payment_matches_requirement(_result(), config)
    assert not routes_module._payment_matches_requirement(_result(network=""), config)
    assert not routes_module._payment_matches_requirement(_result(asset=""), config)
    assert not routes_module._payment_matches_requirement(_result(resource=""), config)
    assert not routes_module._payment_matches_requirement(_result(pay_to=""), config)
