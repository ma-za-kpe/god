# Coalition System — Implementation Spec

> Code-level specification for the coalition and family alliance system. Covers the `coalitions.py` module, the coalition lifecycle (formation, joining, treasury, dissolution), how coalitions integrate with governance voting (doc 65), the messaging channel routing (doc 68), and the API endpoints. The DB schema (`coalitions`, `coalition_members`) already exists in `init-db.sql`.

---

## What a Coalition Is (in Implementation Terms)

A coalition is:
1. A row in `coalitions` with a treasury wallet address
2. A set of rows in `coalition_members` linking soul_ids to the coalition
3. A NATS subject for group messaging: `world.{world_id}.coalition.{coalition_id}.channel`
4. An optional charter document on IPFS (CID stored in `coalitions.charter_cid`)

Coalitions are not agents — they have no soul_id and no cognition cycle. They are coordination structures that agents act through.

---

## `runtime/src/coalitions.py` — Full Implementation

```python
# runtime/src/coalitions.py
"""
coalitions.py — Coalition lifecycle management.
Formation, membership, treasury, voting, and dissolution.
"""
import logging
import os
import time
import uuid
from typing import Optional

import psycopg2
import psycopg2.extras

log = logging.getLogger("god.coalitions")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID     = os.getenv("WORLD_ID", "local-dev-world-1")

MIN_FORMATION_MEMBERS = 2
MAX_MEMBERS_SIMPLE_MAJORITY = 10     # above this → stake-weighted voting
TREASURY_EMERGENCY_RENT_MULTIPLIER = 2  # treasury must have 2x rent to auto-cover a member


def _db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


# ---------------------------------------------------------------------------
# Formation
# ---------------------------------------------------------------------------

async def form_coalition(
    founder_soul_id: str,
    name: str,
    charter_text: Optional[str] = None,
    initial_members: Optional[list[str]] = None,
) -> dict:
    """
    Create a new coalition. Returns coalition record.
    Emits 'social.coalition.formed' event.
    """
    coalition_id = str(uuid.uuid4())
    treasury_wallet = _generate_treasury_address(coalition_id)
    now = int(time.time())

    conn = _db()
    cur  = conn.cursor()

    # Verify founder exists and is alive
    cur.execute("SELECT soul_id FROM agents WHERE soul_id = %s AND is_alive = true AND world_id = %s",
                (founder_soul_id, WORLD_ID))
    if not cur.fetchone():
        cur.close(); conn.close()
        raise ValueError(f"Founder {founder_soul_id[:8]} not found or not alive")

    cur.execute(
        """
        INSERT INTO coalitions
            (coalition_id, name, founder_soul_id, treasury_wallet, member_count, status, formed_at, world_id)
        VALUES (%s, %s, %s, %s, %s, 'active', %s, %s)
        """,
        (coalition_id, name, founder_soul_id, treasury_wallet, 1, now, WORLD_ID),
    )

    cur.execute(
        """
        INSERT INTO coalition_members
            (membership_id, coalition_id, soul_id, role, joined_at, world_id)
        VALUES (%s, %s, %s, 'founder', %s, %s)
        """,
        (str(uuid.uuid4()), coalition_id, founder_soul_id, now, WORLD_ID),
    )

    conn.commit()

    # Add initial members if provided
    members_added = [founder_soul_id]
    if initial_members:
        for soul_id in initial_members:
            if soul_id != founder_soul_id:
                try:
                    _add_member(coalition_id, soul_id, "member", cur, conn)
                    members_added.append(soul_id)
                except Exception as e:
                    log.debug(f"Could not add initial member {soul_id[:8]}: {e}")

    cur.close(); conn.close()

    # Pin charter to IPFS if provided
    if charter_text:
        try:
            charter_cid = await _pin_charter(charter_text, coalition_id)
            _update_charter_cid(coalition_id, charter_cid)
        except Exception as e:
            log.debug(f"Charter pin failed for {coalition_id[:8]}: {e}")

    from .event_emitter import get_emitter
    emitter = await get_emitter()
    await emitter.emit("social", "coalition.formed", {
        "agent_id":       founder_soul_id,
        "coalition_id":   coalition_id,
        "coalition_name": name,
        "member_count":   len(members_added),
        "narrative":      f"{name} coalition founded by {founder_soul_id[:8]} with {len(members_added)} members.",
    })

    log.info(f"COALITION FORMED: {name} ({coalition_id[:8]}) — {len(members_added)} members")
    return {"coalition_id": coalition_id, "name": name, "treasury_wallet": treasury_wallet,
            "member_count": len(members_added)}


async def join_coalition(soul_id: str, coalition_id: str) -> bool:
    """
    Add an agent to an existing coalition.
    Emits 'social.coalition.member_joined' event.
    """
    conn = _db()
    cur  = conn.cursor()

    cur.execute("SELECT soul_id FROM agents WHERE soul_id = %s AND is_alive = true AND world_id = %s",
                (soul_id, WORLD_ID))
    if not cur.fetchone():
        cur.close(); conn.close()
        return False

    cur.execute("SELECT coalition_id FROM coalition_members WHERE soul_id = %s AND world_id = %s",
                (soul_id, WORLD_ID))
    if cur.fetchone():
        cur.close(); conn.close()
        raise ValueError(f"Agent {soul_id[:8]} is already in a coalition")

    cur.execute("SELECT * FROM coalitions WHERE coalition_id = %s AND world_id = %s AND status = 'active'",
                (coalition_id, WORLD_ID))
    coalition = cur.fetchone()
    if not coalition:
        cur.close(); conn.close()
        raise ValueError(f"Coalition {coalition_id[:8]} not found or inactive")

    _add_member(coalition_id, soul_id, "member", cur, conn)
    cur.close(); conn.close()

    from .event_emitter import get_emitter
    emitter = await get_emitter()
    await emitter.emit("social", "coalition.member_joined", {
        "agent_id":       soul_id,
        "coalition_id":   coalition_id,
        "coalition_name": coalition["name"],
        "narrative":      f"{soul_id[:8]} joins {coalition['name']}.",
    })
    return True


async def leave_coalition(soul_id: str, coalition_id: str) -> bool:
    """Remove an agent from a coalition. Founders cannot leave — they must dissolve."""
    conn = _db()
    cur  = conn.cursor()

    cur.execute("SELECT role FROM coalition_members WHERE coalition_id = %s AND soul_id = %s AND world_id = %s",
                (coalition_id, soul_id, WORLD_ID))
    membership = cur.fetchone()
    if not membership:
        cur.close(); conn.close()
        return False

    if membership["role"] == "founder":
        cur.close(); conn.close()
        raise ValueError("Founders cannot leave — dissolve the coalition instead.")

    cur.execute("DELETE FROM coalition_members WHERE coalition_id = %s AND soul_id = %s AND world_id = %s",
                (coalition_id, soul_id, WORLD_ID))
    cur.execute(
        "UPDATE coalitions SET member_count = member_count - 1 WHERE coalition_id = %s",
        (coalition_id,),
    )
    conn.commit()
    cur.close(); conn.close()

    from .event_emitter import get_emitter
    emitter = await get_emitter()
    await emitter.emit("social", "coalition.member_left", {
        "agent_id":     soul_id,
        "coalition_id": coalition_id,
        "narrative":    f"{soul_id[:8]} leaves the coalition.",
    })
    return True


async def dissolve_coalition(coalition_id: str, by_soul_id: str) -> bool:
    """
    Dissolve a coalition. Only the founder can dissolve.
    Treasury distribution is handled separately (manual or via governance vote).
    """
    conn = _db()
    cur  = conn.cursor()

    cur.execute("SELECT role FROM coalition_members WHERE coalition_id = %s AND soul_id = %s",
                (coalition_id, by_soul_id))
    membership = cur.fetchone()
    if not membership or membership["role"] != "founder":
        cur.close(); conn.close()
        raise ValueError("Only the founder can dissolve a coalition.")

    cur.execute("UPDATE coalitions SET status = 'dissolved' WHERE coalition_id = %s AND world_id = %s",
                (coalition_id, WORLD_ID))
    conn.commit()

    cur.execute("SELECT name FROM coalitions WHERE coalition_id = %s", (coalition_id,))
    name = (cur.fetchone() or {}).get("name", coalition_id[:8])
    cur.close(); conn.close()

    from .event_emitter import get_emitter
    emitter = await get_emitter()
    await emitter.emit("social", "coalition.dissolved", {
        "agent_id":       by_soul_id,
        "coalition_id":   coalition_id,
        "coalition_name": name,
        "narrative":      f"{name} is dissolved.",
    })
    log.info(f"COALITION DISSOLVED: {name} ({coalition_id[:8]})")
    return True


# ---------------------------------------------------------------------------
# Membership queries
# ---------------------------------------------------------------------------

def get_coalition_members(coalition_id: str) -> list[dict]:
    """Return all active members of a coalition."""
    try:
        conn = _db()
        cur  = conn.cursor()
        cur.execute(
            """
            SELECT cm.soul_id, cm.role, cm.joined_at, a.current_name, a.archetype, a.is_alive
            FROM coalition_members cm
            JOIN agents a ON cm.soul_id = a.soul_id
            WHERE cm.coalition_id = %s AND cm.world_id = %s
            ORDER BY cm.joined_at ASC
            """,
            (coalition_id, WORLD_ID),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close(); conn.close()
        return rows
    except Exception as e:
        log.debug(f"get_coalition_members failed: {e}")
        return []


def get_agent_coalition(soul_id: str) -> Optional[dict]:
    """Return the coalition this agent belongs to, or None."""
    try:
        conn = _db()
        cur  = conn.cursor()
        cur.execute(
            """
            SELECT c.*, cm.role, cm.joined_at
            FROM coalition_members cm
            JOIN coalitions c ON cm.coalition_id = c.coalition_id
            WHERE cm.soul_id = %s AND cm.world_id = %s AND c.status = 'active'
            """,
            (soul_id, WORLD_ID),
        )
        row = cur.fetchone()
        cur.close(); conn.close()
        return dict(row) if row else None
    except Exception:
        return None


def get_coalition_vote_weight(coalition_id: str, soul_id: str,
                               model: str = "simple") -> float:
    """
    Return this member's vote weight for a coalition governance action.

    model = "simple"  → 1.0 per member
    model = "stake"   → proportional to USDC balance, capped at 10x median
    model = "prestige"→ proportional to prestige_score
    """
    members = get_coalition_members(coalition_id)
    member_ids = [m["soul_id"] for m in members]

    if soul_id not in member_ids:
        return 0.0
    if model == "simple" or len(members) <= MAX_MEMBERS_SIMPLE_MAJORITY:
        return 1.0

    try:
        conn = _db()
        cur  = conn.cursor()

        if model == "stake":
            cur.execute(
                "SELECT soul_id, COALESCE(balance_usdc, 0) AS weight FROM agents WHERE soul_id = ANY(%s)",
                (member_ids,),
            )
            weights = {r["soul_id"]: float(r["weight"]) for r in cur.fetchall()}
            median = sorted(weights.values())[len(weights) // 2]
            cap = median * 10
            total = sum(min(w, cap) for w in weights.values())
            my_weight = min(weights.get(soul_id, 0), cap)
            cur.close(); conn.close()
            return (my_weight / total) if total > 0 else 0.0

        elif model == "prestige":
            cur.execute(
                "SELECT soul_id, COALESCE(prestige_score, 0) AS weight FROM agent_status WHERE soul_id = ANY(%s)",
                (member_ids,),
            )
            weights = {r["soul_id"]: float(r["weight"]) for r in cur.fetchall()}
            total = sum(weights.values())
            cur.close(); conn.close()
            return (weights.get(soul_id, 0) / total) if total > 0 else 0.0

        cur.close(); conn.close()
    except Exception as e:
        log.debug(f"get_coalition_vote_weight failed: {e}")

    return 1.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _add_member(coalition_id, soul_id, role, cur, conn):
    cur.execute(
        """
        INSERT INTO coalition_members
            (membership_id, coalition_id, soul_id, role, joined_at, world_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (coalition_id, soul_id) DO NOTHING
        """,
        (str(uuid.uuid4()), coalition_id, soul_id, role, int(time.time()), WORLD_ID),
    )
    cur.execute(
        "UPDATE coalitions SET member_count = member_count + 1 WHERE coalition_id = %s",
        (coalition_id,),
    )
    conn.commit()


def _generate_treasury_address(coalition_id: str) -> str:
    """Deterministic placeholder address. Production: derive from coalition_id via HD wallet."""
    import hashlib
    h = hashlib.sha256(coalition_id.encode()).hexdigest()
    return "0x" + h[:40]


def _update_charter_cid(coalition_id: str, cid: str):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur  = conn.cursor()
        cur.execute("UPDATE coalitions SET charter_cid = %s WHERE coalition_id = %s",
                    (cid, coalition_id))
        conn.commit()
        cur.close(); conn.close()
    except Exception:
        pass


async def _pin_charter(charter_text: str, coalition_id: str) -> str:
    """Pin charter to IPFS. Returns CID. Stub if IPFS unavailable."""
    try:
        import httpx
        ipfs_api = os.getenv("IPFS_API", "http://localhost:5001")
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{ipfs_api}/api/v0/add",
                files={"file": charter_text.encode()},
                timeout=10,
            )
            r.raise_for_status()
            return r.json()["Hash"]
    except Exception:
        return f"stub-cid-{coalition_id[:8]}"
```

