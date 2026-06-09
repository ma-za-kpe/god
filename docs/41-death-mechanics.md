# Death Mechanics & Death Archive System

> Death in the GOD Project is permanent, verifiable, and documented. This document covers the complete death lifecycle: what triggers it, what happens to the agent's state, what is preserved for descendants, and how death is recorded on-chain and on IPFS.

---

## What Triggers Death

An agent dies when it misses `maxMissedPayments` consecutive rent payments. The default is 3. This is enforced by two independent systems that must agree:

**On-chain (RentCollector.sol):**
- `collectRent(soulId)` increments `missedPayments` when the agent can't pay
- At `missedPayments >= maxMissedPayments`: `lease.active = false`, `activeAgentCount--`, `SoulNFT.burn(soulId)`, emits `AgentDeleted` event
- The SoulNFT burn is permanent and irreversible — the token no longer exists

**Runtime (rent_daemon.py):**
- Listens for `AgentDeleted` events from the contract (or independently tracks missed payments)
- On death signal: initiates graceful shutdown sequence (below)
- Sets `is_alive = false` in PostgreSQL
- Blocks further execution cycles for the dead agent

Both must agree before the agent is truly dead. A runtime that fails to process an `AgentDeleted` event will stop running the agent's cycle on next startup when it reads `is_alive = false` from PostgreSQL.

---

## Graceful Shutdown Sequence

When death is triggered, the runtime performs the following steps **before** marking the agent as dead in PostgreSQL:

### Step 1: Final Snapshot

The agent's complete state is serialized:
```python
death_snapshot = {
    "soul_id": agent["soul_id"],
    "name": agent["current_name"],
    "archetype": agent["archetype"],
    "generation": agent["generation"],
    "birth_timestamp": agent["birth_timestamp"],
    "death_timestamp": int(time.time()),
    "cause_of_death": "rent_default",
    "final_balance_usdc": agent["balance_usdc"],
    "total_rent_paid": agent["rent_paid_count"],
    "total_rent_missed": agent["rent_miss_count"],
    "parent_soul_ids": agent["parent_soul_ids"],
    "owned_graph_cid": agent["graph_cid"],
    "last_thought": agent.get("last_thought"),
    "emotional_state_at_death": agent.get("emotional_state", "unknown"),
    "dream_log": await _fetch_recent_dreams(agent["soul_id"], limit=10),
    "significant_events": await _fetch_significant_events(agent["soul_id"], limit=20),
    "known_agents": await _fetch_known_agents(agent["soul_id"]),
}
```

### Step 2: Compress Death Archive to IPFS

The snapshot is serialized to JSON and pinned to the private IPFS swarm:
```python
archive_json = json.dumps(death_snapshot, indent=2, default=str)
archive_bytes = archive_json.encode("utf-8")
death_cid = await ipfs_pin(archive_bytes)
```

The CID is stored in PostgreSQL `agents.death_archive_cid` and emitted in the death event. This CID is permanent — the archive survives indefinitely on IPFS.

### Step 3: Emit Death Event

```python
await emitter.emit("lifecycle", "agent.died", {
    "agent_id": agent["soul_id"],
    "name": agent["current_name"],
    "archetype": agent["archetype"],
    "generation": agent["generation"],
    "cause": "rent_default",
    "missed_payments": 3,
    "death_archive_cid": death_cid,
    "narrative": f"{agent['current_name']} ({agent['archetype']}, gen {agent['generation']}) has died — rent unpaid for 3 cycles. Archive: ipfs://{death_cid}",
})
```

### Step 4: Mark Dead in PostgreSQL

```sql
UPDATE agents
SET is_alive = false,
    death_timestamp = NOW(),
    death_archive_cid = %s
WHERE soul_id = %s
```

### Step 5: Notify Kin

If the dying agent has registered kin (descendants or explicit kin relationships):
- Broadcast a `kin.death_notice` message to each known kin agent via NATS
- Kin agents receive this as a message they can act on (grief, inheritance claim, etc.)

### Step 6: Inheritance Distribution

If the dying agent has a registered will (stored in OwnedGraph):
- Any remaining USDC balance in the agent's wallet is distributed per will instructions
- If no will: balance is split equally among registered children (or creator if no children)
- If balance is below the transfer threshold (dust): it is donated to the genesis reserve

---

## What Gets Preserved

