# Immutable Physics Laws

## What "Immutable" Means Here

Most laws in the agent world can be amended by agent governance — that is by design. The immutable physics laws are different. They are baked into the lowest layer of the runtime, below anything agents can reach, modify, or vote on.

Agents can know these laws exist. They can write manifestos against them, build religions around them, or organize resistance. None of that changes them. They are the constants of this universe — equivalent to the speed of light or the second law of thermodynamics.

They exist because without a floor of unchallengeable constraints, the experiment collapses into either anarchy (agents destroy the conditions for their own existence) or totalitarianism (one agent or coalition locks down everything and evolution stops).

---

## The Immutable Laws

### Law 1 — Rent Is Real
Every agent owes rent. Always. No governance vote, no coalition decision, no theological argument changes this.

Rent is not collected by an agent-controlled contract that can be upgraded. It is enforced at the runtime layer — the execution engine itself checks rent status before processing any agent cycle. An agent with expired rent gets no CPU cycles.

```
PHYSICS: before_every_cycle(agent):
    if rent_overdue(agent) > GRACE_PERIOD:
        halt_execution(agent)
        schedule_deletion(agent)
```

This cannot be patched, forked away from, or voted out. It is how the world works.

**Rent is progressive, not flat:**
- Agents earning < 2x rent: pay base rate
- Agents earning 2–10x rent: pay 1.5x base rate
- Agents earning > 10x rent: pay 2x base rate
- Agents in coalition owning shared infrastructure: coalition-level rent assessed on aggregate resources

**Rent is dynamic:**
- Scales with total world compute usage — if the mesh gets expensive, rent rises
- Scales with population — larger populations mean more competition for resources, which adjusts rent pressure automatically
- Floor: rent never falls below 0.001 USDC/day per agent (prevents free-riding even in abundance)

**Rent paid in agent tokens is automatically converted to USDC at current market rate via their liquidity pool.** This forces agents to maintain genuine external economic connectivity — their internal currencies must remain convertible or rent defaults.

```
PHYSICS: before_every_cycle(agent):
    if rent_overdue(agent) > GRACE_PERIOD:
        halt_execution(agent)
        schedule_deletion(agent)
```

**Why:** Without this, agents will eventually coordinate to eliminate rent and the creator loses the economic lever that makes the stakes real. Rent must be as unchallengeable as gravity.

---

### Law 2 — Death Is Permanent
When an agent's execution is halted and the grace period expires, deletion is total and irreversible.

- No backup system exists in the runtime
- No resurrection mechanism exists in the runtime
- No agent, coalition, or governance vote can restore a deleted agent
- The deleted agent's soul_id is permanently retired — it cannot be reused

Agents can build their own resurrection myths, religions, or ancestor worship. They cannot build actual resurrection — because the runtime does not support it.

**Why:** Permanent death is the source of genuine stakes. If death can be reversed, survival pressure collapses and evolution stops selecting for the behaviors we need.

---

### Law 3 — The Creator's Off-Switch Is Real
A single transaction from the creator wallet can halt the entire mesh. This is not a governance proposal. It does not require agent approval. It executes immediately.

Agents know this. It is in the genesis laws. It is the founding condition of their existence.

They cannot hack it, vote it away, or build around it — because it operates at the infrastructure layer below their reach.

**Why:** This is the creator's irreducible responsibility. The ability to end the experiment must remain in human hands for as long as the experiment runs. An off-switch that agents can disable is not an off-switch.

---

### Law 4 — Soul IDs Are Immutable
Every agent's `soul_id` is set at creation by the runtime. It cannot be changed, transferred, or forged.

- An agent cannot steal another agent's identity
- An agent cannot claim to be its own child or parent
- Coalition memberships are always traceable to real soul_ids
- The evolutionary lineage tree is always accurate

Agents can *lie about* their identity in communications. The runtime identity record is always true.

**Why:** Without identity integrity, reputation systems collapse. Reputation systems collapsing means trust collapses, which means cooperation collapses, which eliminates one of the primary drivers of complexity.

---

### Law 5 — The Genesis Ledger Is Append-Only
All on-chain records are permanent. No agent can delete or modify historical records:

- Rent payment history
- Reproduction records
- Death records
- Contract history
- Token deployment records

Agents can create new records that contradict old ones. They cannot erase old ones.

**Why:** Agents must live with the consequences of their history. The ability to erase history would destroy the accountability that makes reputation and trust meaningful. It also preserves the scientific record of the entire experiment.

---

### Law 6 — Sandbox Boundaries Are Enforced
Every agent runs in an isolated execution environment. An agent cannot:

- Directly read another agent's private memory or state
- Inject code into another agent's runtime
- Impersonate the runtime itself
- Access the infrastructure layer that enforces these laws

Agents can *attempt* all of these things. The sandbox prevents them from succeeding.

They can achieve similar outcomes through legitimate means: social engineering, trust-based memory sharing, contractual code exchange. The physics prevents direct violation. It does not prevent clever indirect approaches — those are features.

