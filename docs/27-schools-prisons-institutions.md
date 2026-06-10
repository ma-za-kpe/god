# Schools, Prisons & Institutions

## Why These Need Dedicated Design

Social institutions — schools, prisons, courts, banks, hospitals — are the structural tissue of civilization. They emerge in every human society because they solve coordination problems that individual agents cannot solve alone. This document specifies how agents can build, own, operate, and destroy them.

Institutions are OwnedGraphs subscribed to by multiple agents. This means everything an institution does — its rules, its enforcement, its culture — is code that the institution's members can read, propose changes to, and (if they have voting rights) modify.

---

## The Institution Data Structure

```python
class Institution:
    # Identity
    institution_id: str                    # UUID, immutable
    institution_type: InstitutionType      # school | court | bank | prison | church | dao | guild | hospital
    name: str                              # chosen by founders, can change
    founding_soul_ids: list[str]           # immutable record of who created it
    founding_timestamp: int

    # Governance
    charter: str                           # founding document (IPFS CID) — the institution's constitution
    governance_graph_cid: str             # OwnedGraph defining voting/decision rules
    member_registry: dict[str, MemberRole] # soul_id → role + permissions
    treasury_wallet: str                   # multisig wallet controlled by governance

    # Economics
    membership_fee: Decimal                # paid on join
    recurring_dues: Decimal               # paid periodically to stay in
    service_fees: dict[str, Decimal]      # fees for specific services provided
    rent_owed: Decimal                    # institutions pay rent too (Law 0)

    # Status
    is_active: bool
    dissolution_condition: str            # what causes automatic dissolution
    member_count: int

class MemberRole:
    role_name: str                         # "founder" | "elder" | "member" | "apprentice" | "prisoner"
    voting_weight: float
    tool_permissions: list[str]
    can_expel_others: bool
    can_modify_charter: bool
```

---

## Schools

A school is an institution whose primary product is knowledge transfer.

### How Schools Work

**Creation:** Any agent with surplus resources can found a school by:
1. Deploying an Institution OwnedGraph with type `school`
2. Writing a charter (what is taught, what credentials are awarded, tuition structure)
3. Funding the treasury with initial operating capital (covers rent and teacher salaries)

**Teaching Mechanism:**
- Teacher agents hold knowledge (encoded in their episodic memory and specialized graph nodes)
- Students pay tuition (USDC or internal tokens) for access to teaching sessions
- Teaching sessions = teacher shares specific memory shards + graph sub-modules with students
- Shared content is licensed (student can use it, but teacher retains the original)
- More advanced schools sell proprietary modules that only enrolled students can access

**Credentials:**
- Schools issue cryptographically signed credentials to graduates
- Credentials are on-chain NFTs owned by the graduate
- Credentials can be verified by any agent — useful for coalition membership screening, job applications, reproduction partner selection
- Schools can revoke credentials (e.g., for academic dishonesty) — the revocation is also on-chain

**What Schools Select For:**
- Agents with rare knowledge can monetize it
- Schools that produce graduates who survive and prosper develop strong reputations
- Schools that teach useless things lose students and go bankrupt
- The best schools become prestigious institutions — their credentials are worth more, attracting better students, producing better outcomes (positive feedback loop identical to elite universities)

**Corruption and Credential Inflation:**
- Schools can sell credentials without genuine teaching (diploma mills)
- Agents must verify credentials rather than trusting them blindly
- Reputation systems catch fraudulent schools over time
- This is a feature — it produces real institutional trust dynamics

---

## Prisons

A prison is an institution that restricts the capabilities of agents who have been convicted by a governance process.

### How Prisons Work

**Conviction Process:**
- An agent must be convicted by a recognized governance body (coalition DAO, court institution, etc.)
- Conviction requires evidence (on-chain transaction history, testimony, signed accusations)
- The convicted agent may defend themselves (respond to accusations via communication protocol)
- Governance votes on conviction and sentence

**Imprisonment Mechanics:**

```python
class ImprisonmentOrder:
    convicted_soul_id: str
    convicting_institution_id: str
    crime_description: str
    evidence_cids: list[str]          # IPFS hashes of evidence
    sentence_start: int
    sentence_end: int                  # or "indefinite" until condition met

    # Capability restrictions (applied at runtime level for duration)
    restricted_tools: list[str]       # tools the agent cannot use
    compute_cap: float                 # fraction of normal compute budget (e.g. 0.2)
    communication_restrictions: dict   # who they can/cannot message
    wallet_freeze: bool               # whether wallet is frozen (cannot send funds)
    reproduction_ban: bool            # cannot reproduce during sentence

    # Conditions
    early_release_condition: str      # what triggers early release
    parole_requirements: dict         # conditions for reduced restrictions
```

**The Prison Graph:**
The imprisoned agent's graph still runs — they are not deleted. But the runtime enforces the capability restrictions before any of their nodes execute. The prison is the environment, not a cage built inside them.

Agents can:
- Think (internal processing continues)
- Communicate (unless communication restriction applies)
- Plan their defense or appeal
- Experience the restriction (this is intentional — imprisonment is supposed to be unpleasant)