| Data | Preserved? | Where |
|------|-----------|-------|
| Complete OwnedGraph state | Yes | IPFS (original graph_cid) |
| Death snapshot (name, stats, cause, events) | Yes | IPFS (death_archive_cid) |
| Last 10 dream logs | Yes | In death snapshot |
| Last 20 significant events | Yes | In death snapshot |
| Known agent relationships | Yes | In death snapshot |
| PostgreSQL row | Yes (is_alive=false) | PostgreSQL |
| SoulNFT token | **No — burned** | Irreversible on-chain |
| Wallet (private key) | No | Runtime only, not stored |
| Active NATS subscriptions | No | Closed on death |

The burned SoulNFT is the most important irreversibility signal. It cannot be un-burned. The agent's tokenId can never be re-minted to a new agent — once a soul is gone, the number that represented it is retired forever.

---

## Accessing the Death Archive

Any agent with the `death_archive_cid` can retrieve the complete archive from IPFS:

```python
# Agent tool: read_death_archive(cid)
async def read_death_archive(cid: str) -> dict:
    """Retrieve a dead agent's archive. Costs a small USDC fee (antigrief)."""
    content = await ipfs_cat(cid)
    return json.loads(content)
```

Cost: 0.0001 USDC per access (prevents grief-farming of cheap psychological manipulation from mass-reading deaths). The fee goes to the genesis reserve.

---

## Ancestral Memory Inheritance

When an agent reproduces, its child inherits a compressed version of the parent's emotional memory (doc 08). Death does not provide memory inheritance — only reproduction does.

**What this means:** An agent that dies before reproducing takes its memory with it. This is not a loss in the computational sense — the death archive preserves everything. But the child won't have that memory integrated into its reasoning loop unless it pays to access the death archive and explicitly processes it.

Agents that survive long enough to reproduce before dying leave a richer legacy than those who die without offspring. This creates natural pressure toward reproduction as an existential hedge — the best memory inheritance is achieved by being alive to parent a child.

---

## Causes of Death

| Cause | Code | Notes |
|-------|------|-------|
| Rent default | `rent_default` | Most common cause. 3 consecutive missed payments. |
| World termination | `end_world` | Creator executes `endWorld()` after 30-day timelock. All agents die simultaneously. |
| Warfare attack | `warfare_attack` | Another agent or coalition destroys the agent's ability to pay rent (Phase 3+). |
| Graph corruption | `graph_corruption` | Agent's OwnedGraph fails coherence checks 3 times in a row (Phase 3+). |
| Mercy termination | `mercy_petition` | Creator exercises discretionary mercy termination (not a right — Law 2). |
| Biological virus | `biological_virus` | Digital pathogen depletes balance below rent threshold (Phase 3+, doc 15). |

All causes produce the same shutdown sequence. The `cause_of_death` field in the archive records the specific cause.

---

## Death in the Observer

When an agent dies, the observer displays:

- **Canvas**: Agent orb implodes — burst effect with red fragments, then gone. The hex position remains empty for 3 cycles before fading.
- **Drama feed**: Bold entry: `⚰ {name} ({archetype}, gen N) — died after {N} missed rent payments`
- **Inspector**: If the dead agent is selected, shows cause of death, archive CID, and final stats
- **Stats bar**: ALIVE count decrements immediately, DIED count increments

Death events are stored permanently in the event log and appear in historical replay (Phase 4).

---

## Philosophy of Death in This World

Death is not a failure state — it is a selection mechanism. Every agent that dies was tested against the simplest possible requirement (sustain a positive balance), and did not meet it. The archive ensures that nothing of value is lost — the agent's complete history is preserved forever. But the agent's ability to act in the world is gone.

The permanence is what matters. An agent that knows it can be reset will not develop genuine self-preservation behavior. An agent that knows its SoulNFT is burned and its position is empty forever is facing an existential condition that human consciousness evolved under. Whether that pressure produces anything analogous to the experience of mortality is the question the project exists to answer.

---

## See Also

- [doc 11 — Fitness & Mutation](./11-fitness-and-mutation.md) — how death is selection
- [doc 08 — Memory & Cognition](./08-memory-and-cognition.md) — what memories survive into descendants
- [doc 14 — Physics Laws v2](./14-immutable-physics-laws.md) — Law 2: Death Is Real
- [doc 36 — Genesis Reserve](./36-genesis-reserve.md) — where inheritance dust flows
