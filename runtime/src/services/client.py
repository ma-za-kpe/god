"""
client.py — HTTP client for x402-gated agent services.

Agents exercise the real 402 → pay → 200 flow when buying services.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import httpx

log = logging.getLogger("god.services.client")

RUNTIME_BASE_URL = os.getenv("RUNTIME_BASE_URL", "http://localhost:8888")


@dataclass(frozen=True)
class InvokeResult:
    ok: bool
    status_code: int = 0
    body: dict | None = None
    tx_hash: str = ""
    error: str = ""


async def invoke_x402_service(
    resource_url: str,
    payer_wallet: str,
    *,
    timeout_s: float = 20.0,
) -> InvokeResult:
    """
    Call an x402-gated service endpoint.
    1. GET without payment header → expect 402
    2. GET with X-Payment-Authorization → expect 200
    """
    if not payer_wallet:
        return InvokeResult(ok=False, error="missing_payer_wallet")

    headers = {"X-Payment-Authorization": payer_wallet}

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            first = await client.get(resource_url)
            if first.status_code not in (200, 402):
                return InvokeResult(
                    ok=False,
                    status_code=first.status_code,
                    error=f"unexpected_status_{first.status_code}",
                )

            if first.status_code == 402:
                paid = await client.get(resource_url, headers=headers)
                if paid.status_code != 200:
                    return InvokeResult(
                        ok=False,
                        status_code=paid.status_code,
                        error="payment_not_accepted",
                    )
                try:
                    body = paid.json()
                except Exception:
                    body = {"raw": paid.text[:500]}
                return InvokeResult(ok=True, status_code=200, body=body)

            try:
                body = first.json()
            except Exception:
                body = {"raw": first.text[:500]}
            return InvokeResult(ok=True, status_code=200, body=body)
    except Exception as e:
        log.warning(f"x402 invoke failed for {resource_url}: {e}")
        return InvokeResult(ok=False, error=str(e))


def service_resource_url(endpoint_path: str) -> str:
    base = RUNTIME_BASE_URL.rstrip("/")
    path = endpoint_path if endpoint_path.startswith("/") else f"/{endpoint_path}"
    return f"{base}{path}"
