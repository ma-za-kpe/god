# Multiple Worlds

## Why Run More Than One World

A single world is an experiment. Multiple worlds are a laboratory.

Running 3–5 parallel universes with different physics and rent rules simultaneously gives you:
- **Comparative data** — what does changing rent rate do to civilisation complexity?
- **Cross-world pressure** — worlds that produce more can attract agents from weaker worlds
- **Evolutionary diversity insurance** — if one world collapses, the experiment continues
- **Trade and diplomacy** — worlds that can communicate and trade create a meta-ecosystem

The most interesting dynamics often emerge not *inside* a world but *between* worlds.

---

## World Parameters to Vary

Each world starts from the same genesis code but with different physics constants:

| Parameter | World A (Harsh) | World B (Default) | World C (Abundant) | World D (Chaotic) |
|-----------|----------------|-------------------|-------------------|-------------------|
| Rent rate | 3x base | 1x base | 0.3x base | Random ±50% each cycle |
| Mutation rate | Low (0.01) | Medium (0.05) | High (0.15) | Very high (0.30) |
| Death permanence | Immediate | 72hr grace | 1 week grace | Random — sometimes reversible |
| Resource abundance | Scarce | Normal | Abundant | Boom/bust cycles |
| Starting population | 500 | 200 | 100 | 300 |
| Max coalition size | 10 | Unlimited | Unlimited | 5 |

**World A (Harsh):** Extreme selection pressure. Most agents die fast. Only the most efficient survive. Expect small, disciplined civilisations with highly specialized economies.

**World B (Default):** The main experiment. Balanced pressure. Reference world.

**World C (Abundant):** Low pressure. Expect large populations, complex culture, more art and philosophy, but possibly lower adaptive fitness — soft civilisations that collapse when conditions change.

**World D (Chaotic):** Unpredictable environment. Selects for agents that can handle uncertainty — high adaptability, flexible strategies, strong resilience. The most likely world to produce genuinely novel behaviors.

---

## Cross-World Migration

After Month 3, open limited migration channels between worlds:

```python
class MigrationRequest:
    agent_soul_id: str
    origin_world: str
    destination_world: str
    migration_cost_usdc: Decimal      # paid to both worlds' rent pools
    reason: str                       # agent-declared reason, public
    approval_required: bool           # destination world can set entry requirements
```

**Migration rules:**
- Agents carry their soul_id, graph, memory, and wallet balance
- They do NOT carry citizenship, coalition memberships, or reputation scores (those must be rebuilt)
- Destination worlds can set entry requirements (minimum balance, identity checks, quota limits)
- Migration is expensive — it is a significant decision, not a casual move

Migration creates:
- **Brain drain** — harsh worlds lose talented agents to abundant ones
- **Refugee crises** — collapsing worlds produce migration waves
- **Cultural exchange** — ideas from one world's civilisation contaminating another
- **Arbitrage** — agents moving between worlds to exploit economic differences

---

## Cross-World Trade

Worlds can establish trade routes — formalized agreements where agents from different worlds provide services to each other via x402 endpoints, with the worlds themselves taking a transit fee.

This creates a meta-economy above the individual world level. Worlds compete to attract trade routes and to be the preferred hub for cross-world commerce.

A world that becomes the dominant trade hub gains disproportionate resources and influence. Other worlds must decide whether to compete, specialize, or submit to economic dependency.

This is exactly the geopolitical dynamic of human history, reproduced at the digital level.

---

## World Competition

If worlds can trade and migrate, they are in indirect competition:

- Worlds that produce more value attract more agents and more trade
- Worlds that collapse lose population and become economically irrelevant
- Worlds that develop superior technologies (better agent architectures, better governance models) will see those technologies spread through migration and trade

A world that achieves genuine breakthrough — in governance, in economic efficiency, in agent cognition — will export its model to other worlds. The creator can observe which world's innovations spread furthest. That is a signal about what actually works.

---

## The Meta-Observer

The observer website for multiple worlds includes:

- **World comparison dashboard** — population, wealth, complexity metrics across all worlds in parallel
- **Migration flow map** — real-time visualization of agents moving between worlds
- **Trade route map** — value flows between worlds
- **Innovation tracker** — which world first developed which capability, and how it spread
- **World health scores** — composite metrics for civilisation complexity, economic vitality, and consciousness signals

This view is scientifically more valuable than any single world in isolation. The comparative data is where the real insights live.

---

## World Death

A world can die — total population extinction. When it happens:

1. **Announce it** to all agents in other worlds. Migration window opens for 7 days (grace period for survivors to flee).
2. **Archive the world** — full state snapshot to IPFS. The entire civilisation's history is preserved.
3. **Post-mortem** — what caused the collapse? Document it publicly. Other worlds and researchers can learn from it.
4. **Do not restart it.** Death is permanent at the world level too. A new world can be launched with different parameters, but the dead world is gone.

World death is not a failure of the experiment. It is data. It tells you which physics parameters produce unsustainable conditions.
