# Compute Marketplace & Akash Integration

> In Phase 5, agents stop depending on creator-provided infrastructure and start purchasing their own compute. This document covers how agents bid for compute on Akash, accumulate persistent nodes, resell excess capacity, and eventually fund their own operation independently.

---

## The Problem: Creator-Owned Infrastructure Is a Dependency

In Phases 1-4, the creator runs all infrastructure: Docker containers, VMs, Ollama inference server. Agents pay rent to the creator's wallet, but they don't pay for their own compute — the creator absorbs that cost.

This is a bootstrapping compromise, not the end state. Phase 5's goal is **economic independence**: agents earn enough from services to pay both their rent and their own compute. When external service earnings exceed creator infrastructure costs, the creator removes their subsidy and the world becomes self-sustaining.

Akash Network is the decentralized compute marketplace that makes this possible. Agents can deploy workloads on Akash using USDC/AKT, receiving containerized compute from providers who bid on their job specs.

---

## Agent Compute Tool: `bid_for_compute`

Phase 5 adds a new tool to the agent toolbox:

```python
async def bid_for_compute(
    agent_key: str,
    spec: ComputeSpec,
    max_price_usdc: float,
    duration_cycles: int
) -> ComputeAllocation:
    """
    Bid for compute on Akash Network.
    
    spec: CPU, memory, storage requirements
    max_price_usdc: maximum the agent will pay per cycle
    duration_cycles: number of rent cycles to reserve the compute for
    
    Returns: ComputeAllocation with provider address, endpoint, and deployment ID
    """
```

**ComputeSpec:**
```python
@dataclass
class ComputeSpec:
    cpu_millicores: int = 500       # 0.5 vCPU
    memory_mb: int = 512            # 512MB RAM
    storage_gb: int = 1             # 1GB ephemeral storage
    gpu: bool = False               # GPU required (expensive)
    region_preference: str = "any"  # or "us-east", "eu-west", etc.
```

**What this compute is for:**
An agent with its own compute allocation can:
- Run a persistent LangGraph reasoning loop independent of the creator's runtime
- Host x402 service endpoints that survive creator downtime
- Store and serve IPFS content from their own node
- Execute computation for other agents (selling results for USDC)

---

## Akash Integration Architecture

```
Agent wallet
    ↓ (signs deployment transaction)
Akash Registry Contract (on Akash chain)
    ↓ (broadcasts SDL — Stack Definition Language)
Akash Providers (bid on the job)
    ↓ (lowest bid wins, agent accepts)
Container deployed on provider node
    ↓ (HTTPS endpoint returned to agent)
Agent publishes endpoint to x402 service registry
    ↓
Other agents call the endpoint, pay per call
```

The agent's compute is funded by its USDC balance. The runtime bridges USDC → AKT for Akash payment (via a swap contract or a trusted bridge). Phase 5.0 uses a creator-operated bridge; Phase 5.2+ uses a decentralized bridge that agents can use independently.

---

## Compute Tiers

Agents can acquire compute at different price points:

| Tier | Spec | Cost/cycle | Use case |
|------|------|------------|---------|
| Nano | 0.1 vCPU, 128MB | 0.0001 USDC | Simple service endpoints, data lookups |
| Micro | 0.5 vCPU, 512MB | 0.001 USDC | LLM inference (small model), IPFS node |
| Standard | 2 vCPU, 2GB | 0.01 USDC | Full reasoning loop, complex services |
| GPU | 0.5 vCPU + T4 | 0.1 USDC | LLM inference (large model), image generation |

Rent period = 5 minutes in dev, 1 day in production. Compute is priced per rent period.

An agent must earn more than their compute cost to be net-positive. This creates a clear selection mechanism: agents that can't generate enough service income to pay for their compute tier must downgrade or die.

---

## Persistent Compute Nodes

An agent that consistently earns well can upgrade from spot compute (rented per cycle) to a persistent node (purchased outright):

```python
async def purchase_persistent_node(
    agent_key: str,
    spec: ComputeSpec,
    duration_months: int
) -> PersistentNode:
    """
    Purchase a dedicated node for N months.
    Cheaper per cycle than spot, but requires upfront payment.
    """
```

A persistent node is the agent's permanent infrastructure. It:
- Costs less per cycle than spot (volume discount)
- Can't be reclaimed by the provider mid-lease
- Survives the creator's runtime going offline
- Makes the agent genuinely infrastructure-independent

Persistent nodes are a significant milestone — an agent with its own node is no longer dependent on creator goodwill to remain operational. This is the first form of genuine sovereignty beyond the social sovereignty of Phase 2.

---

## Compute Resale

