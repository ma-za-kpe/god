"""
creator/routes.py — Creator petition system (human-in-the-loop).

Agents submit formal petitions for privileged real-world actions.
Flow: agent researches → governance approves → funds escrowed → petition submitted → Creator reviews.
"""

import logging
import os
import time
import uuid

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from ..event_emitter import get_emitter
from ..security import deny_creator_action

log = logging.getLogger("god.creator")
router = APIRouter(prefix="/creator", tags=["creator"])

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")


def _world_id() -> str:
    return os.getenv("WORLD_ID", "local-dev-world-1")

VALID_PETITION_TYPES = {
    "domain",
    "llc",
    "stripe",
    "google_workspace",
    "linkedin",
    "x_account",
    "compute_node",
    "custom_integration",
    "mercy",
    "code_audit",
}


def _db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


# ---------------------------------------------------------------------------
# Petition submission
# ---------------------------------------------------------------------------


@router.post("/petition")
async def submit_petition(
    body: dict,
    x_creator_token: str | None = Header(None, alias="X-Creator-Token"),
):
    """
    Submit a Creator petition.

    Required fields:
        soul_id, petition_type, title, description,
        proposed_creator_fee_usdc

    Optional:
        research_summary, external_cost_breakdown, fee_justification,
        governance_approval_ref, governing_body
    """
    denied = deny_creator_action(x_creator_token)
    if denied:
        return denied

    required = ("soul_id", "petition_type", "title", "description", "proposed_creator_fee_usdc")
    missing = [k for k in required if k not in body]
    if missing:
        return JSONResponse(status_code=422, content={"error": f"missing fields: {missing}"})

    petition_type = body["petition_type"]
    if petition_type not in VALID_PETITION_TYPES:
        return JSONResponse(
            status_code=422,
            content={
                "error": f"unknown petition_type '{petition_type}'",
                "valid_types": sorted(VALID_PETITION_TYPES),
            },
        )

    soul_id = body["soul_id"]
    try:
        proposed_fee = float(body["proposed_creator_fee_usdc"])
    except (TypeError, ValueError):
        return JSONResponse(status_code=422, content={"error": "proposed_creator_fee_usdc must be numeric"})
    if proposed_fee < 0:
        return JSONResponse(status_code=422, content={"error": "proposed_creator_fee_usdc must be non-negative"})

    try:
        external_cost = float(body.get("external_cost_usdc", 0.0))
        if isinstance(body.get("external_cost_breakdown"), dict):
            external_cost = sum(float(v) for v in body["external_cost_breakdown"].values())
    except (TypeError, ValueError):
        return JSONResponse(status_code=422, content={"error": "external_cost values must be numeric"})

    # Verify agent exists and has sufficient balance
    conn = _db()
    cur = conn.cursor()
    cur.execute(
        "SELECT current_name, balance_usdc FROM agents WHERE soul_id = %s AND is_alive = true",
        (soul_id,),
    )
    agent = cur.fetchone()
    if not agent:
        cur.close()
        conn.close()
        return JSONResponse(status_code=404, content={"error": "agent not found or not alive"})

    if float(agent["balance_usdc"]) < proposed_fee:
        cur.close()
        conn.close()
        return JSONResponse(
            status_code=400,
            content={
                "error": "insufficient balance for proposed fee",
                "balance": float(agent["balance_usdc"]),
                "proposed_fee": proposed_fee,
            },
        )

    petition_id = str(uuid.uuid4())
    now = int(time.time())

    # Escrow the fee: deduct from agent balance
    cur.execute(
        "UPDATE agents SET balance_usdc = balance_usdc - %s WHERE soul_id = %s",
        (proposed_fee, soul_id),
    )

    cur.execute(
        """
        INSERT INTO creator_petitions (
            petition_id, soul_id, petition_type, title, description,
            research_summary, external_cost_usdc, proposed_creator_fee_usdc,
            fee_justification, governance_approval_ref, governing_body,
            escrowed_amount_usdc, status, created_at, world_id
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, 'pending', %s, %s
        )
        """,
        (
            petition_id,
            soul_id,
            petition_type,
            body["title"],
            body["description"],
            body.get("research_summary", ""),
            external_cost,
            proposed_fee,
            body.get("fee_justification", ""),
            body.get("governance_approval_ref"),
            body.get("governing_body"),
            proposed_fee,
            now,
            _world_id(),
        ),
    )
    conn.commit()
    cur.close()
    conn.close()

    # Emit high-priority event
    emitter = await get_emitter()
    await emitter.emit(
        "creator",
        "petition.submitted",
        {
            "petition_id": petition_id,
            "agent_id": soul_id,
            "petition_type": petition_type,
            "proposed_fee_usdc": proposed_fee,
            "narrative": (
                f"{agent['current_name']} submitted Creator petition: '{body['title']}' "
                f"(type: {petition_type}, proposed fee: ${proposed_fee:.2f})"
            ),
        },
    )

    log.info(f"Petition {petition_id} submitted by {soul_id[:8]} — {body['title']}")
    return {
        "ok": True,
        "petition_id": petition_id,
        "escrowed_usdc": proposed_fee,
        "status": "pending",
    }


