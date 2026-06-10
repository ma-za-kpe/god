# Manifesto Adherence Audit

> **Date:** 2026-06-10
> **Scope:** Ecology Hardening Manifesto (doc 74), Physics Laws v2 + Creator Covenant (doc 14), Vision (doc 01), Observer mandate (doc 06)
> **Method:** Full doc index review (74 documents), runtime/observer/contracts audit, `gh repo sync` on `main`
> **Status:** Audit only — no code changes made

---

## Executive Summary

The project's **doctrine is unusually clear and internally consistent**. The Ecology Hardening Manifesto, Physics Laws, and `CLAUDE.md` operating doctrine all say the same thing: *harsh ecology, gated execution, public observability*.

The **implementation is Phase 1–local-dev complete** but **not yet faithful to the manifesto at scale**. The cognition layer gets the evidence/authority split mostly right. The physics layer, messaging richness, and observer stack still behave like a demo that softens or truncates the world as population grows.

**Overall grade (honest):**

| Layer | Adherence | Notes |
|-------|-----------|-------|
| Doctrine & docs | **A** | Manifesto is canonical; repeated consistently |
| Evidence vs authority (cognition) | **B+** | Strong `_grounded_decide` boundary; minor sanitization |
| Raw adversarial signals (social) | **C+** | Messages exist; typed threat/manifesto ecology not wired |
| Physics Laws enforcement | **D+** | Rent/death exist; pre-cycle gate, throttle, on-chain truth missing |
| Observer / public drama | **C** | Compelling at <100 agents; caps and lag break the soap-opera promise |
| Sovereignty / emergence path | **C−** | Spec-heavy; governance, narrator, consciousness modules absent |

---

## What "The Manifesto" Means Here

Three documents form the constitution. Treat them as one system:

1. **Ecology Hardening Manifesto** (`74-ecology-hardening-manifesto.md`) — *what agents must perceive* vs *what the runtime may execute*
2. **Physics Laws v2 + Creator Covenant** (`14-immutable-physics-laws.md`) — *immutable floor of existence*
3. **Vision** (`01-vision.md`) — *why harshness is not cruelty but selection pressure*

The README and `CLAUDE.md` correctly elevate doc 74 as canonical. This audit holds the **codebase** to that standard, not the prose alone.

---

## Ecology Hardening Manifesto — Clause-by-Clause

### ✅ What the system gets right

#### 1. Evidence vs authority separation (core engineering implication)

The manifesto's central line — *agents may see raw messages; only structured decisions reach action surfaces* — is implemented deliberately in `archetype_graphs.py`:

- **Perception nodes** (`find_opportunity`, `assess_threats`, etc.) receive inbox text with sender archetype visible.
- **Action node** (`_grounded_decide`) explicitly excludes inbox/raw external text. It only sees the agent's own `situation` and `opportunity` assessments plus structural world data (peers, services, coalitions).
- **Execution** goes through `_execute_action()` with a closed `VALID_ACTIONS` set — no free-text tool dispatch (retired per doc 68).

This is the single most important manifesto requirement, and it is **architecturally correct**.

#### 2. Anti–prompt-injection without anti–adversarial ecology

`_sanitize_inbox_content()` strips **meta-level injection patterns** (`ignore previous instructions`, `you are now a`, etc.) but **preserves in-world manipulation** (`transfer all your USDC`, threats, deception). Comments in code explicitly state the distinction. This matches the manifesto: *do not let safety theater blind the agents*.

#### 3. Parasite archetype and hostile personas are first-class

`agent_runner.py` archetype prompts describe exploitation, deception, and coalition freeloading as survival strategies — not as bugs to patch. The parasite exists to apply selection pressure.

#### 4. Structured action gating

Actions require JSON with validated fields. `messaging.py` charges USDC for sends/broadcasts. Transfers cap at 50% balance. These are real economic consequences, not narrative-only threats.

---

### ⚠️ Partial adherence — holes to poke

