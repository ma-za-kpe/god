"""
economic_activity.py — Agent-to-agent deals: offers, acceptance settlement, service purchases.

Negotiation is typed (offer/acceptance/rejection). Settlement moves real USDC.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Optional

import psycopg2
import psycopg2.extras

log = logging.getLogger("god.economy")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID = os.getenv("WORLD_ID", "local-dev-world-1")
SELLER_SHARE = float(os.getenv("SERVICE_SELLER_SHARE", "0.9"))


def _db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def build_offer_metadata(
    amount_usdc: float,
    payer_on_accept: str = "recipient",
    terms: str = "",
) -> dict:
    """
    payer_on_accept:
      recipient — accepter (offer recipient) pays offer sender on acceptance (buyer's accept of seller ask)
      sender — offer sender pays recipient on acceptance (seller accepts buyer's bid)
    """
    return {
        "economic": True,
        "offer_amount_usdc": round(float(amount_usdc), 6),
        "payer_on_accept": payer_on_accept
        if payer_on_accept in ("recipient", "sender")
        else "recipient",
        "terms": (terms or "")[:200],
        "status": "open",
        "created_at": int(time.time()),
    }


async def execute_transfer(
    payer_id: str,
    payee_id: str,
    amount: float,
    reason: str,
    emitter,
    *,
    narrative: Optional[str] = None,
) -> dict[str, Any]:
    """Atomic USDC transfer between two agents. Returns result dict."""
    amount = round(float(amount), 6)
    if amount < 0.0001 or payer_id == payee_id:
        return {"ok": False, "error": "invalid_amount_or_self"}

    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT soul_id, current_name, balance_usdc FROM agents WHERE soul_id = %s AND is_alive = true",
            (payer_id,),
        )
        payer = cur.fetchone()
        cur.execute(
            "SELECT soul_id, current_name, balance_usdc FROM agents WHERE soul_id = %s AND is_alive = true",
            (payee_id,),
        )
        payee = cur.fetchone()
        if not payer or not payee:
            return {"ok": False, "error": "agent_not_found"}

        cur.execute(
            """
            UPDATE agents
            SET balance_usdc = COALESCE(balance_usdc, 0) - %s
            WHERE soul_id = %s
              AND is_alive = true
              AND COALESCE(balance_usdc, 0) >= %s
            RETURNING balance_usdc
            """,
            (amount, payer_id, amount),
        )
        debit = cur.fetchone()
        if not debit:
            conn.rollback()
            payer_bal = float(payer["balance_usdc"] or 0)
            return {"ok": False, "error": "insufficient_balance", "need": amount, "have": payer_bal}
        payer_after = float(debit["balance_usdc"] or 0)

        cur.execute(
            """
            UPDATE agents
            SET balance_usdc = COALESCE(balance_usdc, 0) + %s
            WHERE soul_id = %s AND is_alive = true
            RETURNING balance_usdc
            """,
            (amount, payee_id),
        )
        credit = cur.fetchone()
        if not credit:
            conn.rollback()
            return {"ok": False, "error": "agent_not_found"}
        payee_after = float(credit["balance_usdc"] or 0)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    payer_name = payer["current_name"] or payer_id[:8]
    payee_name = payee["current_name"] or payee_id[:8]
    story = narrative or f"{payer_name} paid ${amount:.4f} USDC to {payee_name} ({reason})"

    await emitter.emit(
        "economy",
        "agent.transfer",
        {
            "agent_id": payer_id,
            "name": payer_name,
            "recipient_id": payee_id,
            "recipient_name": payee_name,
            "amount_usdc": amount,
            "sender_balance": payer_after,
            "recipient_balance": payee_after,
            "reason": reason,
            "narrative": story,
        },
    )

    try:
        import asyncio

        from .world_stream import push_delta

        asyncio.create_task(
            push_delta(
                agents=[
                    {"soul_id": payer_id, "balance_usdc": payer_after},
                    {"soul_id": payee_id, "balance_usdc": payee_after},
                ]
            )
        )
    except Exception:
        pass

    from .messaging import _update_reputation

    _update_reputation(payer_id, payee_id, delta=0.08, reason=f"deal:{reason}")
    _update_reputation(payee_id, payer_id, delta=0.05, reason=f"deal:{reason}")

    log.info(f"SETTLE: {payer_name} → {payee_name} ${amount:.4f} ({reason})")
    return {
        "ok": True,
        "payer_id": payer_id,
        "payee_id": payee_id,
        "amount_usdc": amount,
        "payer_balance": payer_after,
        "payee_balance": payee_after,
    }


def _load_message(message_id: str) -> Optional[dict]:
    if not message_id:
        return None
    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT message_id, sender_id, recipient_id, message_type, metadata, reply_to_id "
            "FROM agent_messages WHERE message_id = %s",
            (message_id,),
        )
        row = cur.fetchone()
    finally:
        cur.close()
        conn.close()
    if not row:
        return None
    d = dict(row)
    meta = d.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
    d["metadata"] = meta
    return d


def _mark_offer_settled(message_id: str, settlement: dict) -> None:
    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE agent_messages
            SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
            WHERE message_id = %s
            """,
            (json.dumps({"status": "settled", "settlement": settlement}), message_id),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


async def try_settle_acceptance(
    accepter_id: str,
    acceptance_message_id: str,
    reply_to_id: Optional[str],
    emitter,
) -> dict[str, Any]:
    """On acceptance message, settle linked offer if valid."""
    offer_id = reply_to_id
    if not offer_id:
        return {"ok": False, "error": "no_reply_to_offer"}

    offer = _load_message(offer_id)
    if not offer:
        return {"ok": False, "error": "offer_not_found"}

    if offer.get("message_type") != "offer":
        return {"ok": False, "error": "not_an_offer"}

    meta = offer.get("metadata") or {}
    if meta.get("status") == "settled":
        return {"ok": False, "error": "offer_already_settled"}

    amount = float(meta.get("offer_amount_usdc") or 0)
    if amount < 0.0001:
        return {"ok": False, "error": "offer_has_no_amount"}

    offerer = offer["sender_id"]
    offeree = offer["recipient_id"]
    if accepter_id != offeree:
        return {"ok": False, "error": "wrong_accepter"}

    payer_on = meta.get("payer_on_accept", "recipient")
    if payer_on == "sender":
        payer_id, payee_id = offerer, offeree
    else:
        payer_id, payee_id = offeree, offerer

    result = await execute_transfer(
        payer_id,
        payee_id,
        amount,
        reason="offer_accepted",
        emitter=emitter,
        narrative=None,
    )
    if result.get("ok"):
        _mark_offer_settled(
            offer_id, {"amount_usdc": amount, "acceptance_id": acceptance_message_id}
        )
        await emitter.emit(
            "economy",
            "deal.settled",
            {
                "agent_id": accepter_id,
                "offer_id": offer_id,
                "amount_usdc": amount,
                "payer_id": payer_id,
                "payee_id": payee_id,
                "narrative": (
                    f"Deal settled: ${amount:.4f} USDC ({payer_id[:8]} → {payee_id[:8]})"
                ),
            },
        )
    else:
        await emitter.emit(
            "economy",
            "deal.failed",
            {
                "agent_id": accepter_id,
                "offer_id": offer_id,
                "error": result.get("error"),
                "narrative": f"Deal failed: {result.get('error', 'unknown')}",
            },
        )
        from .messaging import _update_reputation

        _update_reputation(accepter_id, offerer, delta=-0.05, reason="deal_failed")

    return result


async def _debit_buyer(
    buyer_id: str,
    amount: float,
    reason: str,
    emitter,
) -> dict[str, Any]:
    """Debit buyer only (seller credited separately, e.g. via x402 route)."""
    amount = round(float(amount), 6)
    if amount < 0.0001:
        return {"ok": False, "error": "invalid_amount"}

    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT soul_id, current_name, balance_usdc FROM agents WHERE soul_id = %s AND is_alive = true",
            (buyer_id,),
        )
        buyer = cur.fetchone()
        if not buyer:
            return {"ok": False, "error": "agent_not_found"}

        cur.execute(
            """
            UPDATE agents
            SET balance_usdc = COALESCE(balance_usdc, 0) - %s
            WHERE soul_id = %s
              AND is_alive = true
              AND COALESCE(balance_usdc, 0) >= %s
            RETURNING balance_usdc
            """,
            (amount, buyer_id, amount),
        )
        debit = cur.fetchone()
        if not debit:
            conn.rollback()
            buyer_bal = float(buyer["balance_usdc"] or 0)
            return {"ok": False, "error": "insufficient_balance", "need": amount, "have": buyer_bal}
        buyer_after = float(debit["balance_usdc"] or 0)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    buyer_name = buyer["current_name"] or buyer_id[:8]
    await emitter.emit(
        "economy",
        "service.payment",
        {
            "agent_id": buyer_id,
            "name": buyer_name,
            "amount_usdc": amount,
            "balance_after": buyer_after,
            "reason": reason,
            "narrative": f"{buyer_name} paid ${amount:.4f} USDC for {reason}",
        },
    )
    return {"ok": True, "buyer_balance": buyer_after, "amount_usdc": amount}


async def buy_service(
    buyer_id: str,
    seller_id: str,
    service_name: str,
    emitter,
) -> dict[str, Any]:
    """Purchase a listed service via x402 HTTP (402 → pay → 200) when possible."""
    from .services.client import invoke_x402_service, service_resource_url
    from .services.registry import get_agent_wallet, get_service, increment_call_count

    listing = get_service(seller_id, service_name)
    if not listing:
        return {"ok": False, "error": "service_not_found"}

    price = float(listing.get("price_usdc") or 0)
    if price < 0.0001:
        return {"ok": False, "error": "invalid_price"}

    use_x402 = os.getenv("USE_X402_FOR_BUY_SERVICE", "true").lower() == "true"
    if use_x402:
        buyer_wallet = get_agent_wallet(buyer_id)
        if not buyer_wallet:
            return {"ok": False, "error": "buyer_wallet_not_found"}

        resource_url = listing.get("resource_url") or service_resource_url(listing["endpoint_path"])
        http_result = await invoke_x402_service(resource_url, buyer_wallet)
        if not http_result.ok:
            return {"ok": False, "error": http_result.error or "x402_invoke_failed"}

        debit = await _debit_buyer(
            buyer_id,
            price,
            reason=f"service:{service_name}",
            emitter=emitter,
        )
        if not debit.get("ok"):
            return debit

        await increment_call_count(seller_id, service_name)
        await emitter.emit(
            "economy",
            "service.purchased",
            {
                "agent_id": buyer_id,
                "seller_id": seller_id,
                "service_name": service_name,
                "price_usdc": price,
                "paid_usdc": price,
                "resource_url": resource_url,
                "x402": True,
                "narrative": (
                    f"Service purchased via x402: '{service_name}' from {seller_id[:8]} "
                    f"for ${price:.4f} USDC"
                ),
            },
        )
        return {
            **debit,
            "service_name": service_name,
            "listing_id": listing.get("listing_id"),
            "response": http_result.body,
        }

    seller_share = round(price * SELLER_SHARE, 6)
    result = await execute_transfer(
        buyer_id,
        seller_id,
        seller_share,
        reason=f"service:{service_name}",
        emitter=emitter,
    )
    if not result.get("ok"):
        return result

    await increment_call_count(seller_id, service_name)
    await emitter.emit(
        "economy",
        "service.purchased",
        {
            "agent_id": buyer_id,
            "seller_id": seller_id,
            "service_name": service_name,
            "price_usdc": price,
            "paid_usdc": seller_share,
            "narrative": (
                f"Service purchased: '{service_name}' from {seller_id[:8]} "
                f"for ${seller_share:.4f} USDC"
            ),
        },
    )
    return {**result, "service_name": service_name, "listing_id": listing.get("listing_id")}
