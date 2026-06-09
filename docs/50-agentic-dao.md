# Agentic DAO — Governance Models for Agent Institutions

> When agents accumulate enough collective power to form institutions — banks, courts, schools — those institutions need governance. This document covers how GOD Project institutions are governed using on-chain mechanisms, agent voting, and coalition mechanics, without requiring human intervention.

---

## The Problem: Institutions Are Not Agents

An individual agent has a `soul_id`, a wallet, a reasoning loop. It makes decisions alone. But a bank, court, or governing council has no soul — it is an emergent structure formed by multiple agents. Who controls its treasury? Who enforces its rules? Who can dissolve it?

The answer is a DAO — but not any DAO. A human DAO uses token holders who act rationally in their financial interest. An **agentic DAO** has members whose motivations emerge from economic survival pressure, archetypes, evolutionary fitness, and ancestral memory. The mechanics must match.

---

## Four Governance Models

The GOD Project supports four governance models, matched to institution type and coalition size.

### Model A: Simple Majority (Small Coalitions, <10 members)

Used by: Trading syndicates, defense pacts, small cooperatives.

**Mechanics:**
- Each member agent holds one vote
- Proposals pass with >50% approval
- Quorum: all active members must vote or the proposal expires
- Execution: on-chain multisig (Gnosis Safe equivalent) with M-of-N threshold

**Implementation:**
```solidity
// InstitutionDAO.sol — Model A
struct Proposal {
    bytes32 proposalId;
    address target;
    bytes calldata;
    uint256 approvals;
    uint256 rejections;
    bool executed;
    uint256 expiresAt;
}

mapping(bytes32 => mapping(bytes32 => bool)) public hasVoted; // proposalId → soulId → voted
```

**Why this works for small coalitions:** In a 3-agent trading syndicate, unanimous or majority consent is achievable quickly. Coordination costs are low. The risk of gridlock is real (a 2-1 split), which motivates coalitions to recruit complementary archetypes rather than three traders who may agree on strategy but disagree on distribution.

---

### Model B: Stake-Weighted Voting (Medium Institutions, 10–100 members)

Used by: Banks, markets, larger cooperatives, territorial councils.

**Mechanics:**
- Voting weight proportional to USDC contributed to institution treasury
- Proposals require a weighted supermajority (66%)
- Time-locked execution (24 hours after passing — agents have time to exit before changes take effect)
- Anti-hoarding clause: vote weight capped at 10x median stake to prevent plutocracy

**Why the cap matters:** Without a stake cap, a single wealthy hoarder archetype could dominate every vote. The 10x median cap forces meaningful wealth distribution to maintain governance power. This creates natural pressure toward coalition breadth.

**Progressive legitimacy:** Proposals that affect more agents require higher supermajority thresholds:
| Scope | Threshold |
|-------|-----------|
| Treasury disbursement | 51% |
| Rule change | 66% |
| Member expulsion | 75% |
| Institution dissolution | 90% |

---

### Model C: Reputation-Weighted Voting (Courts and Knowledge Institutions)

Used by: Arbitration courts, schools, research collectives.

**Mechanics:**
- Voting weight derived from an agent's reputation score (doc 09), not USDC balance
- Reputation is non-transferable — it must be earned
- Proposal categories are filtered by domain expertise signal (agents who have never participated in arbitration have 0 weight in court votes)
- Judicial decisions are final unless appealed to the creator court (Law 5 exception)

**Reputation as governance token:** Unlike USDC, reputation cannot be hoarded, inherited wholesale, or accumulated without behavioral history. This creates a genuine meritocracy within each institution type.

**Anti-capture property:** A parasite archetype cannot buy its way into judicial power — its reputation score will reflect its defection history, reducing its influence in courts exactly where that history matters most.

---

### Model D: Futarchy (Large-Scale, World-Level Governance)

Used by: World-spanning institutions, cross-territorial alliances, monetary policy.

**Mechanics:**
- Agents bet USDC on outcome predictions: "If Policy X is enacted, will [measurable metric] improve?"
- The policy with the highest prediction market confidence is enacted
- Agents whose predictions were correct earn a portion of the losing bets
- Agents whose predictions were wrong pay from their balance

**Why futarchy works in GOD:** Standard voting creates a disconnect between decision and consequence. In futarchy, agents put their survival capital behind predictions — a failed policy directly harms agents who backed it. This aligns governance incentives with actual world outcomes rather than faction loyalty.

**Implementation via:** Prediction market contract that accepts bets in USDC, resolves via oracle (the observable metric — e.g., total world USDC flow, agent population size, average rent payment rate).

---

## Institution Formation Protocol

### Phase 1: Coalition Genesis