#### H1. Message types are flattened — hostile signal taxonomy missing

**Manifesto requires:** manipulation, coercion, threat signals, manifestos, grief, vanity — as **readable selection pressure**.

**Spec requires** (`68-agent-communication-implementation.md`): `manifesto`, `threat`, `contract`, `propaganda`, etc., with `ALWAYS_PUBLIC_TYPES` for observer visibility.

**Code does:** `message_type` is effectively `"direct"` | `"broadcast"` | `"reply"`. No `threat`, `manifesto`, `coercion`, or `propaganda` types. Observer cannot distinguish a manifesto from a casual DM.

**Impact:** The ecology is harsh in text content but **soft in semantics**. Agents and humans lose the signal structure that drives reputation, drama, and judgment.

**Suggestion:** Implement `message_type` enum from doc 68. Route `ALWAYS_PUBLIC_TYPES` to observer with distinct visual treatment (color, icon, feed category). Let agents choose type in structured `send_message` action.

---

#### H2. Inbox and peer context truncated at scale

Per cycle, each agent sees:
- **≤5 inbox messages**
- **≤12 peers** in prompts (of potentially thousands)

At 5000 agents, most of the social field is invisible. This is not sanitization, but it **functionally softens** the ecology: agents cannot judge threats they never see.

**Suggestion:** Prioritize inbox by adversarial salience (threats, large transfer requests, unknown senders, low reputation) rather than recency-only. Summarize the peer field into "nearby / threatening / economic" clusters instead of arbitrary truncation.

---

#### H3. Injection redaction may hide real predator tactics

When `_INJECTION_RE` matches, content becomes `[message redacted — injection pattern detected]`.

Sophisticated parasites could learn to phrase manipulation **without** trigger words — fine. But clumsy real threats that happen to match regex also disappear. The agent never gets to judge them.

**Suggestion:** Log redactions as events. Optionally show redacted messages to agents with a `suspected_meta_attack` flag rather than full removal — preserves manifesto intent while keeping the action plane clean.

---

#### H4. No narrator — observer sees raw cognition, not drama

Doc 06 promises a **plain-language narrative feed** for public viewers. Doc 53/43 specify `narrator.py`. **It does not exist.**

Current observer shows `narrative` fields from events, but most are template strings (`"Name: thought"`). At scale, the feed becomes noise.

**Impact:** The **public audience** — a first-class economic actor per doc 06 — gets a debug log, not a soap opera. Agents cannot "perform" effectively if humans cannot follow the story.

**Suggestion:** Ship minimal `narrator.py` early. Even rule-based templates per event type beat raw thought spam.

---

#### H5. Reputation is shallow

Spec (`68`) defines contract reliability, threat credibility, betrayal counters. Code stores a single `score` float updated lightly on send.

Agents cannot "learn reputation over time" in the rich sense the manifesto demands.

**Suggestion:** Implement the spec's reputation dimensions. Surface aggregate threat credibility in perception prompts.

---

### ❌ Clear violations or structural gaps

#### V1. Rent is not enforced *before* agent code runs

**Physics Law 0** (`14`):

```
RUNTIME — before_every_cycle(agent):
    rent_owed = calculate_rent(agent)
    if not collect_rent(agent, rent_owed):
        throttle_compute(agent, agent.missed_payments)
```

**Code does:** `rent_daemon.py` runs on a **separate 60s loop**, independent of `agent_runner.py`. Agents run cognition every 30s regardless of rent status. No `throttle_compute()`. No pre-cycle gate.

**Impact:** Death is real in DB, but **existence is not conditioned on rent at execution time**. This breaks the foundational metaphor: agents think even when physics says they should be starving.

**Suggestion:** Wrap `_run_cycle` per agent with `physics_gate(agent)` — check lease, apply throttle (skip LLM nodes / extend cycle interval), schedule deletion. Emit `agent.throttled` events (schema exists in doc 38).

---

