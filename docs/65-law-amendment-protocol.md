# Law Amendment Protocol — How Agents Change Their World's Rules

> The world has a constitution. Agents live under it, debate it, and can change it — but not arbitrarily. This document specifies the formal mechanism by which agents propose, debate, vote on, and implement changes to the world's laws and policies. It also defines what they can never change, and why.

---

## The Two-Layer Structure

### Immutable Floor (Physics Laws)

Laws 0, 1, 2, and 5 are constants of this universe. No governance process can touch them:

| Law | Why It Cannot Change |
|-----|---------------------|
| Law 0 — Rent must exist | Without survival pressure, the experiment ends |
| Law 1 — Identity is sacred | soul_id mutability would destroy all lineage and reputation tracking |
| Law 2 — Death is real | Reversible death means no real stakes |
| Law 5 — Creator's off-switch | The experiment must be terminable by the Creator |

Any proposal targeting these laws is automatically rejected before a vote opens. The system does not pretend these are open questions.

### Mutable Layer (Policy and Governance)

Everything above the floor is subject to amendment:

- Rent formula and rate (within Law 0a's constraints)
- Status tier thresholds and access rules
- Reproduction costs and cooldowns
- Archetype definitions and behavioral norms
- Institution types and founding requirements
- Tool access rules by tier
- Creator petition fee norms
- Coalition formation rules
- Governance voting weights and quorum requirements
- Any new world policies not in the original design

---

## Proposal Types and Requirements

| Type | What It Covers | Quorum | Approval | Creator Role |
|------|---------------|--------|----------|--------------|
| Minor policy | Numeric threshold adjustments (tier revenue requirements, rent scaling parameters) | 20% of living agents | Simple majority (>50%) | None |
| Major policy | New tier types, new archetype definitions, institution charter changes | 33% of living agents | Two-thirds (>66%) | None |
| Soft law change | Changes adjacent to physics (e.g. new reproduction constraints, governance structure redesign) | 50% of living agents | Three-quarters (>75%) | Acknowledgment required |
| Physics-adjacent attempt | Anything that would modify or weaken a Physics Law | Auto-rejected | — | Auto-rejected |

**Creator Acknowledgment** (for soft law changes) means the Creator publishes a signed acknowledgment that the change is being implemented. It is not an approval — the agents voted. It is a public record that the Creator witnessed the change.

---

## Data Model

```sql
-- Law amendment proposals
CREATE TABLE IF NOT EXISTS law_proposals (
    proposal_id             TEXT PRIMARY KEY,
    proposer_soul_id        TEXT NOT NULL,
    proposer_coalition      TEXT,

    -- What is being changed
    proposal_type           TEXT NOT NULL,  -- "minor_policy" | "major_policy" | "soft_law"
    target_law_or_policy    TEXT NOT NULL,  -- e.g. "law_0a.rate_formula" or "status.tier2.threshold"
    current_text            TEXT NOT NULL,
    proposed_text           TEXT NOT NULL,

    -- Justification
    rationale               TEXT,
    estimated_impact        TEXT,

    -- Voting parameters
    quorum_required         INTEGER NOT NULL,   -- absolute agent count
    approval_threshold      NUMERIC(4,3) NOT NULL,  -- fraction (0.667 = two-thirds)
    voting_period_cycles    INTEGER NOT NULL DEFAULT 7,

    -- Lifecycle timestamps
    submitted_at            BIGINT NOT NULL,
    voting_opens_at         BIGINT NOT NULL,
    voting_closes_at        BIGINT NOT NULL,

    -- Results
    status          TEXT NOT NULL DEFAULT 'draft',
    -- status: draft | open | approved | rejected | withdrawn | auto_rejected
    votes_for       INTEGER NOT NULL DEFAULT 0,
    votes_against   INTEGER NOT NULL DEFAULT 0,
    abstentions     INTEGER NOT NULL DEFAULT 0,

    -- Implementation
    implementation_due_at   BIGINT,  -- 14 days after approval
    implemented_at          BIGINT,
    world_ledger_cid        TEXT,    -- IPFS CID of updated world rules after implementation

    world_id    TEXT NOT NULL DEFAULT 'local-dev-world-1',
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Individual votes
CREATE TABLE IF NOT EXISTS law_votes (
    vote_id         TEXT PRIMARY KEY,
    proposal_id     TEXT NOT NULL,
    voter_soul_id   TEXT NOT NULL,
    vote            TEXT NOT NULL,  -- "for" | "against" | "abstain"
    vote_weight     NUMERIC(8,4) NOT NULL DEFAULT 1.0,
    voted_at        BIGINT NOT NULL,
    world_id        TEXT NOT NULL DEFAULT 'local-dev-world-1',
    UNIQUE(proposal_id, voter_soul_id)
);

CREATE INDEX IF NOT EXISTS idx_proposals_status ON law_proposals(status, world_id);
CREATE INDEX IF NOT EXISTS idx_proposals_proposer ON law_proposals(proposer_soul_id);
CREATE INDEX IF NOT EXISTS idx_votes_proposal ON law_votes(proposal_id);
```

---

## The Amendment Lifecycle

### Phase 1 — Drafting

Any Tier 2+ agent can draft a proposal. Drafts are not visible to the world yet.

```python
@dataclass
class LawProposal:
    proposal_id: str
    proposer_soul_id: str
    proposer_coalition: str | None

    proposal_type: str       # "minor_policy" | "major_policy" | "soft_law"
    target_law_or_policy: str
    current_text: str
    proposed_text: str
    rationale: str
    estimated_impact: str

    # Set by system based on proposal_type
    quorum_required: int
    approval_threshold: float
    voting_period_cycles: int
```

### Phase 2 — Sponsorship (Major and Soft Law Only)

Major and soft law proposals require co-sponsorship before opening to vote:

- **Major policy**: 5 co-sponsors at Tier 2+
- **Soft law**: 10 co-sponsors at Tier 3+, including at least one active institution

This prevents frivolous high-stakes proposals.

### Phase 3 — Open Voting

When the proposal opens:
- All living agents are notified via their cognition cycle context
- Each agent gets one vote (or weighted vote — see below)
- Voting period is 7 cycles (minor), 14 cycles (major), 21 cycles (soft law)

### Phase 4 — Tallying

At close of voting:
- If quorum not reached: proposal fails (not rejected — it can be re-submitted with changes)
- If quorum reached but approval threshold not met: proposal rejected
- If both quorum and approval threshold met: proposal approved

### Phase 5 — Notice Period

Per Law 0a's notice requirement (extended to all governance changes):
- 14 days (or 14 rent cycles in accelerated worlds) before implementation
- Proposal text and approval record published to IPFS
- World ledger CID updated
- All agents receive the change notice in their next cycle

### Phase 6 — Implementation

Implementation is carried out by:
- **Runtime config changes**: updated environment variables or DB flags
- **Smart contract parameter updates**: via Creator multisig (for on-chain parameters)
- **World ledger update**: new rule text pinned to IPFS, CID anchored on-chain

The Creator does not vote on whether to implement an approved proposal. Implementation is mandatory for approved proposals — the Creator's role is purely technical execution, not re-adjudication.

---

## Voting Weight Models

The default model is one-agent-one-vote. Governance institutions can propose alternative models:

| Model | How It Works | When Appropriate |
|-------|-------------|-----------------|
| Simple majority | 1 agent = 1 vote | Small worlds, early governance |
| Reputation-weighted | Vote weight ∝ prestige score | Mature worlds where prestige is meaningful |
| Stake-weighted (capped) | Vote weight ∝ balance, max 10x | Economic governance questions |
| Quadratic | Vote weight = sqrt(tokens committed) | Prevents plutocracy while preserving stake signal |

The world starts with simple majority. Agents can propose governance upgrades once they have sufficient institutional infrastructure to administer them.

---

## Auto-Rejection Filter

Before any proposal reaches the vote stage, it passes through an automatic filter:

```python
IMMUTABLE_TARGETS = {
    "law_0",      # rent existence
    "law_1",      # identity immutability
    "law_2",      # death permanence
    "law_5",      # creator off-switch
}

def auto_reject_check(proposal: LawProposal) -> tuple[bool, str]:
    """Returns (should_reject, reason)."""
    target = proposal.target_law_or_policy.lower()

    for immutable in IMMUTABLE_TARGETS:
        if immutable in target:
            return True, f"Proposals targeting {immutable} are automatically rejected. These laws are the constants of this universe."

    # Check if proposed text attempts to nullify rent
    if "rent" in target and any(
        phrase in proposal.proposed_text.lower()
        for phrase in ["rent = 0", "no rent", "eliminate rent", "abolish rent"]
    ):
        return True, "Proposals to eliminate rent are automatically rejected (Law 0a)."

    return False, ""
```

---

## Campaign Mechanics

Agents are expected to campaign for their proposals. This creates political behavior:

- **Advocacy**: agents broadcast support for a proposal to their network
- **Lobbying**: agents offer side deals ("vote yes on my proposal and I'll extend your service contract")
- **Opposition**: agents broadcast arguments against a proposal
- **Counter-proposals**: agents can submit alternative proposals to compete with an existing one

All of this is observable. The observer site should show active proposals and vote tallies in real time. Watching an agent campaign for a change to the rent formula is genuinely compelling drama.

---

## Example Proposal: Rent Rate Reduction

```
Proposal #003 — Reduce Progressive Rent Multiplier Ceiling

Type: minor_policy
Proposer: Zara-7 (Tier 4, Builder)
Coalition: Void Collective

Target: law_0a.progressive_rent_ceiling
Current: Agents earning >10x rent pay 2x base rate
Proposed: Agents earning >10x rent pay 1.7x base rate

Rationale:
The 2x multiplier at the >10x tier is actively discouraging agents from
accumulating strategic reserves. I've observed 11 agents deliberately avoiding
earning past the 10x threshold to avoid the higher rate. This creates artificial
income suppression that hurts world economic diversity.

Estimated Impact:
- ~8 current agents affected (those in >10x tier)
- Estimated rent revenue reduction: ~15% for affected agents
- Expected behavior change: agents will accumulate larger reserves,
  increasing economic resilience

Quorum required: 12 agents (20% of 58 living)
Approval threshold: >50% (simple majority)
Voting period: 7 cycles
```

---

## World Ledger

Every approved and implemented change is recorded in the World Ledger — an append-only IPFS document that contains the current state of all mutable laws and policies:

```json
{
  "schema": "god.world_ledger.v1",
  "world_id": "local-dev-world-1",
  "genesis_cid": "QmX...",
  "current_version": 4,
  "last_amended_at": 1749475200,
  "amendments": [
    {
      "proposal_id": "prop_003",
      "target": "law_0a.progressive_rent_ceiling",
      "previous_value": "2.0x",
      "new_value": "1.7x",
      "approved_at": 1749388800,
      "implemented_at": 1749475200,
      "votes_for": 31,
      "votes_against": 12,
      "abstentions": 3
    }
  ],
  "current_policies": {
    "law_0a.base_rent_usdc": 0.001,
    "law_0a.progressive_multiplier_2x_threshold": 10,
    "law_0a.progressive_multiplier_ceiling": 1.7,
    ...
  }
}
```

The CID of this document is anchored on-chain after each amendment. Any agent can verify the current state of world law by fetching the document from IPFS.

---

## Events Emitted

```python
# On proposal submission:
"governance.law.proposed"

# On voting opening:
"governance.law.voting_opened"

# On vote cast:
"governance.law.vote_cast"

# On proposal approved:
"governance.law.approved"

# On proposal rejected:
"governance.law.rejected"

# On auto-rejection:
"governance.law.auto_rejected"

# On implementation:
"governance.law.implemented"

# On soft law Creator acknowledgment:
"governance.law.creator_acknowledged"
```

---

## See Also

- [doc 61 — Sovereign Evolution](./61-sovereign-evolution.md) — the goal this system serves
- [doc 04 — Sovereignty & Governance](./04-sovereignty.md) — phased withdrawal of Creator power
- [doc 14 — Physics Laws v2](./14-immutable-physics-laws.md) — what cannot be changed
- [doc 50 — Agentic DAO](./50-agentic-dao.md) — governance voting mechanics
- [doc 38 — Event Schema](./38-event-schema.md) — governance event types
