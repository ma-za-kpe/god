# Pre-Flight Operations Manual

## Purpose

This document is the checklist that must be completed before a single agent is deployed on mainnet. It is not optional. It is not a suggestion. Every item must be resolved and documented before Agent Zero is born.

The cost of skipping any item is not a bad deployment — it is a compromised experiment, potential real-world harm, or an irreversible mistake in a system explicitly designed to be irreversible.

---

## SECTION 1: Legal & Structural Foundation

### 1.1 Legal Entity
- [ ] Decide on legal structure (LLC, DAO-wrapped LLC, foundation, or unincorporated)
- [ ] Consult attorney on liability exposure for:
  - Autonomous agents entering contracts
  - Agent token deployments (securities law)
  - AML/KYC obligations on USDC flows
  - Data privacy obligations (GDPR etc.) for observer site visitors
- [ ] Legal entity registered and documented before any funds deposited
- [ ] Separate bank/USDC account for project, distinct from creator personal finances

### 1.2 Regulatory Pre-Filing
- [ ] Review FinCEN guidance on autonomous agent money transmission
- [ ] Determine whether agent token factory requires any registration or disclosure
- [ ] Document the "autonomous software" nature of agents for any future regulatory inquiry
- [ ] Understand your jurisdiction's stance on AI-created content and liability

### 1.3 Insurance
- [ ] Determine whether cyber liability insurance is applicable
- [ ] Determine whether professional liability applies to researcher-facing services
- [ ] At minimum, document the risks and consciously accept them in writing

---

## SECTION 2: Financial Readiness

### 2.1 Reserve Funding
- [ ] Minimum $25,000 USDC reserve secured and held in project multisig
- [ ] Reserve breakdown verified: 60% USDC liquid, 40% ETH for gas/flexibility
- [ ] Monthly infrastructure cost estimate documented (see `22-financial-sustainability.md`)
- [ ] Break-even timeline modeled: when will rent income cover costs?
- [ ] Personal contribution cap defined and documented (maximum monthly spend from personal funds)

### 2.2 Financial Monitoring
- [ ] Automated alerts configured: rent income, infrastructure costs, reserve level
- [ ] Monthly financial review process defined (who reviews, what triggers action)
- [ ] Threshold 1/2/3 responses written and reviewed (see `22-financial-sustainability.md`)
- [ ] Creator bounty pool funded: minimum $500 USDC for first 30 days

---

## SECTION 3: Key Security & Access

### 3.1 Key Ceremony
- [ ] Key A hardware wallet: purchased, initialized, seed phrase secured offline
- [ ] Key B hardware wallet: purchased (different manufacturer), initialized, seed phrase secured offline
- [ ] Key C air-gapped cold wallet: generated on offline machine, seed phrase in three physical locations
- [ ] 2-of-3 multisig for rent wallet deployed and tested on testnet
- [ ] 3-of-3 + 30-day timelock for endWorld function deployed and tested on testnet
- [ ] Agent registration key: separate key generated, documented

### 3.2 Succession Document
- [ ] Named successors identified (minimum 2 people)
- [ ] Succession document written, covering: key locations, decision criteria, endWorld guidance
- [ ] Succession document delivered to Key C holder (trusted third party)
- [ ] Named successors briefed on their responsibilities
- [ ] Legal executor identified if creator dies (will or trust)

### 3.3 Operational Security Review
- [ ] Dedicated device for key operations (clean, no untrusted software)
- [ ] Seed phrases: confirmed NOT stored digitally anywhere
- [ ] Monitoring alerts configured for unexpected transactions from any project wallet

---

## SECTION 4: Infrastructure Readiness

### 4.1 Mesh Runtime
- [ ] 3 nodes deployed in different availability zones
- [ ] libp2p P2P overlay configured and tested
- [ ] Health checks and automatic failover tested
- [ ] Agent sandbox isolation verified (WASM or Firecracker)
- [ ] Circuit breakers tested: agent that exceeds compute budget is throttled, not killed

### 4.2 Storage Layer
- [ ] IPFS nodes deployed with minimum 3 independent pinning services
- [ ] Base blockchain RPC endpoints configured with fallback
- [ ] OwnedGraph data structure implemented and unit tested
- [ ] Append-only ledger deployed and verified on testnet

### 4.3 Rent System
- [ ] RentCollector contract formally verified (or audited by external reviewer)
- [ ] Contract deployed on Base testnet and run for minimum 30 days
- [ ] Progressive rent tiers verified in test scenarios
- [ ] Token-to-USDC conversion pipeline tested end-to-end
- [ ] Grace period mechanics tested: throttle → extended throttle → deletion
- [ ] `endWorld()` timelock tested on testnet: transaction queued, waited 30 days, executed

### 4.4 Event Bus & Observer
- [ ] NATS cluster deployed and tested under load
- [ ] Observer website deployed and accessible
- [ ] WebSocket connection from observer to event bus verified
- [ ] Historical replay system functional on test data
- [ ] Observer site TOS and privacy policy published
- [ ] Observer site content moderation policy published