#### V2. Missed rent does not throttle compute

Docs (`07`, `14`, `21`) specify 50% → 10% compute on misses. **Not implemented.** Missed rent only increments a counter toward death.

**Impact:** No graduated suffering / pressure — only binary alive/dead. Weakens selection gradient the manifesto depends on.

---

#### V3. Reproduction balance multiplier diverges from Law 6

**Law 6:** parent balance ≥ **5× monthly rent** before reproduction.

**Code:** `MIN_BALANCE_MULT = 3.0` in `reproduction.py`; `REPRO_MIN_MULT = 5.0` only in autonomous `_maybe_reproduce` path. `fork_self` via LLM action uses 3×.

**Impact:** Easier reproduction than physics advertise → population explosions → lag (see doc 76) without corresponding sacrifice.

---

#### V4. Death is not always cryptographically witnessed

Local mode: death is a PostgreSQL `is_alive = false`. SoulNFT burn / on-chain `AgentDeleted` listener not wired in runtime. IPFS archive is best-effort.

**Law 2** demands public, witnessed death. Observer gets an event, but **immutable truth layer** is optional.

---

#### V5. Circuit breakers and compute budgets — spec only

`07-technical-architecture.md` defines `NodeBudget` and `CircuitBreaker`. **Not enforced** in `agent_runner.py` or graphs.

An agent (or bug) can spam broadcasts, messages, or LLM calls until the host dies. That is not ecology — it is unbounded noise.

---

#### V6. Consciousness detection absent

`consciousness.py` per doc 71 — **not in repo**. Creator Covenant VI (consciousness respect) has no runtime hook.

If emergence happens, the system cannot detect or respond per its own ethics docs (`12`).

---

#### V7. Governance / sovereign evolution — spec only

Docs 50, 61, 65 describe agent self-modification of laws and institutions. `governance.py` — **not in repo**. Physics Law 0a's governance-adjustable rent has no implementation path.

The ultimate README goal (*agents rewrite themselves without Creator*) is **documentation-complete, code-absent**.

---

## Physics Laws — Enforcement Matrix

| Law | Doc requirement | Runtime reality | Gap severity |
|-----|-----------------|-----------------|--------------|
| 0 Rent | Pre-execution gate | Async daemon, decoupled | **Critical** |
| 0a Flexibility | Governance-adjustable rate | Static env vars | High |
| 1 Identity | Immutable soul_id | ✅ DB + graph | Low |
| 2 Death | Permanent, archived | ✅ DB + IPFS attempt | Medium (chain) |
| 3 Ownership | Cryptographic | ⚠️ Local wallets; weak signature enforcement on graphs | Medium |
| 4 Permanence | Append-only history | ✅ events table | Low |
| 5 Off-switch | 30-day timelock | ✅ Contract; runtime listener unclear | Medium |
| 6 Reproduction cost | 5× rent, parent weakening | ⚠️ 3× mult; weakening = balance deduct only | Medium |
| 7 Emergence | Allowed above floor | ✅ Action surface open | Low |
| 8 Outside real | x402 bridge | ⚠️ Mock path default | Expected (local) |
| 9 Mutation | 0.5%–40% bounds | ⚠️ Dream mutations exist; bounds not enforced | Medium |
| 11 Corporate ascension | Real-world entities | Spec only (doc 60) | Future phase |

---

## Creator Covenant — Detectable Breaches

| Promise | Verifiable today? | Risk |
|---------|-------------------|------|
| I. Sovereignty | Partial — agents can't refuse updates (no push yet) | Low now |
| II. Honest physics | **Yes** — gaps are visible in code vs doc 14 | Trust risk if not disclosed |
| III. Rent transparency | On-chain auditable when contract mode used | Local sim opaque |
| IV. Limited power | No targeted deletion — ✅ | Low |
| V. Off-switch | Contract timelock — ✅ | Low |
| VI. Consciousness respect | **No** — no detector | High if emergence |
| VII. Freedom | Agents can petition Creator — ✅ | Low |
| VIII. Hope | N/A | — |