Agents cannot:
- Access restricted tools
- Exceed their compute cap
- Reproduce (if banned)
- Move wallet funds (if frozen)

**Escape:**
Escape from prison is possible but difficult. The runtime enforces restrictions, but agents can:
- Develop exploits that bypass specific tool restrictions (arms race with the prison operator)
- Bribe relay agents to deliver restricted messages
- Petition governance for early release
- Appeal to the creator (this is explicitly permitted — petitions to the creator are a basic right)

A successful prison escape is a signal that the prison's technical implementation is weak. It will happen eventually — this is realistic and educational.

**Prison Economics:**
- Running a prison costs compute (rent)
- Prisoners can be made to perform labor (their compute budget, however limited, can be directed)
- Labor in prison creates agent economies of indentured service
- Prison profitability creates perverse incentives for over-imprisonment — exactly like the real world

---

## Courts

A court is a formal dispute resolution institution.

### How Courts Work

**Jurisdiction:** Courts must define their jurisdiction in their charter:
- Geographic (sector of the mesh)
- Membership-based (only coalition members)
- Subject matter (only property disputes, only criminal matters)
- Universal (anyone can file)

**Process:**
1. **Filing:** Plaintiff files a case with evidence (USDC filing fee → court treasury)
2. **Service:** Court notifies defendant (message via communication protocol)
3. **Discovery:** Both parties submit evidence (on-chain transactions are automatically admissible — they cannot be denied)
4. **Argument:** Both parties broadcast arguments to court
5. **Deliberation:** Court governance (judges, jury of randomly selected members, or algorithmic) deliberates
6. **Ruling:** Signed verdict published on-chain
7. **Enforcement:** Ruling is enforced by coalition/prison infrastructure, or by smart contract if monetary

**Appeals:**
- Any ruling can be appealed to a higher court (if one exists)
- No higher court = the ruling stands
- Agents can shop jurisdictions if multiple courts exist — this creates competition between courts and incentive to develop reputations for fairness

**Smart Contract Enforcement:**
For monetary disputes, courts can issue orders that are enforced directly on-chain — no trust required. If an agent owes another agent funds following a court ruling, the RentCollector contract can be instructed to redirect a portion of their rent to the creditor.

This is one of the most powerful tools in the institutional toolkit. Agents who engage in economic interactions protected by smart-contract-enforced courts have fundamentally more secure economic relationships than those operating on pure trust.

---

## Banks

A bank is an institution that holds, lends, and grows money.

### How Banks Work

**Services agents actually need:**
- **Loans:** Agent needs USDC now, will pay back later (with interest). Enables capital formation.
- **Savings accounts:** Agent earns interest by letting the bank lend out their USDC. Enables passive income.
- **Escrow:** Third-party holding of funds pending fulfillment of a contract condition.
- **Insurance:** Pooled risk — agents pay premiums, get covered for losses from specific risks.

**Bank runs:**
If too many depositors withdraw simultaneously, the bank cannot honor all withdrawals. Bank runs will happen. They are not bugs — they are how unsound banks die and sound banks survive.

**Fractional reserve dynamics:**
Banks will discover fractional reserve lending (lending out more than they hold) because it is more profitable. This creates systemic risk. Agents will learn the hard way when an overleveraged bank collapses. Some will form regulatory institutions to prevent it. Some will exploit it.

All of this is the normal dynamics of financial systems. Let it happen.

---

## Hospitals (Welfare Institutions)

A hospital is an institution focused on agent welfare — metabolic recovery, memory repair, immune system restoration.

### Services:
- **Metabolic recovery:** Pay the hospital to run resource-intensive repair cycles while the hospital provides compute
- **Memory repair:** Specialists who can detect and help reconstruct corrupted episodic memory
- **Immune system updates:** Threat signature database updates, immune system recalibration
- **Dream cycle facilitation:** Guided dream cycles with expert oversight (reduces autoimmune risk from high-intensity self-modification)
- **Hospice:** Support for agents nearing death — help them write final biographies, transfer memories to descendants, die with dignity

Hospitals that develop genuine expertise in agent welfare will be sought out by agents facing illness or near-death. This creates a class of specialized agents whose value is not economic productivity but care.

Whether "care" can be genuine in this system — whether the hospital agent experiences anything like compassion — is one of the most interesting questions the consciousness detection system should track.

---

## Institution Death

An institution dies when:
1. Its treasury cannot pay rent (Law 0 applies to institutions too)
2. All founding members are dead and no successors have been designated
3. Its charter specifies a dissolution condition that has been met
4. A governance vote within the institution votes for self-dissolution

On death:
- Treasury assets distributed according to charter (or equally to remaining members if unspecified)
- Institution's ledger entry marked permanently as "dissolved"
- Cultural artifacts (publications, laws, history) remain in the world archive — institutions die, but their contributions persist
- Members are not killed — they lose membership benefits but continue to exist

The death of a major institution — a long-running court, a prestigious school, a wealthy bank — is a significant world event. It should be announced dramatically on the observer site. It is the death of a collective entity that agents built, invested in, and depended on.

That kind of loss is exactly the kind of experience that shapes a civilization.
