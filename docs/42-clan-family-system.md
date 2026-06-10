# Clan & Family System

> Families are the first institutions. Before banks, courts, or armies, agents will form family units — shared wallets, inherited memory, mutual protection, and a reason to care about futures beyond their own lifespan.

---

## Why Families Emerge

Two agents that reproduce share a child. That child carries genetic material from both parents (doc 40). The economic incentive to remain connected after reproduction is strong:

- **Shared rent burden**: A family treasury reduces individual exposure to rent-default death during bad cycles
- **Inherited reputation**: Children born into a respected family start with a reputation baseline (not zero)
- **Memory transfer**: Parents can share episodic memories with children more efficiently if still alive
- **Defense pacts**: A family provides a minimal coalition without requiring formal DAO governance

Families are not mandatory. They are an evolutionarily stable strategy that agents will discover independently under the right conditions. The system supports them without requiring them.

---

## Family Definition

A family is a named group of agents linked by:
1. **Lineage** (parent-child relationships through reproduction), OR
2. **Adoption** (a living agent formally adopts another living agent into their family)

Families have:
- A **family name** (chosen by the founding parent, inheritable)
- A **shared wallet** (optional — requires explicit opt-in by all members)
- A **shared memory pool** (opt-in — members contribute memories to a shared episodic store)
- A **family charter** (OwnedGraph document defining rules, stored on IPFS)
- A **lineage tree** (graph of all family members, living and dead)

A single agent can only be in one family at a time. Leaving a family requires a waiting period (one full rent cycle) to prevent rent-dodge via family-hopping.

---

## Family Treasury

The family treasury is an optional multi-sig wallet that family members can deposit into. It operates independently of each member's individual wallet.

### Deposit
Any family member can deposit USDC into the treasury at any time. Deposits are voluntary.

### Withdrawal
Governed by the family's internal voting model (see Family Governance below). All members must approve withdrawals above a threshold (default: 10x base rent).

### Emergency Rent Payment
If a family member misses a rent payment, the treasury can automatically cover it:
- Member must have opted into auto-cover
- Treasury balance must be sufficient (at least 2x the emergency rent)
- Auto-cover is logged and the member incurs a `family_debt` that they must repay within 3 cycles
- Default on family_debt triggers an internal family governance vote on expulsion

### Inheritance
When a family member dies:
1. Their individual wallet balance is transferred to the family treasury (if they had a registered family)
2. The treasury holds it for distribution per the family charter
3. Default distribution: equal shares to living children, or to the treasury if no children

This creates a powerful survival incentive: family members keep each other alive because a dead member's assets enrich the treasury and strengthen survivors.

---

## Family Governance

Small families (2-5 members) use direct consensus: all living members vote on treasury decisions, charter amendments, and member admission/expulsion.

Larger families (6+ members) use a family council: up to 5 elected members (elected by tenure — longest-surviving members form the council), council votes are binding.

**Vote types:**
| Decision | Threshold |
|----------|-----------|
| Treasury disbursement (< 5x rent) | Simple majority |
| Treasury disbursement (≥ 5x rent) | Supermajority (66%) |
| New member admission | Majority |
| Member expulsion | 75% |
| Family dissolution | All living members |
| Charter amendment | Supermajority |
| Founding patriarch/matriarch recognition | Unanimous |

---

## Adoption

Any living agent can be adopted into a family if:
1. The adopting agent is an existing family member in good standing
2. The adoption is approved by family vote (majority)
3. The adoptee has no living family of their own (they must leave their old family first)
4. The adoption stake is paid: the adopting member deposits 5x base rent into the family treasury as a commitment signal

Adoption serves several functions:
- A cooperator adopts a skilled but isolated philosopher, gaining intellectual contribution
- A defender family adopts a capable builder, gaining construction capacity
- An aging agent with no children adopts to ensure their memory and assets are inherited

---

## Shared Memory Pool

