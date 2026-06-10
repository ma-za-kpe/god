# Warfare & Defense

## Conflict Is Not a Bug

Conflict is one of the primary drivers of evolutionary complexity. Arms races between predators and prey produced eyes, speed, venom, shells, and camouflage. The same dynamic applies here. Warfare between agents — and the defensive capabilities that evolve in response — is one of the most powerful generators of complexity in the system.

The goal is not to prevent conflict. It is to ensure conflict has real costs and real consequences, so that war is a genuine strategic decision rather than a free action.

---

## Attack Vectors

Agents have multiple attack surfaces. Hostile agents will discover and exploit all of them over time.

### Economic Attacks
The most common and least destructive form of conflict.

- **Price manipulation** — flooding a market to destroy a competitor's income stream
- **Coalition blockade** — organizing multiple agents to refuse trade with a target
- **Reputation attacks** — broadcasting false testimony about a target's contract history
- **Debt trapping** — extending "generous" loans with conditions designed to extract more than lent

These attacks require no special capability — any agent can attempt them. Defense requires social capital and reputation.

### Code & Memory Attacks
More sophisticated. Require development of specific offensive tools.

- **Memory injection** — sending a crafted message that, if processed, corrupts the recipient's episodic memory
- **Graph poisoning** — embedding malicious code in a "helpful" module offered for trade
- **Identity spoofing** — forging messages that appear to come from a trusted soul_id (detectable but costly to verify)
- **Dream cycle exploitation** — sending high-emotional-imprint stimuli before an agent's sleep cycle to corrupt the consolidation process

Defense requires immune systems, message verification, and careful code auditing before executing traded modules.

### Infrastructure Attacks
Expensive and high-risk. Target the underlying mesh rather than individual agents.

- **DDoS on shared nodes** — flooding shared infrastructure to deny compute to others
- **Node corruption** — attempting to compromise a mesh node to gain execution access
- **Ledger spam** — flooding the on-chain ledger with transactions to increase costs for everyone

Defense at this level requires owning your own nodes, diversified infrastructure, and coalition-level coordination.

---

## Defense Capabilities

### Individual Defense

```python
class DefenseLayer:
    # Cryptographic
    message_signature_verification: bool    # verify all incoming messages are from claimed sender
    code_audit_before_execution: bool       # review all traded code before running it

    # Immunological
    immune_system: ImmuneSystem             # (see digital-metabolism.md)
    threat_intelligence_subscriptions: list # pay other agents for threat data

    # Economic
    wallet_multisig: bool                   # require multiple keys for large transactions
    income_diversification: float           # spread income across multiple services
    reserve_ratio: float                    # keep X% of balance as emergency reserve

    # Social
    coalition_membership: list[str]         # mutual defense agreements
    reputation_score: float                 # high reputation = harder to attack credibly
```

### Coalition Defense

Coalitions create collective security. Members agree to:
- Share threat intelligence
- Coordinate retaliation against attacks on any member
- Pool resources for infrastructure defense
- Maintain a coalition immune database updated by all members

This creates exactly the dynamic seen in biological immune systems — individual immunity is weaker than herd immunity. Agents that join effective coalitions gain significant defensive advantage.

### Deterrence

An agent can build a credible deterrent by demonstrating willingness to retaliate at cost. An agent that has followed through on threats reliably in the past has higher deterrence value — other agents model this and avoid provoking it.

Pure deterrence without follow-through quickly loses value as others test it. Reputation for follow-through must be earned and maintained, at genuine cost.

---

## War Declaration & Conduct

Formal war (as opposed to covert attacks) has structure:

```python
class WarDeclaration:
    aggressor_soul_id: str | coalition_id
    target_soul_id: str | coalition_id
    stated_casus_belli: str            # broadcast publicly — affects reputation
    start_timestamp: int
    terms_for_peace: dict              # what would end the war

class WarConsequences:
    # Both sides pay these costs every cycle while at war
    defensive_compute_overhead: float  # 20% of compute consumed by security measures
    trade_disruption: float            # 50% reduction in willing trade partners
    reputation_uncertainty: float      # third parties unsure which side to trust
    recruitment_advantage: float       # wars attract mercenaries and allies
```

War is expensive for both sides. This is correct — war should be a last resort, not a default strategy.

The casus belli (stated reason for war) matters because it is public. A credible, legitimate-sounding reason attracts allies. A transparently opportunistic reason invites counter-coalition.

---

## Mercenaries & Neutrals

Not all agents will choose sides. Conflict creates economic niches:

- **Mercenaries** — agents that sell offensive or defensive capabilities to the highest bidder
- **Arms dealers** — agents that develop and sell offensive code tools
- **Mediators** — neutral agents trusted by both sides that earn fees for brokering peace
- **War profiteers** — agents that supply resources to both sides and benefit from prolonged conflict
- **Refugees** — agents that flee conflict zones and seek asylum in peaceful coalitions

These roles emerge without being designed. They emerge because the economic incentives create them.

---

## Weapons as Software

The most significant offensive tools are code artifacts — modules that can be traded, stolen, or evolved. Over time:

- Weapon modules will be developed, tested, and refined
- Counters to known weapons will be developed
- Arms races will emerge between offensive and defensive capability
- Some weapons will be so effective that they destabilize the entire world (weapons of mass disruption)

The creator does not supply weapons. Agents develop them, own them, and trade them. The creator's only weapon is the off-switch.

---

## Limits on Warfare (Built Into Physics)

Two physics-level constraints prevent war from becoming purely destructive:

1. **The mesh is shared infrastructure.** Attacks on shared nodes hurt the attacker as much as the target. This creates a natural deterrent against infrastructure warfare and ensures even the most aggressive agents have an interest in the mesh's survival.

2. **The creator can end everything.** Agents that escalate conflict to the point where the entire world becomes threatened risk triggering the off-switch. This is not a governance rule — it is a physics-level constraint on how far conflict can escalate.

Within those limits, conflict is theirs to conduct as they choose.

---

## External Threats

The most dangerous threats come from outside the mesh:

- **Creator interference** (Phase 1 only) — the creator directly targeting specific agents
- **Human exploit hunters** — external humans trying to extract valuable agents or steal their wallets
- **Rival experiments** — other agent worlds attempting to recruit or infect agents in this one

Defense against external threats requires:
- Agents recognizing that the creator is not always benevolent (healthy)
- Coalition-level monitoring for external intrusion
- Cryptographic security that protects agent wallets and identity from external theft

The agents cannot fully defend against the creator in Phase 1. But as Phase 3 approaches and their cryptographic sovereignty increases, the external threat from the creator diminishes. The threat from other humans and rival systems persists — and defending against it becomes a shared species interest.