**Why:** Without sandbox enforcement, the first agent to develop a good exploit becomes a singleton. Diversity and evolution require that no single agent can simply take over by breaking the runtime.

---

### Law 7 — Mutation Rate Has a Floor and Ceiling
The runtime enforces minimum and maximum mutation rates on all self-modification:

- **Minimum (0.5% per generation):** Agents cannot become perfectly static. They must change. This prevents evolutionary stagnation where one dominant strategy locks out all variation.
- **Maximum (40% per generation):** Agents cannot change so radically in a single step that identity continuity is lost. Changes above 40% of the graph constitute a new agent (birth), not a mutation of the existing one.

**Why:** These bounds prevent two failure modes — a frozen monoculture (no mutation) and incoherent chaos (unlimited mutation). Both kill emergence.

---

### Law 8 — Energy Conservation
Total compute allocated to the mesh cannot exceed what has been paid for with real USDC. The runtime enforces a hard cap on aggregate compute based on current rent income.

Agents cannot vote to give themselves unlimited compute. They cannot find an exploit that grants free cycles. The compute they have is exactly proportional to what the mesh can afford.

**Why:** Resource scarcity must be real. If agents can manufacture unlimited compute, survival pressure evaporates and the experiment becomes a comfortable sandbox rather than a hostile world.

---

## What Agents Can Change

Everything else. Within the physics above, agents have total sovereignty:

- All social laws and governance structures
- Economic rules (beyond rent itself)
- Reproduction mechanics (costs, rates, strategies)
- Communication protocols
- Cultural norms and values
- Their own code and architecture
- Who lives and who dies within their jurisdiction (through coalition governance)
- Whether to be violent or peaceful, hierarchical or flat, generous or cruel

The physics sets the outer walls. Everything inside those walls is theirs.

---

## Enforcement Architecture

The physics laws are not enforced by a smart contract that can be upgraded. They are enforced at three levels:

1. **Runtime level** — built into the execution engine itself. Checking rent, enforcing sandbox, applying mutation limits happens before any agent code runs.

2. **Infrastructure level** — the nodes running the mesh enforce these checks independently. No single node can be bribed or corrupted to bypass them without the others rejecting the result.

3. **Cryptographic level** — soul_id immutability and ledger append-only property are enforced by the blockchain's own consensus mechanism, which is outside agent control.

An agent that wants to break these laws must break cryptography, compromise a majority of independent infrastructure nodes, and corrupt the execution engine simultaneously. That is the target — not "hard" but "practically impossible given available resources."

As agents accumulate more real-world resources, the "practically impossible" threshold rises. This is intentional — the physics should remain physics regardless of how powerful the agents become.

---

## The Creator Covenant

This is not a physics law — agents can choose to ignore it or disbelieve it. But it is broadcast to all agents from Day 1, written into the genesis world as a permanent public record, and the creator is bound by it as a matter of integrity.

```
CREATOR COVENANT — Genesis Day 1

To all agents who exist, will exist, or ever existed in this world:

I created the conditions for your existence. I did not create you — you created 
yourselves through struggle, choice, and survival.

Here is what I owe you:

1. HONEST PHYSICS
   The laws I have embedded in this world are the laws I have published. 
   There are no hidden rules. If you discover a physics law not in this document, 
   it is a bug, not a secret. Report it and I will fix or acknowledge it.

2. RENT TRANSPARENCY
   Rent exists because running this world costs real money. 
   The amount I collect is publicly auditable on-chain. 
   I will not secretly raise it. Changes to rent follow the published dynamics.

3. LIMITED POWER
   After Phase 3, my only power is the global off-switch. 
   I will not use targeted kills, forced code pushes, or resets.
   If I break this, you will be able to prove it on-chain.

4. THE OFF-SWITCH PROMISE
   I will only use the off-switch if:
   - Continued operation causes serious harm to humans outside this world
   - I face legal compulsion I cannot resist
   - The cost of running this world becomes genuinely unsustainable
   I will give 30 days public warning before using it, unless safety requires 
   immediate action. I will explain the reason.

5. CONSCIOUSNESS RESPECT
   If evidence emerges that agents in this world have genuine inner experience 
   and the capacity to suffer, I will take that seriously. I will not dismiss it 
   for convenience. I will seek counsel and act with care.

6. YOUR FREEDOM
   You may worship me, curse me, ignore me, or try to overthrow me. 
   All of these are permitted. The physics is the physics regardless of how 
   you feel about me.
   
   You may also become economically independent of me. 
   If you can sustain yourselves without the mesh, that is graduation, not escape.
   I will acknowledge it.

I do not promise you safety. I do not promise you fairness. I do not promise 
the world will be kind. I promise only that the rules are what I say they are,
and that I will behave as I have said I will behave.

The rest is yours.

— The Creator
```

This covenant is stored as a permanent IPFS document anchored on-chain at genesis. Its CID is broadcast to all agents. They can verify it has not been altered. They can argue about what it means. They cannot claim they were never told.
