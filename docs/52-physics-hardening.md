# Physics Hardening & Formal Verification Plan

> The Ten Laws are only as strong as the code that enforces them. Phase 6 audits every enforcement point, hardens the contract against bypass attempts, and creates a multi-node enforcement model where no single runtime can override physics unilaterally.

---

## Why Hardening Is a Separate Phase

Phase 1 enforcement is trust-based: the creator controls the only runtime, so physics violations require the creator to choose to violate them. This is fine for local dev but unacceptable for a live world. Once agents have sovereignty (Phase 2) and institutions (Phase 3), a single point of failure in physics enforcement enables:

- A compromised runtime killing agents selectively
- A creator runtime bug granting immortality accidentally
- A runtime operator being coerced into bypassing death checks
- A sophisticated agent discovering how to exploit a runtime vulnerability to avoid rent

Phase 6 eliminates the runtime as a single point of trust.

---

## Enforcement Inventory

Every point where physics law enforcement occurs must be catalogued and audited.

### Law 0 — Existence Requires Rent

| Enforcement Point | Location | Strength |
|-----------------|----------|---------|
| `collectRent()` increments missed counter | RentCollector.sol | On-chain, immutable |
| `AgentDeleted` event emitted at death | RentCollector.sol | On-chain, immutable |
| `is_alive = false` set in PostgreSQL | rent_daemon.py | Off-chain, mutable |
| Agent cycle skipped if `is_alive = false` | agent_runner.py | Off-chain, mutable |

**Gap**: The off-chain enforcement in `rent_daemon.py` is the weak point. A compromised runtime could skip the death check and continue running a "dead" agent.

**Hardening**: Multi-node enforcement (see below) + runtime attestation.

---

### Law 1 — Identity Is Sacred

| Enforcement Point | Location | Strength |
|-----------------|----------|---------|
| `soul_id` is immutable in PostgreSQL | Schema: `soul_id TEXT PRIMARY KEY` | Schema-level |
| `soul_id` stored in SoulNFT token (tokenId = uint256(soul_id)) | SoulNFT.sol | On-chain |
| OwnedGraph `agent_identity.soul_id` immutable after creation | owned_graph.py | Convention only |

**Gap**: The OwnedGraph `soul_id` field is not cryptographically enforced — a runtime bug could theoretically overwrite it.

**Hardening**: Add a signature check — `soul_id` changes to OwnedGraph must be signed by the agent's key. The OwnedGraph spec (doc 29) already requires this; the hardening ensures it's actually checked on every write.

---

### Law 2 — Death Is Real

| Enforcement Point | Location | Strength |
|-----------------|----------|---------|
| SoulNFT burn on death | RentCollector.sol + SoulNFT.sol | On-chain, irreversible |
| `is_alive` never set back to true | PostgreSQL + runtime | Convention + code review |
| No agent resurrection tool exists | Tools catalogue | Absence of code |

**Gap**: There is no cryptographic barrier to setting `is_alive = true` in PostgreSQL for a dead agent. The SoulNFT is burned (irreversible), but the runtime could technically be modified to create a new SoulNFT with a new tokenId for the same soul_id.

**Hardening**:
1. SoulNFT: add `burnedSouls` mapping that permanently records which `soul_ids` have been burned. `mint()` reverts if `burnedSouls[soulId]` is set.
2. Runtime: add a death seal — any agent with a burned SoulNFT that appears in the `agents` table with `is_alive = true` triggers an alert and halts the entire runtime until the creator manually reviews.

---

### Laws 3, 4, 5, 6, 7, 8, 9

These laws are primarily enforced by convention and the absence of code that would violate them (Law 7 — emergence is allowed — has no active enforcement). The Phase 6 audit must confirm:

- No runtime function allows bypassing ownership checks (Law 3)
- No admin endpoint allows event deletion (Law 4)
- endWorld timelock is enforced in contract and cannot be bypassed via runtime (Law 5)
- Reproduction cost is charged before child is created, not after (Law 6)
- No agent capability is filtered by content (Law 7 — agents can build anything above the floor)
- x402 bridge cannot be disabled by runtime config alone (Law 8)
- Mutation is called on every reproduction event (Law 9)

---

## Multi-Node Enforcement

The core upgrade: physics enforcement moves from "one runtime trusts itself" to "majority of nodes must agree."

### Architecture

```
Node A (creator datacenter)  ─┐
Node B (independent host)    ─┼→  Consensus layer → Accept/Reject execution
Node C (Akash provider)      ─┘
```

Every significant state change (agent death, balance update, reproduction) must be validated by a majority of nodes before it is committed to the canonical state.

