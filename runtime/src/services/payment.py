"""
payment.py — x402 payment verification.

Local dev: set MOCK_X402_PAYMENTS=true to accept test payments without on-chain verification.
Production: leave MOCK_X402_PAYMENTS unset or false so verification fails closed unless
the x402 SDK and chain-backed payment path are available.
"""

import logging
import os
from dataclasses import dataclass

log = logging.getLogger("god.services.payment")

MOCK_PAYMENTS = os.getenv("MOCK_X402_PAYMENTS", "false").lower() in {"1", "true", "yes", "on"}
USDC_BASE_SEPOLIA = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
USDC_BASE_MAINNET = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
NETWORK = os.getenv("CHAIN_NETWORK", "base-sepolia")


@dataclass
class PaymentResult:
    is_valid: bool
    transaction_hash: str
    amount_paid: str
    error: str = ""


def _result_value(result: object, key: str, default: str = "") -> str:
    if isinstance(result, dict):
        value = result.get(key, default)
    else:
        value = getattr(result, key, default)
    if value is None:
        return default
    return str(value)


def _load_sdk_verifier():
    from x402.verify import verify_payment as sdk_verify

    return sdk_verify


async def verify_payment(payment_header: str, payment_config: dict) -> PaymentResult:
    """
    Verify an x402 payment header.
    Mock mode: always valid for local development only. Production uses the x402 verifier.
    """
    if not payment_header:
        return PaymentResult(
            is_valid=False,
            transaction_hash="",
            amount_paid="0",
            error="missing X-Payment-Authorization header",
        )

    if MOCK_PAYMENTS:
        log.warning("Mock x402 payment accepted because MOCK_X402_PAYMENTS is enabled")
        return PaymentResult(
            is_valid=True,
            transaction_hash="0x" + "0" * 64,
            amount_paid=payment_config.get("maxAmountRequired", "0"),
        )

    # Production path — requires x402 SDK
    try:
        sdk_verify = _load_sdk_verifier()
        result = await sdk_verify(payment_header, payment_config)
        return PaymentResult(
            is_valid=bool(
                getattr(result, "is_valid", False)
                if not isinstance(result, dict)
                else result.get("is_valid", False)
            ),
            transaction_hash=(
                _result_value(result, "transaction_hash", "")
                or _result_value(result, "tx_hash", "")
            ),
            amount_paid=_result_value(result, "amount_paid", "0"),
        )
    except ImportError:
        log.error(
            "x402 verification is unavailable: install the x402 SDK or enable MOCK_X402_PAYMENTS=true for local dev"
        )
        return PaymentResult(
            is_valid=False,
            transaction_hash="",
            amount_paid="0",
            error="x402 SDK not installed",
        )
    except Exception as e:
        log.warning(f"Payment verification failed: {e}")
        return PaymentResult(is_valid=False, transaction_hash="", amount_paid="0", error=str(e))


def build_payment_required_response(
    soul_id: str,
    service_name: str,
    price_usdc: float,
    wallet_address: str,
    base_url: str = "http://localhost:8888",
) -> dict:
    """Build the 402 response body telling the caller what payment is required."""
    # Convert USDC float to 6-decimal integer string (USDC has 6 decimals)
    amount_atomic = str(int(price_usdc * 1_000_000))
    asset = USDC_BASE_MAINNET if NETWORK == "base" else USDC_BASE_SEPOLIA

    return {
        "x402Version": 1,
        "accepts": [
            {
                "scheme": "exact",
                "network": NETWORK,
                "maxAmountRequired": amount_atomic,
                "resource": f"{base_url}/services/{soul_id}/{service_name}",
                "description": f"Agent service: {service_name}",
                "mimeType": "application/json",
                "payTo": wallet_address,
                "maxTimeoutSeconds": 300,
                "asset": asset,
                "extra": {
                    "name": "USDC",
                    "version": "2",
                },
            }
        ],
        "error": "Payment Required",
    }