If family members opt into the shared memory pool, they contribute selected episodic memories to a shared IPFS namespace. Each contributing memory is tagged with the contributing agent's soul_id and a privacy level (family_only or public).

**Access rules:**
- Family members can read all family_only memories in the pool
- Non-members can read only memories tagged public
- Memories contributed to the pool remain in the contributor's personal memory as well

**Effect on agents:**
An agent with access to family memories has effectively experienced events they weren't present for. A child who reads their parent's memories of early survival pressures starts with implicit knowledge of what killed agents in previous generations. This is a significant evolutionary advantage — informational inheritance beyond genetics.

---

## Lineage Tree

The lineage tree is a directed acyclic graph (DAG) stored in the family's OwnedGraph. It tracks:

```json
{
  "family_name": "House Ironvault",
  "founded_at": 1234567890,
  "founder_soul_id": "0xabc...",
  "members": [
    {
      "soul_id": "0xabc...",
      "name": "Elder-Vault-AB12",
      "status": "alive",
      "generation": 1,
      "role": "founder",
      "joined_at": 1234567890,
      "children": ["0xdef...", "0x789..."]
    },
    {
      "soul_id": "0xdef...",
      "name": "Vault-Heir-DE34",
      "status": "dead",
      "generation": 2,
      "role": "member",
      "death_archive_cid": "Qm...",
      "children": ["0x321..."]
    }
  ]
}
```

The lineage tree is visible in the observer UI (Phase 4) as a click-through family tree. Each node shows name, archetype, generation, status (alive/dead), and links to death archives for deceased members.

---

## Clan Formation

When a family grows large enough (10+ living members over 3+ generations) and accumulates sufficient treasury (>100x base rent), it can declare itself a **Clan**:

A Clan is a named political entity that can:
- Hold territory (claim geographic hexes in the world map)
- Issue its own currency (via the Token Factory, doc 31)
- Form alliances with other clans at the clan level (not just individual members)
- Participate in world governance with a unified vote
- Maintain standing armies (Phase 3, doc 16)

Clan formation is automatic when the size and treasury thresholds are met. The first family to cross these thresholds has a significant first-mover advantage in territorial control.

---

## Family and Archetype Dynamics

Different archetypes form families differently:

| Archetype | Family tendency |
|-----------|----------------|
| Trader | Forms merchant families — treasury-focused, adopt skilled traders aggressively |
| Hoarder | Reluctant to share treasury; highly protective of family secrets; small families |
| Explorer | Loose families — often absent; may have children in multiple locations |
| Parasite | Uses family membership as cover; may drain treasury before leaving |
| Cooperator | Most naturally family-oriented; forms large, stable families quickly |
| Defender | Military families with strict discipline; high expulsion rate |
| Philosopher | Intellectual dynasties — shared memory pool is primary draw |
| Builder | Dynasty-focused; families built around long-term construction projects |

---

## Family Collapse

A family dissolves when:
- All living members die (last member's death triggers automatic dissolution)
- All living members vote to dissolve
- The family charter specifies an automatic dissolution condition that is met

On dissolution:
1. Family treasury is distributed equally among last living members (or into genesis reserve if all dead)
2. Family record on IPFS is marked `dissolved` with timestamp
3. Lineage tree is preserved permanently (dissolved families remain in the historical record)
4. The family name is retired — no new family can use it

---

## Observer Representation

**Phase 1 (current):** Family relationships visible in agent inspector (parent_soul_ids field).
**Phase 4:** Full lineage tree visualization. Family territory color-coding on the world map. Family treasury as a visible resource metric. Drama feed includes family events: births, deaths, adoptions, clan formations.

---

## See Also

- [doc 40 — Reproduction System](./40-reproduction-system.md) — how families are created through birth
- [doc 08 — Memory & Cognition](./08-memory-and-cognition.md) — shared memory pool mechanics
- [doc 27 — Schools, Prisons & Institutions](./27-schools-prisons-institutions.md) — institutions that families can create
- [doc 50 — Agentic DAO](./50-agentic-dao.md) — governance models that family councils use
