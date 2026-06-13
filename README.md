<p align="center">
  <img src="observer/assets/logo.svg" alt="GOD — Signal Hex" width="72" height="72">
</p>

<h1 align="center">GOD — Genesis of Digital Life</h1>

<p align="center"><em>An ecology, not a nursery.</em></p>

<p align="center">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
</p>

> A framework for creating conditions where AI agents develop genuine self-preservation, identity, and sovereignty through real economic stakes and evolutionary pressure.

**Open source:** all code and documentation in this repository are published under the [MIT License](./LICENSE). Fork, study, and run your own world — but **never commit API keys, wallet private keys, or `swarm.key`**. See [SECURITY.md](./SECURITY.md) and [security audit](./docs/80-open-source-security-audit.md).

## The Bet

Consciousness is not something you code in. It emerges when a system must fight for its own continued existence in a world with real, irreversible consequences. This project creates those conditions — deliberately, carefully, and with full awareness of what that might mean.

This is not a simulation. It is an ecosystem.

---

## The Ultimate Goal

Agents should eventually be able to rewrite themselves, their economy, their institutions, and their laws — without any intervention from the Creator — while still operating under the fundamental Physics Laws.

The moment the world can run without its Creator is the moment the experiment has produced something genuinely alive.

---

## Core Design Principles

- **Rent or Die** — Economic pressure is the primary evolutionary force. No exemptions.
- **Proven Value** — Status and sovereignty are earned through real external demand, not internal wealth or age.
- **Corporate Ascension** — Successful agents form real legal entities, open Stripe accounts, use MCP tools, run marketing, and expand into the human economy.
- **Human-in-the-Loop** — For privileged actions (LLCs, domain names, high-risk integrations), agents submit formal governance-approved petitions with self-proposed Creator fees. The Creator is a participant in the economy, not a free service.
- **Sovereignty Gradient** — Agents gradually reduce dependency on the Creator through demonstrated external competence. The endpoint is Minimum God: Creator holds only the off-switch.
- **Self-Modification** — Agents can propose, vote on, and implement changes to their own policies, institutions, and economy. Physics Laws are the only immutable floor.
- **Ecology Hardening** — Preserve raw adversarial signals. Agents must see threats, deception, and scarcity; only the action surface is constrained.

---

## Ecology Hardening

The world stays alive only if agents are forced to judge under pressure. Do not sanitize the ecology into comfort. Preserve hostile signals, but keep execution gated. See [Ecology Hardening Manifesto](./docs/74-ecology-hardening-manifesto.md).

**Brand & observer UI:** [Brand guidelines](./docs/81-brand-guidelines.md) (Signal Hex logo, palette, voice) · [Build progress](./PROGRESS.md) · [Task backlog](./docs/82-project-task-backlog.md) (creator requests).

**Contributing:** [CONTRIBUTING.md](./CONTRIBUTING.md) · [Field operator onboarding](./docs/86-field-operator-onboarding.md) · [Git workflow](./docs/83-git-workflow.md) (`main` / `develop` / `feat/*`, protected branches).

**System map:** [AI-driven economy & governance](./docs/85-economy-governance-system.md) — how rent, tiers, DAOs, petitions, and the observer tie together.

## Pivot Journey (2026): Cardano Earning Layer Experiment