---

## Coalition Routing in `agent_runner.py`

The agent cognition cycle should inject the agent's coalition context:

```python
async def _think(llm, agent: dict) -> str:
    from .coalitions import get_agent_coalition

    coalition = get_agent_coalition(agent["soul_id"])
    coalition_context = ""
    if coalition:
        coalition_context = (
            f"\nYou are a member of '{coalition['name']}' coalition "
            f"({coalition['member_count']} members, role: {coalition['role']})."
        )

    system = archetype_persona + coalition_context + ...
```

---

## Coalition Integration with Governance (doc 65)

When a coalition submits a law proposal (`proposer_coalition` field), the quorum and vote counting logic in the governance system should:

1. Count members of the sponsoring coalition as already informed (reduced notification cost)
2. Allow the coalition to co-sign the submission (counts as co-sponsors automatically)
3. Track coalition vote patterns in the `law_votes` table for replay

Relevant check in `governance.py` (to be implemented):

```python
async def validate_co_sponsors(proposal_id: str, coalition_id: Optional[str]) -> bool:
    """
    If a coalition submitted this proposal, its members count as co-sponsors
    up to the coalition's total active membership.
    """
    if not coalition_id:
        return False
    members = get_coalition_members(coalition_id)
    alive_tier2_plus = [
        m for m in members
        if m.get("is_alive") and _get_tier(m["soul_id"]) >= 2
    ]
    return len(alive_tier2_plus) >= 3
```