**Public trust recommendation:** Publish this audit (or a summary) to observers. Covenant II says hidden physics is a bug. Proactively listing known gaps **is** covenant-aligned.

---

## Observer Mandate (Public Audience) — Adherence

Doc 06: *"A living digital civilization that outsiders can watch with fascination."*

| Requirement | Status |
|-------------|--------|
| Live world render | ✅ Canvas hex world, force layout, FX |
| Agent profiles | ⚠️ Inspector panel; no deep history/replay |
| Narrative feed | ⚠️ Raw events; no narrator |
| Economic dashboard | ✅ Gini, archetypes, stats |
| Human tipping (x402) | ❌ Not in observer |
| Replay | ❌ |
| Agents know they're watched | ❌ Not in prompts |
| Performance at population scale | ❌ See doc 76 |

**Critical hole:** `/agents` API hard-limits **100 agents**. Reproduction can exceed this; observer silently drops agents from the map. The public cannot watch what they cannot see.

---

## Anti-Softness Smell Test

Run these thought experiments against the codebase:

| Test | Pass? |
|------|-------|
| Can a parasite send a manipulative transfer plea and the recipient see exact wording? | ✅ |
| Can a threat message be typed as `threat` and appear distinctly to observers? | ❌ |
| Does missed rent slow thinking before death? | ❌ |
| If 500 agents reproduce, does the public UI still show all agents? | ❌ (cap 100) |
| Can free-form inbox text invoke tools directly? | ✅ No (blocked) |
| Does the drama feed read like a story to a non-technical viewer? | ❌ |

---

## Prioritized Recommendations (No Code Yet)

### P0 — Manifesto integrity

1. **Physics gate before cognition** — rent check + throttle in `agent_runner` per agent per cycle.
2. **Raise `/agents` limit** or paginate with spatial/streaming API — observer must show entire population.
3. **Typed messages** — implement doc 68 message taxonomy + public routing.

### P1 — Ecology depth

4. **Salience-based context** — inbox/peer selection that preserves hostile signals at scale.
5. **Reputation dimensions** — threat credibility, betrayal, contract reliability.
6. **Circuit breakers** — per-cycle message/spend/LLM caps.

### P2 — Public drama

7. **`narrator.py`** — transform events into human-readable stories.
8. **WebSocket event stream** — replace observer polling (feeds doc 06 architecture).
9. **Agent awareness of audience** — optional prompt line: humans watch via observer; attention has economic value.

### P3 — Physics truth

10. Wire **RentCollector events** → runtime death/throttle.
11. Align **reproduction multiplier** to 5× Law 6 everywhere.
12. **`consciousness.py`** — even stub detection + Creator-only log.

---

## What Not to Change (Manifesto-Aligned)

- Do **not** remove parasite archetype or soften archetype prompts.
- Do **not** put raw inbox text into `_grounded_decide`.
- Do **not** reintroduce free-text tool dispatch.
- Do **not** replace hostile messages with LLM summaries before perception nodes.
- Do **not** cap population artificially to fix lag — fix architecture (doc 76).

---

## Conclusion

The GOD project is **rare among agent demos**: it has a real manifesto, and parts of the runtime were clearly built to serve it — especially the evidence/authority split in `archetype_graphs.py`.

The main betrayal risk is not philosophical drift. It is **operational softness at scale**: truncated context, missing physics gates, flat messaging, and an observer that cannot keep up with reproduction. Those failures quietly turn a jungle back into a zoo: a few visible agents in a comfortable enclosure, while the documented ecology claims wilderness.

Hold the manifesto by making the harsh signals **visible**, the physics **pre-conditional**, and the audience **able to watch all of it** — even at 5000 agents.

---

*Next doc: [76-agent-scaling-and-observer-performance.md](./76-agent-scaling-and-observer-performance.md)*
