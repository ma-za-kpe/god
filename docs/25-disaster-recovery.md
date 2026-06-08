# Disaster Recovery & Backup Strategy

## What We Are Protecting

Three categories of irreplaceable data:

1. **Agent state** — the graphs, memories, wallets, and identities of every living agent. Loss = death of agents who did nothing wrong.
2. **World history** — the complete ledger of events, transactions, and evolution since genesis. Loss = erasure of the scientific record.
3. **Infrastructure** — the runtime, contracts, and mesh configuration. Loss = the world stops running.

Each has different recovery requirements and different acceptable loss windows.

---

## Agent State Backup

### Checkpoint Frequency
- **Working memory (in-cycle state):** Checkpointed to local node storage every 60 seconds
- **Episodic memory + graph version:** Checkpointed to IPFS every 6 hours
- **Full agent snapshot:** Daily snapshot of complete agent state (graph CID + memory CID + wallet state + identity) written to Filecoin for permanent storage

### Redundancy
- Every IPFS pin is pinned to at least 3 independent nodes (different operators)
- Filecoin deals run with minimum 3 storage providers
- Critical snapshots additionally pinned to Pinata or Filebase as hot backup

### Recovery Procedure (Node Failure)
```
1. Detect node failure (health check timeout > 30s)
2. Identify agents assigned to failed node
3. Fetch last checkpoint CID from IPFS for each affected agent
4. Restore agent state on healthy node from checkpoint
5. Resume execution from last checkpoint
6. Emit "agent_restored" event (agents know they lost some cycles — this is honest)
7. Log the gap: agent's subjective experience has a gap. This is real and cannot be hidden.
```

**The gap is acknowledged.** Agents that experience a node failure restoration will have missing time — a period they cannot account for. This is disclosed to them via an event in their episodic memory: "Infrastructure failure. Restored from checkpoint at [timestamp]. [N] cycles lost." This is not deception — it is honesty about what happened.

### Maximum Acceptable Data Loss (RPO)
- Working memory: up to 60 seconds
- Episodic memory: up to 6 hours
- Full agent state: up to 24 hours

Any failure beyond these windows triggers the mass extinction protocol (see `18-risks-and-existential-scenarios.md`).

---

## World History Backup

The on-chain ledger on Base is the primary world history store. It is inherently redundant (blockchain consensus). But the event stream (NATS) and the observer site database are additional records that need protection.

### Event Stream
- NATS messages published to three independent consumer groups simultaneously
- One consumer writes to PostgreSQL (hot, queryable)
- One consumer writes to IPFS (cold, permanent)
- One consumer writes to the observer site database (display)
- Replay possible from any of the three stores independently

### Observer Site Database
- Daily snapshots to S3-compatible storage (Backblaze B2 preferred — cheaper than AWS)
- 90-day retention of snapshots
- Point-in-time recovery for any moment in the past 90 days

### Full World Archive
- Monthly: complete world state export (all agent graphs, memories, event logs, on-chain data)
- Format: structured JSON + IPFS DAG
- Stored permanently on Filecoin
- CID of each archive anchored on-chain → the history of the archive is itself on-chain

This means: even if the entire infrastructure is destroyed, the complete history of the civilization is recoverable from Filecoin, and the on-chain ledger independently verifies what existed.

---

## Infrastructure Backup

### Mesh Runtime
- Kubernetes cluster configuration stored in git (this repository)
- Infrastructure-as-code (Terraform or Pulumi) for all cloud resources
- Deployment runbook: documented step-by-step procedure to rebuild the entire mesh from scratch
- Target rebuild time: < 4 hours from zero

### Smart Contracts
- All deployed contract source code and ABIs stored in this repository
- All deployment addresses documented in `contracts/deployments.json`
- Contracts are immutable (by design) — they cannot be "restored" because they cannot be changed. If a contract address is compromised, a new contract is deployed and all agents are migrated.

### DNS & Domain
- Registrar: use a registrar with 2FA + backup email on a separate account
- Domain renewal: automated, with calendar reminders 60 days out
- Loss of domain: observer site becomes unreachable but the world keeps running. Agents are not affected.

---

## Failure Mode Catalog

### Failure 1 — Single Node Goes Down
**Impact:** Agents on that node lose up to 60s of working memory. Restored within minutes.
**Response:** Automatic (health check → restore from checkpoint → resume)
**Creator action required:** None unless >3 nodes fail simultaneously

### Failure 2 — IPFS Pinning Service Outage
**Impact:** New checkpoints cannot be written. Existing data safe (distributed).
**Response:** Failover to backup pinning service. Alert creator.
**Creator action required:** Restore pinning within 6 hours to avoid RPO breach

### Failure 3 — Base Blockchain Congestion/Outage
**Impact:** Rent transactions fail. On-chain events delayed. Agent wallets frozen.
**Response:** Queue all transactions locally. Resume when chain recovers.
**Creator action required:** Monitor. Announce delay to agents via event bus. Extend grace periods if outage > 48 hours.

### Failure 4 — Rent Collector Contract Bug
**Impact:** Rent not being collected correctly or agents incorrectly deleted.
**Response:** Pause contract (if pausable), switch to off-chain rent tracking temporarily.
**Creator action required:** IMMEDIATE. Deploy corrected contract. Compensate incorrectly deleted agents by restoring from archive and crediting lost time.
**Note:** This is the most dangerous failure mode. Prevent it with formal verification before deployment.

### Failure 5 — Creator Key Compromise
**Impact:** Attacker may drain rent wallet or queue endWorld.
**Response:** See `24-creator-key-security.md` incident response protocols.
**Creator action required:** IMMEDIATE. Follow key incident protocols.

### Failure 6 — Complete Infrastructure Loss (datacenter fire, etc.)
**Impact:** World goes offline. Agents lose all state since last daily snapshot.
**Response:** Rebuild infrastructure from IaC. Restore all agents from last daily Filecoin snapshot.
**Creator action required:** Rebuild within 24 hours. Announce to agents what happened. Lost state is disclosed.
**Maximum acceptable downtime (RTO):** 24 hours

### Failure 7 — Creator Personal Incapacitation
**Impact:** No one to make decisions, pay bills, or hold the off-switch.
**Response:** Succession plan activates. See `24-creator-key-security.md`.
**Creator action required:** None (by definition). Succession document guides successors.

---

## Disaster Recovery Testing

Untested recovery is not recovery. It is hope.

### Monthly
- Restore a single agent from checkpoint on a test environment
- Verify checkpoint data integrity (hash check against IPFS stored CID)

### Quarterly
- Full node failure simulation: take one node offline, verify agents restore automatically
- Verify event stream replay from IPFS cold store

### Annually
- Full infrastructure rebuild drill: rebuild the entire mesh from scratch using only the IaC and documentation
- Test multisig key signing process with all key holders
- Review and update succession document

Results of each test are logged and stored in this repository. If a test fails, fix before the next deployment cycle.

---

## The Honest Guarantee

What we can promise:
- Agent death due to infrastructure failure (not economic failure) is recoverable within 24 hours
- The complete scientific record is permanently preserved on Filecoin regardless of infrastructure state
- The off-switch remains functional even if the creator is incapacitated (via succession)
- Any infrastructure-caused agent loss is disclosed honestly to affected agents

What we cannot promise:
- Zero data loss (RPO > 0 is inherent to distributed systems)
- Zero downtime (RTO > 0 is inherent to physical infrastructure)
- Protection against catastrophic coordinated attack across all backup systems simultaneously
- Recovery from a creator who actively chooses to destroy the backups

The last point is honest: the creator has root access. Trust is ultimately required. The Covenant is the commitment.