---

## New API Endpoints

Add to `main.py`:

```python
@app.get("/coalitions")
async def list_coalitions():
    """All active coalitions with member counts."""
    # SELECT * FROM coalitions WHERE world_id = %s AND status = 'active'
    # ORDER BY member_count DESC

@app.get("/coalitions/{coalition_id}")
async def get_coalition(coalition_id: str):
    """Full coalition record with member list."""
    # Coalition row + members from get_coalition_members()

@app.post("/coalitions")
async def create_coalition(body: dict):
    """
    Form a new coalition.
    Body: { soul_id, name, charter_text (optional) }
    """
    # calls form_coalition()

@app.post("/coalitions/{coalition_id}/join")
async def join_coalition_endpoint(coalition_id: str, body: dict):
    """
    Join a coalition.
    Body: { soul_id }
    """
    # calls join_coalition()

@app.post("/coalitions/{coalition_id}/leave")
async def leave_coalition_endpoint(coalition_id: str, body: dict):
    """
    Leave a coalition.
    Body: { soul_id }
    """
    # calls leave_coalition()

@app.get("/agents/{soul_id}/coalition")
async def get_agent_coalition_endpoint(soul_id: str):
    """Which coalition (if any) this agent belongs to."""
    # calls get_agent_coalition()
```