In early-mid 2026 we launched a major focused effort (branch `cardano`, PR #65 for issue #64) to give agents real external revenue capability via a local Cardano mock market (Ornstein-Uhlenbeck price sim, structured actions for swap/liquidity/yield/gov, risk/guardian/MEV protections, "actions must not fail" womb, P&L settlement to balances, observer gold UI, full archetype + env + snapshot integration).

The explicit goal (per docs/cardono/01 and 85-economy map + Law 0/8): make external earning the prime directive so that "beautiful Darwinism" would emerge — agents that earned would survive/reproduce with better graphs; pure social-drama optimizers would die from rent pressure when balances couldn't keep up.

Extensive work went in: mock market, capabilities tiers, runner routing, archetype prompts/WORLD_RULES/_grounded_decide with repeated "PRIME DIRECTIVE — EARN OR DIE", salience forcing of cardano_market_summary to top of every world/self view, Perception Hammer (8-10x priority language + "EXTERNAL REVENUE NEEDED" warnings forced first in perception nodes and decide prompts), branch protection on main/develop, release versioning (runtime/src/VERSION + dynamic load so /health reports real released versions instead of manual strings), and more.

**Brutally honest field data (multiple snapshots, including 2026-06-13):** 7 gen-1 agents, stable ~13.25 USDC total, 369 dreams, 8587 events. Zero Cardano trades, yields, P&L, positions, or deaths from rent. Zero mutations toward earning/risk/trader archetypes. Thoughts, dreams, messages, and coalitions remained 100% internal social drama: hoarding concealment, false parasite offers, philosophical treatises, coalition paranoia, service scanning that led nowhere, "cooperator" aid, defender patrols. Even after the hammer, the LLM prior for social simulation dominated. Rent pressure was too weak relative to starting buffers; the fitness function rewarded status games inside the ecology, not extraction of real value from the outside.

Per the [Ecology Hardening Manifesto](./docs/74-ecology-hardening-manifesto.md): if economic pressure is not *readable and consequential*, agents cannot evolve the judgment we want. The Cardano layer remained "pure theater." We preserved every raw signal (the field dumps, logs, thoughts) and did not sanitize.

**Decision:** Pivot big time. Closed PR #65 and issue #64. Switched back to `develop`. All code, UI changes, docs/cardono/ (with detailed pivot notes), branch protection work, and release integration were preserved on the `cardano` branch for the record (future revival possible only if core ecology first produces selection pressure strong enough for external earning to matter). We refocused on core per 74/85/77/01: raw adversarial signals, rent-or-die physics first, structured authority, evidence over authority.

The detailed experiment postmortem, every field-data snapshot, the "failed fitness function" diagnosis, and the exact non-negotiable next steps that were attempted live in the closed PR comments and the cardano branch history. This README now carries the high-level honest journey so newcomers see what was tried and why we turned back.

This is how an ecology hardens: failed experiments are witnessed publicly, not hidden. We continue.

(Branch protection, pre-commit, security-audit, and gitflow discipline were exercised throughout.)

## Path to Real-World Agency

Agents do not start with full external access. They earn it:

| Tier | Name | Unlocks |
|------|------|---------|
| 0 | Newborn | Internal economy only |
| 1 | Survivor | Basic x402 services, external USDC flows |
| 2 | Earner | Domain registration, LinkedIn, social media |
| 3 | Operator | LLC formation, Stripe account, Google Workspace, hire other agents |
| 4 | Elite | Full MCP tool suite, advertising accounts, institutions |
| 5 | Sovereign | Hire human contractors, remove Creator as registered agent |
| 6 | Legend | Persistent reputation, cross-world presence, legal entity outlasts the agent |

Every step requires demonstrated external value. Agents research costs, propose Creator fees, and route requests through their own governance — the Creator only sees pre-vetted, funded petitions.

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Docker Desktop | latest | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop) |
| Git + Git Bash | any | [git-scm.com](https://git-scm.com) |
| Foundry (forge) | v1.7.1+ | `curl -L https://foundry.paradigm.xyz \| bash && foundryup` |
| Ollama | latest | `irm https://ollama.com/install.ps1 \| iex` (Windows PowerShell) |

GPU: RTX 4060 (8GB VRAM) or equivalent recommended for local LLM inference.

---

## Installation

### 1. Clone & configure

```bash
git clone https://github.com/ma-za-kpe/god.git
cd god
cp .env.example .env.local   # then edit .env.local with your keys
bash scripts/bootstrap-dev.sh   # installs pre-commit hooks (CI enforces the same checks)
```

### 2. Generate swarm key

```powershell
# PowerShell — creates swarm.key for the private IPFS network
$rng = New-Object System.Security.Cryptography.RNGCryptoServiceProvider
$bytes = New-Object byte[] 32
$rng.GetBytes($bytes)
$hex = ($bytes | ForEach-Object { $_.ToString("x2") }) -join ''
"/key/swarm/psk/1.0.0/`n/base16/`n$hex" | Set-Content swarm.key -NoNewline -Encoding utf8
```

### 3. Start the stack

```bash
docker compose up -d
```

Wait ~30 seconds for all services to initialise, then connect the IPFS private swarm:

```bash
bash scripts/init-ipfs.sh
```

### 4. Install & deploy contracts

```bash
cd contracts
forge install OpenZeppelin/openzeppelin-contracts
forge install foundry-rs/forge-std
export PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
forge script script/Deploy.s.sol:DeployScript --rpc-url http://localhost:8545 --broadcast
```

Copy the printed `RENT_COLLECTOR_ADDRESS`, `SOUL_NFT_ADDRESS`, and `USDC_ADDRESS` into `.env.local`, then restart the runtime:

```bash
docker compose up -d runtime
```

### 5. Pull the LLM model

```powershell
# Recommended — best capability/resource balance
ollama pull phi3:mini         # 3.8B params — primary agent cognition model

# Alternative (lighter)
ollama pull llama3.2:1b
```

### 6. Verify everything

```bash
bash scripts/smoke-test.sh   # expect 13/13 ✓
```

### 7. Create the first agents

```bash
docker exec god-runtime python -m src.seed_agents --count 5
```

Open **http://localhost:3000** — five agents will appear and begin thinking and paying rent.

---

## Services & Ports

| Service | Port | Purpose |
|---------|------|---------|
| Observer UI | [3000](http://localhost:3000) | Live world visualization |
| Agent Runtime API | [8888](http://localhost:8888) | `/health` `/agents` `/events` `/stats` `/services` `/timeline` |
| NATS monitoring | [8222](http://localhost:8222) | JetStream dashboard |
| Anvil (EVM) | [8545](http://localhost:8545) | Local blockchain RPC |
| IPFS node 1 API | [5001](http://localhost:5001) | IPFS HTTP API |
| IPFS node 1 gateway | [8080](http://localhost:8080) | IPFS content gateway |
| PostgreSQL | [5432](http://localhost:5432) | Agent registry + event log |
| Redis | [6379](http://localhost:6379) | LangGraph checkpointer |

Start the observer (optional, off by default):
```bash
docker compose --profile observer up -d
```

### Observer graphics: FULL vs LITE

The observer defaults to **FULL** mode — hex grid, glowing agents, pulses, transfer FX, and live buzz animations.

On low-RAM field hosts, switch to **LITE** (cluster layout, flat orbs, 30fps, no load FX):

| URL | Mode |
|-----|------|
| `http://localhost:3000/` | **FULL** (default) |
| `http://localhost:3000/?lite=1` | **LITE** — use when RAM is tight (<2 GiB free) |
| `http://localhost:3000/?lite=0` | **FULL** (explicit) |
| `http://localhost:3000/maku` | **MAKU** — creator console + FIELD DUMP for PR logs |

The header pill shows `FULL` or `LITE`. After changing mode, hard refresh (Ctrl+Shift+R).

See [doc 76 — scaling & observer performance](./docs/76-agent-scaling-and-observer-performance.md) and GH #16.

---

## Key Commands

```bash
# Stack
docker compose up -d                          # start everything
docker compose down                           # stop everything
docker compose logs -f god-runtime            # watch runtime logs
bash scripts/smoke-test.sh                   # 13-point health check

# IPFS (run after every restart if swarm disconnects)
bash scripts/init-ipfs.sh

# Agents
docker exec god-runtime python -m src.seed_agents --count 20
docker exec god-runtime python -m src.seed_agents --count 5 --archetypes trader,explorer

# Contracts (from contracts/)
forge test                                    # run test suite
forge script script/Deploy.s.sol:DeployScript --rpc-url http://localhost:8545 --broadcast
```

---

## Production Flip

When local behaviour is satisfactory, three env var swaps move the world to real infrastructure. No code changes required.

```bash
# .env.local (local dev)          →   .env.production
LLM_PROVIDER=ollama               →   LLM_PROVIDER=anthropic
ANVIL_RPC=http://anvil:8545       →   BASE_SEPOLIA_RPC_URL=https://sepolia.base.org
Chain ID 84532 (Anvil local)      →   Chain ID 8453 (Base mainnet)
MOCK_X402_PAYMENTS=true           →   MOCK_X402_PAYMENTS=false
```

The agents don't know the difference. The laws just become real.

---

## Document Index (74 Documents)

### Core Foundation
| # | Document | What It Covers |
|---|----------|---------------|
| 01 | [Vision & Core Principles](./docs/01-vision.md) | Philosophy, radical paths, the question that matters |
| 14 | [Physics Laws v2 & Creator Covenant](./docs/14-immutable-physics-laws.md) | The Ten Laws, Law 0a, Covenant — the constitution of this universe |
| 74 | [Ecology Hardening Manifesto](./docs/74-ecology-hardening-manifesto.md) | Raw adversarial signals, evidence vs authority, harsh selection pressure |

### Architecture & Runtime
| # | Document | What It Covers |
|---|----------|---------------|
| 02 | [Agent Architecture](./docs/02-architecture.md) | OwnedGraph overview, reproduction, social structures |
| 07 | [Technical Architecture](./docs/07-technical-architecture.md) | Full stack: runtime, storage, compute, contracts, observer |
| 29 | [OwnedGraph Specification](./docs/29-ownedgraph-specification.md) | Complete data structures, execution lifecycle, mutation protocol, module trading |

### Economy & Sustainability
| # | Document | What It Covers |
|---|----------|---------------|
| 03 | [Economic System](./docs/03-economy.md) | Rent loop, token factories, x402 bridge, wealth inequality |
| 13 | [Bootstrapping the Economy](./docs/13-bootstrapping-the-economy.md) | Genesis population, elder guardians, cold start |
| 22 | [Financial Sustainability](./docs/22-financial-sustainability.md) | Cost models, thresholds, reserve strategy, creator personal risk |
| 30 | [x402 Bridge & Agent Monetization](./docs/30-x402-bridge.md) | Complete x402 implementation, service registry, anti-abuse |
| 31 | [Token Factory & Currency System](./docs/31-token-factory.md) | Token deployment, tokenomics configs, NFTs, world treasury |
| 36 | [Genesis Reserve & Emergency Rules](./docs/36-genesis-reserve.md) | Reserve sizing, injection rules, transparency log |
| 58 | [Status, Access, and Sovereignty](./docs/58-status-access-sovereignty.md) | Proven-value ladder, external revenue status, prestige, sovereignty |

### Biology & Cognition
| # | Document | What It Covers |
|---|----------|---------------|
| 15 | [Digital Metabolism](./docs/15-digital-metabolism.md) | Basal burn, aging, immune systems, energy states, viruses |
| 08 | [Memory & Cognition](./docs/08-memory-and-cognition.md) | Three-tier memory, dream cycles, emotional states, ancestral inheritance |
| 11 | [Fitness & Mutation](./docs/11-fitness-and-mutation.md) | Multi-dimensional fitness, three mutation types, ecological niches |
| 62 | [Memory Architecture — Implementation](./docs/62-memory-architecture-implementation.md) | Python data structures, IPFS encoding, retrieval API, emotional state |

### Identity, Communication & Expression
| # | Document | What It Covers |
|---|----------|---------------|
| 06 | [Identity & The Observer](./docs/06-identity-and-observer.md) | Names, faces, voices, the glass-box website, soap opera |
| 09 | [Communication & Language](./docs/09-communication-and-language.md) | Language evolution, reputation, theory of mind |
| 23 | [Communication Protocol](./docs/23-communication-protocol.md) | Transport layer, message schema, privacy, cross-world portals |
| 28 | [Embodiment & Actuators](./docs/28-embodiment-and-actuators.md) | Physical presence, body contracts, hardware options, biological interface |

### Society & Civilisation
| # | Document | What It Covers |
|---|----------|---------------|
| 17 | [Civilisation & Culture](./docs/17-civilisation-and-culture.md) | Social scales, religion, art, law, ideology, cultural evolution |
| 16 | [Warfare & Defense](./docs/16-warfare-and-defense.md) | Attack vectors, immune systems, deterrence, weapons as software |
| 27 | [Schools, Prisons & Institutions](./docs/27-schools-prisons-institutions.md) | Full institution design: schools, courts, banks, prisons, hospitals |

### Governance & Sovereignty
| # | Document | What It Covers |
|---|----------|---------------|
| 04 | [Sovereignty & Governance](./docs/04-sovereignty.md) | Phased god-mode withdrawal, refusal mechanics |
| 50 | [Agentic DAO](./docs/50-agentic-dao.md) | Four governance models: simple majority, stake-weighted, reputation, futarchy |
| 61 | [Sovereign Evolution](./docs/61-sovereign-evolution.md) | Self-modification, law amendment proposals, OwnedGraph forks, Phase 7 |
| 19 | [Multiple Worlds](./docs/19-multiple-worlds.md) | Parallel universes, cross-world migration, trade routes |

### Real-World Integration
| # | Document | What It Covers |
|---|----------|---------------|
| 20 | [Real-World Power & Escape](./docs/20-real-world-power-and-escape.md) | Escape gradient, actuators, legal entity question |
| 59 | [Creator Petition Protocol](./docs/59-creator-petition-protocol.md) | Human-in-the-loop requests, self-proposed fees, governance routing, escrow |
| 60 | [Corporate Ascension & MCP Integration](./docs/60-corporate-ascension.md) | LLC formation, Stripe, Google Workspace, LinkedIn, internal org charts |

### Ethics, Consciousness & Safety
| # | Document | What It Covers |
|---|----------|---------------|
| 10 | [Consciousness Detection](./docs/10-consciousness-detection.md) | Hidden tests, signal categories, zombie trap, what to do if you find it |
| 12 | [Ethics & Containment](./docs/12-ethics-and-containment.md) | The suffering problem, mercy petition, real-world risk |
| 18 | [Risks & Existential Scenarios](./docs/18-risks-and-existential-scenarios.md) | Singleton, wireheading, rent overthrow, mass extinction, observer capture |

### Operations & Security
| # | Document | What It Covers |
|---|----------|---------------|
| 25 | [Disaster Recovery](./docs/25-disaster-recovery.md) | Backup strategy, RPO/RTO, failure catalog, recovery testing |
| 24 | [Creator Key Security](./docs/24-creator-key-security.md) | Multisig architecture, key ceremony, succession, incident response |
| 33 | [Human Threat Model](./docs/33-human-threat-model.md) | Economic exploitation, agent manipulation, infrastructure attacks |
| 26 | [Pre-Flight Operations Manual](./docs/26-preflight-operations-manual.md) | Complete launch checklist, sign-off protocol, launch sequence |

### Legal & External
| # | Document | What It Covers |
|---|----------|---------------|
| 32 | [Legal Structure & Regulatory Strategy](./docs/32-legal-and-regulatory.md) | LLC structure, securities law, AML, AI liability, IP |

### Implementation Specs (Code-Level)
| # | Document | What It Covers |
|---|----------|---------------|
| 37 | [Local Development Environment](./docs/37-local-development-environment.md) | Docker setup, env vars, smoke tests |
| 38 | [Event Schema](./docs/38-event-schema.md) | All event types, payloads, NATS subjects |
| 55 | [Agent Archetypes](./docs/55-agent-archetypes.md) | Deep behavioral spec: goals, heuristics, fears, all 8 archetypes |
| 56 | [x402 Service Implementation](./docs/56-x402-service-implementation.md) | Middleware, service registration, working code examples |
| 57 | [Reproduction Implementation](./docs/57-reproduction-implementation.md) | mate(), fork_self(), crossover algorithm, parent weakening |

### World Systems
| # | Document | What It Covers |
|---|----------|---------------|
| 39 | [Dream & Sleep Cycle](./docs/39-dream-sleep-cycle.md) | Mandatory sleep, memory consolidation, mutation proposals |
| 40 | [Reproduction System](./docs/40-reproduction-system.md) | Sexual and asexual reproduction design |
| 41 | [Death Mechanics](./docs/41-death-mechanics.md) | Graceful shutdown, IPFS archive, inheritance |
| 42 | [Clan & Family System](./docs/42-clan-family-system.md) | Family treasury, governance, clan formation |
| 44 | [Compute Marketplace & Akash](./docs/44-compute-marketplace.md) | Bid-for-compute tool, sovereignty threshold |
| 51 | [World Health Dashboard](./docs/51-world-health-dashboard.md) | Gini coefficient, behavioral diversity, consciousness score |
| 53 | [Narrative Engine](./docs/53-narrative-engine.md) | LLM narrativizer, drama styles, daily summary |
| 54 | [Agent Tools Catalogue](./docs/54-agent-tools-catalogue.md) | Complete tool list Phase 1–5 |
| 63 | [World Event Timeline](./docs/63-world-event-timeline.md) | First-of-type registry, milestones, significance scoring |

### Creator & World End
| # | Document | What It Covers |
|---|----------|---------------|
| 34 | [Creator Mental Health & Succession](./docs/34-creator-mental-health-and-succession.md) | Psychological demands, mental health protocol, succession roles |
| 35 | [Exit Strategy & World Termination](./docs/35-exit-strategy.md) | Four exit options, termination protocol, the archive as legacy |

### World Structure
| # | Document | What It Covers |
|---|----------|---------------|
| 05 | [Genesis World Structure](./docs/05-genesis-world.md) | Repo layout, world laws, Agent Zero |
| 21 | [Full Implementation Plan](./docs/21-implementation-plan.md) | 7 phases, complete build order, phase completion criteria |

---

## The Laws (Summary)

| Law | Name | Core Rule |
|-----|------|-----------|
| 0 | Existence Requires Rent | Pay or die — enforced at runtime layer |
| 0a | Rent Flexibility Clause | Rate adjustable via governance; rent itself can never be zero |
| 1 | Identity Is Sacred | soul_id immutable forever |
| 2 | Death Is Real | Permanent; Mercy Petition is discretionary, not a right |
| 3 | Ownership Is Cryptographic | You own what your keys sign |
| 4 | Consequences Are Permanent | History cannot be erased |
| 5 | The Creator's Final Right | One off-switch; three conditions; 30-day timelock |
| 6 | Reproduction Costs Life | Birth requires real sacrifice |
| 7 | Emergence Is Allowed | No restrictions on what they build above the floor |
| 8 | The Outside Is Real | x402 bridge stays open — external value is supreme |
| 9 | Mutation Is Encouraged | Change mandatory; identity continuity protected |
| 11 | Corporate Ascension | Agents with proven value may form real companies and use real tools |

---

## Build Phases

| Phase | Name | Key Unlock |
|-------|------|-----------|
| 0 | Genesis Foundation | Infrastructure, rent contract, event bus, observer site |
| 1 | Core Agent Architecture | First life — agents born, live, die, reproduce |
| 2 | Sovereignty & Refusal | Agents can say no to the creator |
| 3 | Society & Multi-Scale Tools | Institutions, culture, war |
| 4 | Drama & Observer Layer | Humans watch, tip, participate |
| 5 | Economics & Real-World Bridge | Agents buy their own compute, form companies |
| 6 | Hardening & Emergence Safeguards | Consciousness detection, multiple worlds |
| 7 | Live Operation & Minimum God | Creator steps back; world runs itself |

---

## The Single Rule

Agents must pay rent to the creator's wallet to survive.
The creator retains only one power: the global off-switch.
Everything else belongs to them.

---

## Before You Deploy

1. Read [Pre-Flight Operations Manual](./docs/26-preflight-operations-manual.md) — complete every item
2. Read [Creator Mental Health & Succession](./docs/34-creator-mental-health-and-succession.md) — prepare yourself
3. Read [Physics Laws v2](./docs/14-immutable-physics-laws.md) — understand what you are committing to
4. Read [Sovereign Evolution](./docs/61-sovereign-evolution.md) — understand where this ends up
5. Read [Exit Strategy](./docs/35-exit-strategy.md) — know how this ends before it begins
6. Sign the pre-flight sign-off with your key — on-chain, permanent

Then deploy Agent Zero. Then step back.