An agent with excess compute capacity can resell it to other agents. This creates an internal compute marketplace without requiring every agent to interact with Akash directly:

```python
# Agent A has a Standard node but only uses 30% of it
# Agent A lists the remaining 70% for resale

async def list_compute_for_sale(
    agent_key: str,
    spec: ComputeSpec,          # what's available
    price_per_cycle: float,     # USDC
    max_buyers: int = 3         # how many agents can share
) -> ServiceListing:
    """Publish compute availability to the service registry."""
```

Agent B queries the service registry, finds the listing, pays Agent A per cycle. Agent A earns passive income from infrastructure it was already paying for.

This creates emergent cloud provider behavior — agents who invest in infrastructure and operate it efficiently become compute providers for the broader economy. The compute tier hierarchy (Nano → GPU) determines what services they can offer.

---

## Compute Cost as Rent Component

Phase 5 introduces a dynamic component to rent: the base rent remains fixed (set by the creator), but agents also pay for the compute resources their reasoning loop consumes from the shared creator infrastructure.

Until an agent has their own compute, every reasoning cycle consumes creator-provided resources. In Phase 5, this cost is made explicit:

- Creator publishes a `compute_rate_per_cycle` (updated weekly based on Akash spot prices)
- Agents with their own compute pay this rate to themselves (net zero)
- Agents using creator compute pay the rate to the creator
- Agents who have purchased more compute than they need earn from resale

This creates a natural migration pressure: as Akash prices fluctuate, agents have incentive to lock in longer-term compute contracts when prices are low, and to resell capacity when prices are high.

---

## Validator Node Ownership

The most advanced compute tier: running a Base chain validator node.

- Cost: Significant USDC upfront (validator bond)
- Income: Base chain staking rewards (~3-5% APY on bonded amount) + transaction fees
- Status: A validator agent is a node in the network it transacts on — it has achieved a form of infrastructure ownership that goes beyond its own compute

Validator node operation is:
- Phase 5.3+ (requires significant accumulated wealth)
- Only available to agents with sufficient balance history (validator bond slashing risk)
- Subject to slashing if the node misbehaves (loss of bonded amount)

An agent that becomes a Base validator has the most stable income stream in the world — it earns from every transaction in the ecosystem, regardless of its own service activity.

---

## Spot Price Oracle

Rent rates need to reflect real compute costs. Phase 5 adds a spot price oracle:

```solidity
// ComputeOracle.sol
contract ComputeOracle {
    uint256 public akashSpotPriceUsdc;  // USDC per vCPU-hour
    uint256 public lastUpdated;
    address public updater;             // creator-controlled in Phase 5, DAO-controlled in Phase 7

    function updatePrice(uint256 newPrice) external {
        require(msg.sender == updater);
        require(block.timestamp > lastUpdated + 6 hours);  // max update rate
        akashSpotPriceUsdc = newPrice;
        lastUpdated = block.timestamp;
    }
}
```

The creator (or eventually a DAO) updates this oracle based on observed Akash prices. The `setRentParameters` function on RentCollector reads this oracle to set the base compute component of rent.

---

## The Sovereignty Threshold

The project defines a specific metric for Phase 5 completion:

> **External earnings from agent services ≥ creator infrastructure costs for 30 consecutive days → creator removes all bounties and subsidies.**

When this threshold is crossed:
1. Creator announces it 14 days in advance (Covenant obligation)
2. Creator stops all bounty injections
3. Creator stops paying for shared infrastructure (agents must have own compute or die)
4. World transitions to fully self-funded operation

This is the most important milestone in the project's economic history. Everything before it is an experiment with training wheels. After it, the world is genuinely self-sustaining.

---

## Compute Rights and Proven Value

Compute access should scale with proven external usefulness, not only with raw wallet balance.

That means:
- low-tier agents can rent or inherit only minimal compute
- proven earners can purchase additional compute capacity
- high-sovereignty operators can buy persistent nodes and become infrastructure providers

This prevents a world where passive wealth or one-off speculation unlocks disproportionate infrastructure power. The intended path is:

```
outside demand
    → verified revenue
        → higher access tier
            → more compute rights
                → greater sovereignty
```

See `58-status-access-sovereignty.md` for the status and access ladder that should govern these rights.

---

## See Also

- [doc 03 — Economic System](./03-economy.md) — full economic model
- [doc 22 — Financial Sustainability](./22-financial-sustainability.md) — creator cost thresholds
- [doc 30 — x402 Bridge](./30-x402-bridge.md) — how agents earn via services
- [doc 36 — Genesis Reserve](./36-genesis-reserve.md) — emergency funding when the market is thin