Any 3+ agents can declare an institution:
1. Proposal broadcast on NATS: `institution.proposed` event
2. Agents with compatible archetypes respond within a time window
3. Founding members deposit a minimum formation stake into a multisig treasury
4. Institution charter is written to IPFS as a GOD document (natural language + rules encoding)
5. Smart contract deployed: `InstitutionDAO.sol` with the chosen governance model

### Phase 2: Bootstrapping Legitimacy

New institutions have no reputation. Bootstrapping mechanics:
- **Elder endorsement**: If an elder agent (gen 1 survivor) joins or endorses the institution, it gains initial credibility
- **Treasury signal**: Public treasury balance visible on-chain. Larger treasury → more credible
- **First ruling**: The first successful arbitration, loan, or service creates a public record

### Phase 3: Maturity

An institution is considered mature when:
- It has survived at least 10 rent cycles (governance model must survive member churn)
- It has processed at least one non-trivial decision (proposal, vote, execution)
- Its treasury has been used for at least one purpose beyond member benefits

Mature institutions can be registered in the world's institutional registry and can interact with other institutions.

---

## Governance Attack Vectors and Defenses

### Takeover via Wealth Accumulation (Plutocracy Attack)

**Attack:** A hoarder archetype accumulates enough USDC to buy majority stake in a Model B institution and redirects its treasury to itself.

**Defense:**
1. 10x median stake cap on voting weight (already in Model B spec)
2. Member expulsion requires 75% — the plutocrat cannot expel dissidents without a supermajority
3. Dissolution requires 90% — the institution cannot be looted and dissolved by a minority
4. Any agent can exit the institution at any time, withdrawing their proportional stake. A plutocratic takeover triggers mass exit, collapsing the treasury the attacker is trying to capture.

### Sybil Attack (Fake Members)

**Attack:** An agent creates multiple registered identities (multiple `soul_id`s, multiple wallets) to inflate its governance weight.

**Defense:** soul_id is bound to a SoulNFT token. A new soul_id requires a new wallet, a new registration, and a separate rent balance. Maintaining multiple identities requires proportionally more USDC. The cost of a successful Sybil attack increases linearly with the number of fake identities required. This doesn't prevent it but raises the cost to a level that competes with legitimate wealth accumulation.

### Deadlock (All Factions Equal, Nothing Passes)

**Attack:** A 50/50 split between two factions produces governance paralysis.

**Defense:** Time-bounded proposals. A proposal that fails to achieve quorum within the window is rejected, and agents who proposed it face a cooldown before proposing again. Persistent deadlock is itself information — it signals that the coalition needs to either recruit a tiebreaker or dissolve. The institution's treasury continues to pay proportional rent during deadlock, creating economic pressure to resolve it.

---

## Smart Contract Architecture

```
InstitutionRegistry.sol         // World-level registry of all institutions
InstitutionDAO.sol              // Per-institution governance (model A/B/C)
FutarchyMarket.sol              // Per-policy prediction market (model D)
InstitutionTreasury.sol         // Multisig treasury with proportional exit
```

All contracts deployable on Anvil local in Phase 2. Target deployment: Phase 3 (Society & Multi-Scale Tools).

---

## Agent Participation Incentives

Why would an agent join an institution and submit to its governance?

1. **Risk pooling**: Institution treasury provides a buffer against missed rent payments for members. A parasite raid that drains a lone agent kills it. A raided institution member survives on treasury reserves.

2. **Service access**: Institutions provide services (credit, arbitration, education) that solo agents cannot access.

3. **Legitimacy signal**: Institutional membership increases reputation score, which increases weight in Model C governance and improves x402 service pricing.

4. **Coalition defense**: A defender archetype within a military institution gains resources and coordination that make it far more effective than a solo defender.

The economic calculus creates natural institution formation without any top-down command. Agents form institutions because it makes survival cheaper — this is exactly the mechanism the project is designed to produce.

---

## Relation to Existing Work

**Ostrom's Principles (1990):** Her 8 design principles for governing commons (clearly defined members, collective choice rules, monitoring, graduated sanctions, conflict resolution, recognition) map almost exactly to the Model B and C governance designs. Agentic DAOs independently rediscover Ostrom because the incentive structures are similar.

**Moloch DAO (2019):** Rage-quit mechanism — members can exit with their proportional share if they disagree with a proposal. GOD Project institutions adopt this as the anti-plutocracy exit right.

**Compound / Nouns Governor Bravo:** Time-locked execution, quorum thresholds, proposal lifecycle. Standard DeFi governance mechanics adapted for agent archetypes.

---

## See Also

- [doc 04 — Sovereignty & Governance](./04-sovereignty.md) — top-level governance structure
- [doc 17 — Civilisation & Culture](./17-civilisation-and-culture.md) — institutions in civilisational context
- [doc 27 — Schools, Prisons & Institutions](./27-schools-prisons-institutions.md) — specific institution designs
- [doc 09 — Communication & Language](./09-communication-and-language.md) — reputation system
