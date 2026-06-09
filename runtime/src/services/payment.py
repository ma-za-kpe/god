"""
payment.py — x402 payment verification.

Local dev: MOCK_X402_PAYMENTS=true accepts all payments without on-chain verification.
Production: set MOCK_X402_PAYMENTS=false and ensure x402 SDK is configured for Base.
"""
import os
import logging
from dataclasses import dataclass

log = logging.getLogger("god.services.payment")

MOCK_PAYMENTS = os.getenv("MOCK_X402_PAYMENTS", "true").lower() == "true"
USDC_BASE_SEPOLIA = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
USDC_BASE_MAINNET = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
NETWORK = os.getenv("CHAIN_NETWORK", "base-sepolia")


@dataclass
class PaymentResult:
    is_valid: bool
    transaction_hash: str
    amount_paid: str
    error: str = ""


async def verify_payment(payment_header: str, payment_config: dict) -> PaymentResult:
    """
    Verify an x402 payment header.
    Mock mode: always valid. Production: EIP-712 signature + USDC transfer verification.
    """
    if not payment_header:
        return PaymentResult(is_valid=False, transaction_hash="", amount_paid="0",
                             error="missing X-Payment-Authorization header")

    if MOCK_PAYMENTS:
        log.debug("Mock payment accepted")
        return PaymentResult(
            is_valid=True,
            transaction_hash="0x" + "0" * 64,
            amount_paid=payment_config.get("maxAmountRequired", "0"),
        )

    # Production path — requires x402 SDK
    try:
        from x402.verify import verify_payment as sdk_verify
        result = await sdk_verify(payment_header, payment_config)
        return PaymentResult(
            is_valid=result.is_valid,
            transaction_hash=result.transaction_hash or "",
            amount_paid=result.amount_paid or "0",
        )
    except ImportError:
        log.error("x402 SDK not installed — run: pip install x402")
        return PaymentResult(is_valid=False, transaction_hash="", amount_paid="0",
                             error="x402 SDK not installed")
    except Exception as e:
        log.warning(f"Payment verification failed: {e}")
        return PaymentResult(is_valid=False, transaction_hash="", amount_paid="0",
                             error=str(e))


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
        "accepts": [{
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
        }],
        "error": "Payment Required",
    }
