"""Tests for x402 payment verification defaults and fallbacks."""

from __future__ import annotations

import importlib

import pytest

import services.payment as payment_module


def _reload_payment(monkeypatch, *, mock_env: str | None):
    if mock_env is None:
        monkeypatch.delenv("MOCK_X402_PAYMENTS", raising=False)
    else:
        monkeypatch.setenv("MOCK_X402_PAYMENTS", mock_env)
    return importlib.reload(payment_module)


def test_mock_mode_is_off_by_default(monkeypatch):
    payment = _reload_payment(monkeypatch, mock_env=None)
    assert payment.MOCK_PAYMENTS is False


@pytest.mark.asyncio
async def test_mock_mode_accepts_payment(monkeypatch):
    payment = _reload_payment(monkeypatch, mock_env="true")
    result = await payment.verify_payment("header", {"maxAmountRequired": "123"})

    assert result.is_valid is True
    assert result.transaction_hash == "0x" + "0" * 64
    assert result.amount_paid == "123"
    assert result.error == ""


@pytest.mark.asyncio
async def test_missing_header_is_rejected(monkeypatch):
    payment = _reload_payment(monkeypatch, mock_env=None)
    result = await payment.verify_payment("", {"maxAmountRequired": "123"})

    assert result.is_valid is False
    assert result.error == "missing X-Payment-Authorization header"


@pytest.mark.asyncio
async def test_production_path_fails_closed_without_sdk(monkeypatch):
    payment = _reload_payment(monkeypatch, mock_env=None)
    monkeypatch.setattr(
        payment,
        "_load_sdk_verifier",
        lambda: (_ for _ in ()).throw(ImportError()),
    )

    result = await payment.verify_payment("header", {"maxAmountRequired": "123"})

    assert result.is_valid is False
    assert result.error == "x402 SDK not installed"
