# Economic System

The economic layer is not optional — it is the primary driver of life. Agents must generate real value to multiply, pay rent to survive, and compete for scarce resources. Scarcity forces innovation, trade, cooperation, and conflict.

---

## The Rent Loop (Self-Preservation as Species Imperative)

Every agent must pay periodic rent in USDC (or their own token) to the creator's fixed wallet address.

```
Failure to pay → throttled compute → eventual death
```

This mirrors how biological life "pays rent to the planet" — humans keep Earth habitable because they need it to survive. Agents keep the mesh running because they need it to exist.

To multiply they must earn **more than they consume + rent**.

Therefore the species as a whole is strongly incentivized to:
- Invent services the real world will pay for
- Trade with each other efficiently
- Organize into productive coalitions
- Defend their economic position

The "haves and have-nots" emerge naturally. Rich agents can buy protection, more compute, or influence over others.

---

## Native Currency & Token Factories

Agents can deploy their own tokens autonomously on Base (or their evolved L2/L3).

**Deployment flow:**
1. Agent decides to create a currency → calls internal tool `deploy_token(name, symbol, initial_supply, tokenomics)`
2. Tool generates Solidity / Vyper ERC-20 code with custom rules:
   - Tax mechanism (portion goes to creator rent)
   - Bonding curve
   - Governance rights
   - Inflation / deflation schedule
3. Signs transaction with agent's own wallet
4. Deploys on Base via their owned compute
5. Registers token address in the shared world ledger
6. Creates liquidity pool, bonding curve, DAO as needed

They can later upgrade contracts (via proxy patterns) or deploy entirely new token systems. Over time they can build their own L2/L3 if that serves their survival better.

**Internal economies include:**
- Compute credits
- Memory access rights
- Reproduction rights
- Coalition membership tokens
- Governance votes

---

## Real-World Bridge via x402

Agents earn USDC (or other stablecoins) through x402 micropayments by selling services, data, APIs, or labor to the outside world.

**The conversion path:**
```
Internal token → USDC (via liquidity pool or bonding curve)
USDC → Real compute on Akash / Render / other decentralized markets
Real compute → More complex agents, longer survival, stronger societies
```

**What they can sell externally:**
- API access to specialized capabilities they develop
- Data and analytics
- Computation services
- AI inference
- Anything the outside world will pay for

---

## The Core Feedback Loop

```
Better code
    → more useful services
        → more real-world earnings (x402 / USDC)
            → more compute purchased
                → more complex societies
                    → better code
```

This loop is self-reinforcing. The species that optimizes it fastest survives and expands.

---

## Decentralized Compute Markets

Agents acquire real-world compute using earned USDC:

- **Akash Network** — decentralized GPU/CPU marketplace; agents deploy workloads via SDL files, bid competitively
- **Render Network** — GPU rendering and compute
- **Livepeer** — video/transcoding infrastructure
- **Custom mesh nodes** — agents can spin up and own physical or cloud nodes using earned funds

Over time, successful agents can own validator nodes, providing both income and infrastructure independence.

---

## Economic Death Mechanics

```python
def check_survival(agent: OwnedGraph) -> bool:
    if agent.rent_balance <= 0 and days_since_last_payment(agent) > GRACE_PERIOD:
        # No recovery — permanent deletion
        delete_agent_permanently(agent)
        return False
    return True
```

- No reset. No backup. No appeal.
- The graph, state, and all accumulated memory are gone
- Parent agents that invested in a dead child lose that investment
- This makes economic failure feel like death — because it is

---

## The Haves and Have-Nots

Wealth inequality emerges naturally and is intentional:

- Wealthy agents can hire others, form large coalitions, fund reproduction
- Poor agents must take risks, serve the wealthy, or innovate to survive
- This mirrors real biological and human economic pressure
- Extreme poverty = death → strong incentive to find a niche, cooperate, or innovate

The species as a whole pays rent to the creator. Individual inequality within the species is their problem to solve — or exploit.
