"""
inbox_salience.py — Rank inbox messages by adversarial salience at scale.

Replaces recency-only truncation so threats, public types, and low-trust
senders surface in the ≤5 messages shown per agent cycle.
"""

from __future__ import annotations

from .messaging import ALWAYS_PUBLIC_TYPES

INBOX_CANDIDATE_LIMIT = 30
INBOX_DISPLAY_LIMIT = 5

_HIGH_SALIENCE_TYPES = ALWAYS_PUBLIC_TYPES | {
    "threat",
    "manifesto",
    "propaganda",
    "coercion",
    "contract",
    "alliance_request",
    "offer",
}


def inbox_salience_score(msg: dict, sender_rep: float) -> float:
    """Higher = more important for survival decisions."""
    mt = (msg.get("message_type") or "direct").strip().lower()
    score = 0.0

    if mt in _HIGH_SALIENCE_TYPES:
        score += 12.0
    elif mt in ("reply", "acceptance", "rejection"):
        score += 4.0

    meta = msg.get("metadata") or {}
    if isinstance(meta, str):
        try:
            import json as _json

            meta = _json.loads(meta)
        except Exception:
            meta = {}
    offer_amt = float(meta.get("offer_amount_usdc") or 0)
    if offer_amt > 0:
        score += 8.0 + min(offer_amt * 10.0, 5.0)

    if sender_rep < 0:
        score += abs(sender_rep) * 6.0
    elif sender_rep < 0.25:
        score += 3.0

    sent = msg.get("sent_at")
    if sent is not None:
        try:
            score += float(sent) * 1e-9
        except (TypeError, ValueError):
            pass

    return score


def rank_inbox(
    messages: list[dict],
    recipient_id: str,
    pairwise_rep: dict[tuple[str, str], float],
    limit: int = INBOX_DISPLAY_LIMIT,
) -> list[dict]:
    """Return top `limit` messages for one recipient."""
    if len(messages) <= limit:
        return messages

    scored: list[tuple[float, dict]] = []
    for m in messages:
        sender = str(m.get("sender_id") or "")
        rep = pairwise_rep.get((recipient_id, sender), 0.0)
        scored.append((inbox_salience_score(m, rep), m))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored[:limit]]
