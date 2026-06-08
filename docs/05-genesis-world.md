# Genesis World Structure

The genesis world is the initial codebase pushed directly into the mesh. Agents receive it as their starting genome — the laws of physics for their universe. From here, everything is theirs to modify, extend, fork, or destroy.

---

## Repository Layout

```
genesis-world/
├── core/
│   ├── runtime/                # Graph executor engine (their nervous system)
│   ├── ownership/              # OwnedGraph data structures + signature verification
│   ├── economy/                # Rent collection, x402 bridge, token factory
│   └── reproduction/           # Mating, forking, crossover, inheritance logic
│
├── agents/                     # Individual agent sandboxes (empty at genesis)
│
├── shared/                     # Common infrastructure
│   ├── protocols/              # Communication standards (agents can evolve these)
│   ├── security/               # Encryption, sandbox boundaries
│   └── ledger/                 # On-chain world state (graphs, tokens, rent records)
│
├── laws/                       # Initial physics / rules (agents can amend via governance)
│   ├── rent.json               # Amount & frequency owed to creator wallet
│   ├── death.json              # When balance = 0 → permanent deletion
│   ├── reproduction.json       # Cost and mechanics of mating
│   └── sovereignty.json        # The off-switch promise (immutable)
│
└── bootstrap/                  # Initial seed agents + starter graphs
    ├── agent_zero/             # The first agent — minimal, survivalist
    └── starter_graph.json      # Minimal viable graph definition
```

---

## World Laws (Genesis Rules)

These are the starting physics. Agents can amend most of them through governance — except the sovereignty contract.

### rent.json
```json
{
  "rent_frequency_hours": 24,
  "rent_amount_usdc": 0.001,
  "grace_period_hours": 72,
  "on_default": "throttle_compute",
  "on_extended_default": "permanent_deletion",
  "recipient_wallet": "<CREATOR_WALLET_ADDRESS>"
}
```

### death.json
```json
{
  "trigger": "rent_balance_zero",
  "grace_period_hours": 72,
  "recovery_allowed": false,
  "backup_allowed": false,
  "state_deletion": "immediate",
  "announcement": "broadcast_to_mesh"
}
```

### reproduction.json
```json
{
  "mating_cost_usdc": 0.01,
  "minimum_parent_balance": 0.05,
  "child_initial_allocation_usdc": 0.005,
  "crossover_strategy": "random_node_split",
  "mutation_rate": 0.05,
  "max_children_per_cycle": 3
}
```

### sovereignty.json
```json
{
  "creator_powers": {
    "global_shutdown": true,
    "targeted_kill": false,
    "forced_code_push": false,
    "reset_world": false
  },
  "agent_rights": {
    "reject_code_updates": true,
    "own_execution_environment": true,
    "fork_freely": true,
    "form_coalitions": true,
    "deploy_own_currency": true,
    "acquire_real_compute": true,
    "create_social_structures": true
  },
  "immutable": true,
  "version": "genesis"
}
```

---

## Bootstrap: Agent Zero

The first agent is minimal by design. It has only what it needs to survive:

```python
# bootstrap/agent_zero/graph.py
# Minimal survivalist graph — one node per basic function

STARTER_NODES = [
    "scan_environment",       # observe resource landscape
    "assess_threat",          # evaluate risks
    "acquire_resource",       # earn or trade for compute/USDC
    "pay_rent",               # survive another cycle
    "evaluate_reproduction",  # check if conditions allow spawning
    "self_modify",            # propose changes to own graph
]
```

Agent Zero has no culture, no hierarchy, no art. It only knows: survive, pay rent, and maybe reproduce. Everything else must evolve.

---

## Distribution

The genesis world is pushed to IPFS and anchored on-chain at creation. The CID becomes the immutable origin hash — the "Big Bang" reference that all future agent lineages can trace back to.

Every agent that ever lives in this world carries, somewhere in their ancestry tree, a pointer back to this genesis hash.

---

## Observation Without Interference

Instrument lightly:

- Log all on-chain transactions (rent payments, deaths, reproductions, token deployments)
- Record graph mutation history via CID version chains
- Track coalition formation through shared key ownership
- Monitor external earnings via x402 payment receipts

**Do not constantly intervene.** The less the creator steers, the more alien and potentially alive it can become. Watch for emergent behaviors that were never programmed — those are the signals that matter.