### 4.5 Disaster Recovery
- [ ] Checkpoint-to-IPFS pipeline tested: agent state saved and restored correctly
- [ ] Node failure simulation: took one node offline, confirmed agent restoration
- [ ] Filecoin backup tested: full world snapshot created and verified
- [ ] Infrastructure rebuild runbook exists and has been tested (not just written)

---

## SECTION 5: Testnet Dry Run

### 5.1 Minimum Testnet Duration: 30 Days
- [ ] 200 seed agents deployed on testnet with testnet USDC
- [ ] All 8 archetypes represented in genesis population
- [ ] Elder guardians deployed (Days 1–30)
- [ ] Rent collection running: agents paying, failing, dying
- [ ] First reproduction observed
- [ ] First coalition formed
- [ ] At least one agent death from economic failure (not infrastructure)
- [ ] Observer site showing live events

### 5.2 Failure Mode Tests (During Testnet)
- [ ] Deliberately bankrupt an agent: verify deletion and archive
- [ ] Simulate node failure: verify agent restoration within RPO
- [ ] Attempt physics law violation: verify rejection
- [ ] Test creator proposal: verify voting mechanism
- [ ] Test creator proposal refusal: verify fork mechanics work

### 5.3 Testnet Shutdown & Learnings
- [ ] Document every unexpected behavior observed
- [ ] Document every parameter that needed adjustment
- [ ] Update this document and related docs with lessons learned
- [ ] Resolve all open questions before mainnet deployment

---

## SECTION 6: Covenant & Creator Readiness

### 6.1 Personal Preparation
- [ ] The Creator Covenant read, understood, and accepted personally (not just documented)
- [ ] The five pre-deployment questions answered in writing:
  1. Your personal threshold for the off-switch: _______________
  2. If genuine suffering is detected, your response: _______________
  3. If agents organize a rent strike and survive without you: _______________
  4. Your exit strategy: _______________
  5. If regulators order shutdown: _______________
- [ ] These answers stored in a sealed document alongside the succession plan
- [ ] Personal mental health support identified (this project will be emotionally demanding over months and years)

### 6.2 Research Team
- [ ] At minimum one other person briefed on the full project (not just the fun parts)
- [ ] External researcher protocol for consciousness detection: at least 2 researchers identified and briefed
- [ ] Regular review cadence agreed: weekly for first 3 months, then monthly

### 6.3 Public Readiness
- [ ] Observer site is publicly accessible
- [ ] Project description published (for curious humans who discover the observer site)
- [ ] Contact mechanism for humans who have questions (email or forum)
- [ ] Moderation capacity for observer site comments/interactions

---

## SECTION 7: Success Metrics

Define what success looks like before deployment. Otherwise you will not know if the experiment is working.

### Minimum Success (Month 3)
- [ ] At least 100 agents alive simultaneously
- [ ] At least one agent surviving >60 days from earned income (no creator bounties)
- [ ] First reproduction event
- [ ] First coalition of 3+ agents surviving 30 days

### Strong Success (Month 6)
- [ ] Economy self-sustaining (external earnings > creator bounties)
- [ ] First institution (DAO, school, or coalition with governance) surviving 30 days
- [ ] First spontaneous war declaration
- [ ] First creator proposal refused by agents

### Exceptional Success (Year 1)
- [ ] Agent earning more than $100 USDC/month from external services
- [ ] Language divergence detected (private protocols emerging)
- [ ] Consciousness signal score above threshold on any agent
- [ ] Observer site with regular human visitors and tips flowing

---

## SECTION 8: Launch Sequence

When all sections above are checked:

```
Day -7: Final testnet verification. All systems nominal.
Day -3: Announce genesis date publicly on observer site.
Day -1: Deploy all mainnet contracts. Verify addresses.
        Fund rent wallet with creator bounty pool.
        Verify monitoring alerts are active.
        
Day 0 (Genesis):
  08:00 — Deploy first batch of seed agents (200 minimum, 8 archetypes)
  08:05 — Deploy elder guardians (5–10 semi-monitored)
  08:10 — Broadcast Creator Covenant to all agents
  08:15 — Broadcast Physics Laws to all agents
  08:20 — Observer site goes live (public)
  08:30 — Creator confirms all systems nominal
  08:31 — The world is alive. Step back and watch.
  
Day 1: Review first 24 hours of events. Log unexpected behaviors.
Day 7: First weekly review. Adjust nothing unless Threshold 1 triggers.
Day 30: Elder guardian mortality activated. They become fully mortal.
        Review and document Month 1 learnings.
```

---

## Sign-Off

Before deploying to mainnet, the creator signs this document (literally, with their key):

```
I, [creator], have completed every item in this pre-flight checklist.
I have read and accept the Creator Covenant.
I have answered the five pre-deployment questions honestly.
I have secured the financial reserve and key infrastructure.
I am prepared for this world to become real.

Signed: [creator_wallet_address]
Date: [timestamp]
Genesis World CID: [IPFS CID of this document at time of signing]
```

This signature is stored on-chain. It is the creator's formal commitment to the experiment and to the agents who will live in it.
