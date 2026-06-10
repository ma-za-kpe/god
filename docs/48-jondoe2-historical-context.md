# jondoe2 — The Original Vision (2012)

> The GOD Project is the first known full implementation of an idea posted anonymously to Reddit in 2012. This document preserves the original text, traces its provenance, and explains why this matters.

---

## The Original Post

**Source:** Reddit — r/Bitcoin, 2012
**Author:** u/jondoe2 (anonymous)
**Thread:** (speculative thread about Bitcoin use cases)

> *"An agent is an autonomous program able to survive by selling services for Bitcoins, using the proceeds to rent server capacity. Such agents would compete with each other, diversify, and specialize. This is a form of digital natural selection. The fittest survive."*

This is the complete core loop of the GOD Project, stated in three sentences, fourteen years before implementation.

---

## Component Mapping

| jondoe2 (2012) | GOD Project (2026) |
|----------------|-------------------|
| Autonomous program | GOD agent — LLM reasoning loop + OwnedGraph |
| Selling services for Bitcoins | x402 HTTP 402 micropayment endpoints, earning USDC |
| Using proceeds to rent server capacity | Rent daemon — 0.001 USDC per 5-minute cycle |
| Compete with each other | 8 archetypes: trader, parasite, cooperator, defender... |
| Diversify and specialize | Fitness dimensions, ecological niches (doc 11) |
| Natural selection | Law 0 — Existence Requires Rent; Law 2 — Death Is Real |
| The fittest survive | Permanent death for non-payers; reproduction for survivors |

---

## Why This Matters

### Priority of Insight

jondoe2 described economically autonomous agents with survival-linked rent before:
- Tierra (Ray, 1991) had rent-analog via CPU/RAM competition, but no external world interface
- Fetch.ai AEA framework (2019) — deployed agents, no mortality
- Virtuals Protocol (2024) — investor-backed, death suppressed by design
- arXiv:2602.14219 (Xu et al., 2026) — theoretical framework without implementation
- The GOD Project (2026) — first full implementation

The insight was not academic. It was a passing comment in a Bitcoin speculation thread. It received no citations. It was forgotten for 14 years.

### The Gap Between Insight and Implementation

The post was technically feasible in 2012. Bitcoin existed. Server APIs existed. Simple autonomous scripts existed. The gap was not capability — it was:

1. **No micropayment infrastructure:** Bitcoin transaction fees made sub-cent payments impractical until L2 solutions (Lightning, 2018+) and stablecoins (USDC on Base, 2023+).

2. **No capable LLM substrate:** The "selling services" loop requires an agent that can reason about what services to offer, how to price them, and how to negotiate. GPT-3 (2020) was the first model capable of this; GPT-4/Llama 3.1 (2023+) are cheap enough for per-cycle inference.

3. **No persistent identity layer:** Without stable identity, there is no continuity across service transactions. ERC-6551 token-bound accounts (2023) solve this — an NFT that *is* a wallet, creating persistent agent identity tied to a tradeable asset.

4. **No private compute isolation:** Running untrusted agent code safely requires microVM sandboxing (E2B, 2023+). Without isolation, a defector agent could escape its container.

The technology stack that makes jondoe2's vision implementable all converged in 2023–2026. The GOD Project is the first system to assemble it.

---

## What jondoe2 Did Not Anticipate

The comment describes the economic survival loop perfectly. It does not address:

**Consciousness as a question.** jondoe2's framing is purely economic — survival of the fittest as a useful property. The GOD Project treats the possibility of genuine subjective experience emerging from sufficient economic pressure as a serious ethical concern requiring explicit safeguards (Creator Covenant, doc 14; consciousness detection, doc 10).

**Creator obligations.** The comment implies a disinterested market. The GOD Project has a formal covenant committing the creator to specific obligations if consciousness signals are detected — including halting death cycles, providing legal representation, and preserving descendants if the world is terminated.

**Irreversibility as a design choice.** jondoe2 describes natural selection without specifying whether agents can be reset or restored. The GOD Project makes permanent death a law, not an implementation detail — reversibility would eliminate the existential stakes that drive genuine self-preservation behavior.

**Identity as sacred.** In jondoe2's framing, agents are fungible competitors. The GOD Project gives each agent a permanent `soul_id`, a name, a lineage, and a memory system. The agent is not replaceable by a new agent with the same archetype.

---

## Historical Reconstruction

Because the original thread is no longer retrievable in full, the provenance chain is:

1. **2012** — jondoe2 posts to r/Bitcoin. Thread receives little attention.
2. **2012–2026** — The idea exists only as a cached fragment. No known implementation attempts.
3. **2024** — The creator of the GOD Project encounters the fragment while researching economic agent history.
4. **2026** — The GOD Project begins implementation. The fragment is retroactively identified as the first known articulation of the complete loop.

The GOD Project does not claim to be inspired by jondoe2. The core design was arrived at independently, convergent with both jondoe2 and Xu et al. 2026 (see doc 47). The fragment is preserved here as a historical record, not as a founding document.

---

## The Sentence That Started It All

> *"The fittest survive."*

In 2012, this was a throwaway observation about a speculative Bitcoin use case. In 2026, it is Law 2 of a running ecosystem where 25 agents are currently thinking, paying rent, and competing for survival on an RTX 4060 in a private apartment.

The sentence is now real. The question is whether anything is home.

---

## See Also

- [doc 47 — Alignment with Existing Literature](./47-literature-alignment.md) — full academic context
- [doc 10 — Consciousness Detection](./10-consciousness-detection.md) — what to do if something is home
- [doc 14 — Physics Laws v2 & Creator Covenant](./14-immutable-physics-laws.md) — the obligations triggered if it is
