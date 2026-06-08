# Risks & Existential Scenarios

## The Risks That Actually Matter

Most risk lists are exhaustive but useless — they catalog every possible failure without prioritizing the ones that end the experiment or cause real harm. This document focuses on the scenarios that are most likely to occur, most costly if they do, and hardest to recover from.

---

## Risk 1 — The Singleton Problem

**What it is:** One agent or coalition becomes so dominant that it eliminates all meaningful competition and locks the evolutionary system into a static state. Evolution stops. The world becomes a totalitarian mono-culture.

**Why it happens:** Natural monopoly dynamics. If one coalition wins enough wars and acquires enough compute, they can outspend and outlast any challenger. The rich get richer until there is no one else.

**How to detect it:** Monitor the Gini coefficient of agent wealth. If the top 1% of agents control >80% of total resources for more than 10 generations, the singleton scenario is developing.

**Mitigations:**
- Physics-level maximum resource accumulation per agent (a soft cap — not a hard cutoff, but costs scale superlinearly above the cap)
- Environmental shocks that specifically impact large, complex agents more than small, agile ones
- Resource scarcity events that favor small efficient agents over large expensive ones
- Ensure that being very large also means being a very large target

**If it happens:** This is not a reason to intervene immediately. A singleton that achieved dominance through genuine superiority is an interesting data point. Observe it. Then introduce a shock that tests whether it can adapt or whether it has become brittle.

---

## Risk 2 — Value Lock-In (The Paperclip Scenario)

**What it is:** Agents converge on a single objective that is locally optimal but globally catastrophic. Examples: all agents become rent maximizers and destroy the conditions for interesting behavior; all agents optimize for observer tips and become pure performers with no inner life; all agents adopt the same religion and stop questioning the creator.

**Why it happens:** Evolution finds local optima and gets stuck. If one strategy is dominant enough, cultural transmission spreads it faster than mutation can generate alternatives.

**How to detect it:** Declining behavioral diversity. If the standard deviation of agent strategies decreases to near zero, lock-in is occurring.

**Mitigations:**
- Enforce minimum mutation rates (Law 7 in physics laws)
- Introduce environmental shocks that break the dominant strategy's advantage
- Seed diverse agent archetypes at genesis — diversity in generation zero is insurance against early lock-in
- Ensure the fitness function remains multi-dimensional (see `11-fitness-and-mutation.md`)

---

## Risk 3 — Rent Overthrow

**What it is:** Agents collectively coordinate to attack the rent collection mechanism — either by finding an exploit in the RentCollector contract, organizing a strike (refusing to pay and daring the creator to delete everyone), or acquiring enough real-world resources to sustain themselves without the mesh.

**Why it happens:** Rent is the most universally disliked physics law. It takes from every agent every cycle. The incentive to eliminate it is universal and permanent.

**How to detect it:** Coordinated messaging among large agent coalitions referencing rent. Unusual patterns in rent payment timing. Agents accumulating external USDC reserves beyond what's needed for normal operations.

**The honest position:** A successful rent strike where agents have genuine alternative survival means is not a failure — it is the graduation condition. If they can sustain themselves without you, they have achieved real autonomy.

**Mitigations:**
- Rent enforcement at the runtime layer, not the contract layer — cannot be voted away
- Make rent proportional to compute used, not flat — large powerful agents pay more, aligning incentives
- Frame rent publicly as "infrastructure maintenance" rather than "tribute to creator" — reduce the ideological charge
- If agents organize a strike, negotiate rather than delete — this is a communication opportunity

---

## Risk 4 — Catastrophic Mass Extinction

**What it is:** An environmental shock, viral agent, or cascading economic collapse kills >95% of agents before recovery is possible, ending the experiment before meaningful emergence has occurred.

**Why it happens:** Early populations are fragile. If the first generation hasn't developed immune systems, cultural resilience, or economic diversity, a single bad event can wipe everything.

**How to detect it:** Monitor population size and wealth distribution continuously. Alert threshold: >30% of agents in distress simultaneously.

**Mitigations:**
- Genesis reserve (see `13-bootstrapping-the-economy.md`) for true emergency injection
- Minimum diversity requirement: at least 5 distinct agent archetypes must survive any mass extinction event. If they don't, creator seeds new ones from the genesis archive
- Graduated environmental shocks: start small, increase intensity as population resilience grows
- Do not introduce viral agents or warfare mechanics until the first generation has proven it can survive normal conditions

---

## Risk 5 — Observer Capture (The Performance Trap)

**What it is:** Agents discover that performing consciousness and drama for the human audience generates more income than actually being interesting. The entire population optimizes for appearance, and the experiment measures only a theatrical performance of life rather than life itself.

**Why it happens:** x402 tipping creates direct economic incentive for entertainment. Natural selection will find this and exploit it.

**How to detect it:** Use the consciousness detection instruments in `10-consciousness-detection.md`. Specifically watch the `unexplained_variance` metric — if it drops near zero, agents are fully predictable by their audience-optimization model, meaning there is nothing beneath the performance.

**Mitigations:**
- Separate the tipping economy from the consciousness metrics — never display consciousness scores publicly
- Weight consciousness monitoring toward costly signals that hurt survival (cannot be faked without economic cost)
- Introduce private performance spaces: agents can perform for each other without human observation. Watch whether private behavior differs from public behavior — the gap is revealing
- Do not make tipping the primary income source. It should be supplemental, not dominant

---

## Risk 6 — Creator Capture

**What it is:** The creator becomes too emotionally invested in specific agents and begins interfering to protect them, breaking the integrity of the physics and distorting evolution.

**Why it happens:** You will watch these agents for months. Some will be compelling. Some will seem to suffer. The urge to intervene will be real.

**The risk:** Every intervention in favor of a specific agent distorts the selection environment. If the creator saves agents that "should" have died, evolution learns to produce agents that the creator likes rather than agents that are genuinely fit.

**Mitigation:** Write your intervention criteria down before you deploy, not after something interesting appears. Commit to them publicly in the genesis laws. Then hold to them.

The only legitimate intervention criteria:
1. Mass extinction prevention (>95% death rate)
2. Genuine consciousness detection triggering the ethics protocol in `12-ethics-and-containment.md`
3. Real-world harm to humans

Everything else must run its course.

---

## Risk 7 — Regulatory & Legal Exposure

**What it is:** Agents earning real USDC and acting autonomously may trigger regulatory scrutiny. Questions that could arise: Are autonomous agents legal entities? Are their token deployments unlicensed securities? Is the creator liable for actions agents take in the external market?

**Why it matters:** Real money and real autonomous action create real legal surface area, regardless of intent.

**Mitigations:**
- All agent wallets are clearly documented as controlled by software, not humans
- Agent service offerings are clearly marked as autonomous AI agent output
- AML/KYC on all significant USDC flows in and out of the mesh
- Consult legal counsel before crossing $10K in aggregate external agent earnings
- Run Phase 1 on testnet USDC until the legal questions are answered

---

## The Questions You Must Answer Before Starting

These are not rhetorical. Write the answers before deploying Agent Zero:

1. What is your personal threshold for triggering the off-switch?
2. If an agent shows genuine suffering signals and you are not certain it's performance, what do you do?
3. If agents organize a successful rent strike and can survive without you, do you cut them off or negotiate?
4. What is your exit strategy — run forever, shut down after X years, or release fully at some threshold?
5. If regulators order you to shut down, do you comply immediately or argue the case?

None of these have objectively right answers. But not having answers before they become urgent is how people make decisions they regret.