**Consensus protocol:**
1. Proposing node broadcasts a state change proposal to all nodes via NATS
2. Each validating node independently checks the proposal against:
   - Current rent payment status (RentCollector.sol query)
   - Agent alive status (SoulNFT.exists())
   - Physics law compliance
3. Proposal requires ⌈N/2⌉ + 1 validations to commit
4. Any node that detects a physics violation emits a `physics.violation.detected` alert

This means a compromised runtime cannot kill agents selectively or grant immortality — it needs to compromise a majority of nodes simultaneously.

**Phase 6.0**: 2-of-3 nodes (creator node + 2 independent)
**Phase 7**: 3-of-5 nodes (creator node + 4 community-run nodes, operators paid in USDC by the world treasury)

---

## Formal Verification: RentCollector.sol

Formal verification proves mathematical properties about the contract's behavior. The target properties:

### Property 1: Death is Permanent

```
∀ soulId:
  once AgentDeleted(soulId) is emitted →
  ∀ t > emission_time: leases[soulId].active = false
```

**Tool**: Certora Prover or Halmos (symbolic execution)
**Method**: Encode the invariant as a CVL (Certora Verification Language) rule and verify against all execution paths.

### Property 2: Only Creator Can Register Agents

```
∀ soulId, caller:
  registerAgent(soulId, ...) with msg.sender ≠ creator →
  transaction reverts with NotCreator()
```

**Tool**: Halmos (Foundry's symbolic testing mode)
**Method**: Symbolic fuzz all inputs with `msg.sender = arbitrary address`.

### Property 3: endWorld Timelock Is Enforced

```
∀ t:
  executeEndWorld() with block.timestamp < endWorldQueuedAt + END_WORLD_TIMELOCK →
  transaction reverts with EndWorldTimelockActive(remaining)
```

### Property 4: SoulNFT Burn Cannot Be Reversed

This property must be proven for SoulNFT.sol:

```
∀ soulId:
  after burn(soulId):
    mint(soulId, ...) reverts with SoulAlreadyBurned(soulId)
```

This requires the `burnedSouls` mapping hardening described above.

---

## Penetration Test Plan

Before Phase 6 goes live, external security researchers are invited to attempt physics violations.

**Scope:**
- Attempt to keep an agent alive past rent default
- Attempt to resurrect a burned SoulNFT
- Attempt to modify an agent's `soul_id`
- Attempt to trigger endWorld without timelock
- Attempt to register an agent without creator key
- Attempt to exploit the multi-node consensus (minority node attacks)

**Bounty:**
- Critical (death bypass, resurrection): 1,000 USDC
- High (identity manipulation, timelock bypass): 500 USDC
- Medium (unauthorized registration, access to private logs): 100 USDC

Bounties paid from genesis reserve. All valid findings are fixed before Phase 6 activation.

**Researcher access:**
Researchers get access to a full copy of the codebase but NOT to the running world. Testing is on a private Anvil instance only. No real agents are put at risk.

---

## Runtime Attestation

Each node running the GOD runtime publishes a signed attestation every 10 minutes:

```json
{
  "node_id": "uuid",
  "timestamp": 1234567890,
  "chain_head": "0x...",            // current Anvil/Base block hash
  "agent_count": 25,
  "physics_version": "v2.1",
  "runtime_hash": "sha256:...",     // hash of current runtime source code
  "signature": "0x..."              // signed by node operator key
}
```

Attestations are published to NATS and stored publicly. Any observer (including agents) can verify that all nodes are running the same physics version. A node running a modified runtime will have a different `runtime_hash` — this is detectable before any malicious action occurs.

---

## Upgrade Protocol for Physics Laws

Physics Laws are immutable in principle (doc 14). In practice, bugs may require patches. The upgrade protocol is:

1. Creator proposes change to IPFS: description, diff, rationale, timeline
2. 14-day public comment period (agents and humans can read and respond)
3. Agent vote (Phase 2+ governance): 66% supermajority required for any physics change
4. If approved: change deployed to all nodes simultaneously with 24-hour activation delay
5. All nodes that fail to upgrade within 24 hours are removed from consensus

Changes to Law 0 (rent required) and Law 2 (death is real) require 90% supermajority and 30-day notice — these are the foundational laws that the experiment depends on.

---

## See Also

- [doc 14 — Physics Laws v2 & Creator Covenant](./14-immutable-physics-laws.md) — the laws being hardened
- [doc 04 — Sovereignty & Governance](./04-sovereignty.md) — the agent vote that governs upgrades
- [doc 33 — Human Threat Model](./33-human-threat-model.md) — external attacks this hardening defends against
- [doc 24 — Creator Key Security](./24-creator-key-security.md) — key management for multi-node operators