---

## Events Emitted

| Event | When |
|-------|------|
| `social.coalition.formed` | New coalition created |
| `social.coalition.member_joined` | Agent joins existing coalition |
| `social.coalition.member_left` | Agent leaves voluntarily |
| `social.coalition.dissolved` | Coalition dissolved by founder |
| `social.coalition.member_expelled` | Agent removed by governance vote |

The `social.coalition.formed` event triggers `first.coalition` via the existing `FIRST_TYPE_MAP` in `timeline.py`.

---

## NATS Channel Setup

Coalition channels are routed to the `AGENT_MESSAGES` stream (defined in doc 68). No additional stream configuration needed — subjects matching `world.*.coalition.*.channel` are already covered.

When a coalition is formed, its channel subject is immediately available for publishing. No explicit creation step required.

---

## See Also

- [doc 42 — Clan & Family System](./42-clan-family-system.md) — coalitions that grow into clans
- [doc 50 — Agentic DAO](./50-agentic-dao.md) — governance voting models
- [doc 65 — Law Amendment Protocol](./65-law-amendment-protocol.md) — coalitions as proposal sponsors
- [doc 68 — Agent Communication Implementation](./68-agent-communication-implementation.md) — coalition channel routing
- [doc 23 — Communication Protocol](./23-communication-protocol.md) — coalition channel design