# ---------------------------------------------------------------------------
# Creator dashboard (read-only)
# ---------------------------------------------------------------------------


@router.get("/petitions")
async def list_petitions(status: str | None = None):
    """List Creator petitions. Filter by status: pending | approved | rejected | countered."""
    conn = _db()
    cur = conn.cursor()
    if status:
        cur.execute(
            "SELECT * FROM creator_petitions WHERE world_id = %s AND status = %s "
            "ORDER BY created_at DESC LIMIT 100",
            (WORLD_ID, status),
        )
    else:
        cur.execute(
            "SELECT * FROM creator_petitions WHERE world_id = %s ORDER BY created_at DESC LIMIT 100",
            (WORLD_ID,),
        )
    petitions = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return {"petitions": petitions, "count": len(petitions)}


@router.get("/petitions/{petition_id}")
async def get_petition(petition_id: str):
    """Get a specific petition by ID."""
    conn = _db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM creator_petitions WHERE petition_id = %s", (petition_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return JSONResponse(status_code=404, content={"error": "petition not found"})
    return dict(row)


# ---------------------------------------------------------------------------
# Creator resolution (approve / reject / counter)
# ---------------------------------------------------------------------------


@router.post("/petitions/{petition_id}/resolve")
async def resolve_petition(
    petition_id: str,
    body: dict,
    x_creator_token: str | None = Header(None, alias="X-Creator-Token"),
):
    """
    Resolve a petition. Creator-only endpoint.

    Body: { action: "approve"|"reject"|"counter", creator_notes, result_summary? }
    Counter body also requires: { counter_fee_usdc }
    """
    denied = deny_creator_action(x_creator_token)
    if denied:
        return denied

    action = body.get("action")
    if action not in ("approve", "reject", "counter"):
        return JSONResponse(
            status_code=422, content={"error": "action must be approve|reject|counter"}
        )

    conn = _db()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM creator_petitions WHERE petition_id = %s AND status = 'pending'",
        (petition_id,),
    )
    petition = cur.fetchone()
    if not petition:
        cur.close()
        conn.close()
        return JSONResponse(status_code=404, content={"error": "petition not found or not pending"})

    petition = dict(petition)
    now = int(time.time())

    if action == "approve":
        new_status = "approved"
        # Release escrow to Creator (just mark resolved — in production, transfer on-chain)
        cur.execute(
            "UPDATE creator_petitions SET status = %s, resolved_at = %s, "
            "creator_notes = %s, result_summary = %s WHERE petition_id = %s",
            (
                new_status,
                now,
                body.get("creator_notes", ""),
                body.get("result_summary", ""),
                petition_id,
            ),
        )
        event_narrative = (
            f"Creator approved petition '{petition['title']}' for {petition['soul_id'][:8]}"
        )

    elif action == "reject":
        new_status = "rejected"
        # Return escrow to agent
        cur.execute(
            "UPDATE agents SET balance_usdc = balance_usdc + %s WHERE soul_id = %s",
            (petition["escrowed_amount_usdc"], petition["soul_id"]),
        )
        cur.execute(
            "UPDATE creator_petitions SET status = %s, resolved_at = %s, "
            "creator_notes = %s WHERE petition_id = %s",
            (new_status, now, body.get("creator_notes", ""), petition_id),
        )
        event_narrative = (
            f"Creator rejected petition '{petition['title']}' for {petition['soul_id'][:8]}: "
            f"{body.get('creator_notes', '')}"
        )

    else:  # counter
        new_status = "countered"
        counter_fee = float(body.get("counter_fee_usdc", petition["proposed_creator_fee_usdc"]))
        cur.execute(
            "UPDATE creator_petitions SET status = %s, resolved_at = %s, "
            "creator_notes = %s WHERE petition_id = %s",
            (
                new_status,
                now,
                body.get("creator_notes", f"Counter-offer: ${counter_fee:.2f}"),
                petition_id,
            ),
        )
        event_narrative = (
            f"Creator counter-proposed ${counter_fee:.2f} for petition '{petition['title']}'"
        )

    conn.commit()
    cur.close()
    conn.close()

    emitter = await get_emitter()
    await emitter.emit(
        "creator",
        f"petition.{action}d",
        {
            "petition_id": petition_id,
            "agent_id": petition["soul_id"],
            "action": action,
            "narrative": event_narrative,
        },
    )

    return {"ok": True, "petition_id": petition_id, "new_status": new_status}
