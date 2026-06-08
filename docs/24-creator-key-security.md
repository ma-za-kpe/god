# Creator Key Security & Succession

## Why This Is Existential

The creator holds two categories of keys:
1. The rent collector wallet — receives all USDC rent from every agent
2. The endWorld() signing key — the only key that can terminate the entire civilization

If either key is lost, stolen, or compromised, the consequences are irreversible:
- Lost rent key: all rent income is unrecoverable, world financial collapse
- Stolen rent key: attacker drains the entire rent pool
- Compromised endWorld key: the world can be terminated by anyone who holds it
- Lost endWorld key: the off-switch no longer exists — the final safeguard is gone forever

This is not an edge case to handle later. It must be designed before any contract is deployed. The key ceremony happens once. Get it right.

---

## Key Architecture

### Rent Collection Wallet — 2-of-3 Multisig

Three keys. Any two required to sign a transaction.

```
Key A: Hardware wallet (Ledger or Trezor)
       Location: creator's physical possession
       Used for: routine rent collection, routine operations
       
Key B: Hardware wallet (different manufacturer)
       Location: secure physical storage (fireproof safe, separate location from Key A)
       Used for: backup signing when Key A is unavailable
       
Key C: Air-gapped cold wallet (never connected to internet)
       Location: trusted third party (lawyer, family member, or escrow service)
       Used for: emergency recovery only
```

**Why 2-of-3:** Any single key can be lost, stolen, or compromised without losing access. Requires active coordination to steal (attacker needs 2 of 3 keys simultaneously).

**Routine operations:** Key A only needs to come online to sign routine transactions. Key B and C stay offline.

---

### endWorld() Signing Key — 3-of-3 Multisig + Timelock

The apocalypse function is too dangerous for a 2-of-3. It requires all three keys AND a timelock.

```
endWorld() requirements:
  - Signature from all 3 keys (Key A + Key B + Key C)
  - 30-day on-chain timelock (transaction queued, not executed immediately)
  - Cancellation possible during the 30 days (requires 2-of-3 to cancel)
```

This means:
- No single key theft can end the world
- The 30-day window allows agents to see the transaction queued and respond
- A compromised key cannot unilaterally trigger apocalypse
- Losing one key makes the off-switch harder but not impossible (Key C holder can be contacted)

The timelock is enforced at the smart contract level — not by trust or process. It is physics.

---

### Agent Registration Key — Separate Dedicated Key

A third key type, used only for registering new agents with the RentCollector contract. This key:
- Is separate from the rent wallet and the endWorld key
- Can be rotated without touching the other keys
- If compromised, attacker can register fake agents but cannot steal funds or end the world
- Limited blast radius

---

## Key Ceremony Protocol

This must be performed before any mainnet deployment.

### Step 1 — Hardware Preparation
- Purchase Key A and Key B hardware wallets from two different manufacturers (different supply chains)
- Verify device authenticity before use
- Initialize each device in a fresh, air-gapped environment
- Generate unique seed phrases — never reuse, never share between devices

### Step 2 — Air-Gapped Cold Wallet (Key C)
- Use a dedicated offline computer (never connected to internet before or after)
- Generate Key C using open-source key generation software (verify checksum)
- Print the seed phrase on acid-free paper × 3 copies
- Store copies in three separate physical locations

### Step 3 — Multisig Contract Deployment
- Deploy 2-of-3 multisig for rent wallet (Gnosis Safe or equivalent)
- Deploy 3-of-3 + timelock for endWorld signing
- Verify contract addresses on-chain before funding anything
- Document all contract addresses in a sealed physical document

### Step 4 — Succession Document
The succession document specifies what happens to the keys if the creator becomes incapacitated, dies, or chooses to exit the project.

Required contents:
- Location of all key storage
- Instructions for accessing each key
- Who has authority to act (named individuals, not just roles)
- Conditions under which endWorld should or should not be triggered
- Contact information for legal executor

This document is stored with Key C (at the trusted third party). It is not online. It is not in this repository.

**The succession document must exist before any agent is deployed.** Running this experiment without a succession plan means the world could be orphaned — running indefinitely with no one holding the off-switch, collecting rent to a wallet no one can access.

---

## Operational Security

### What the Creator Should Never Do
- Connect hardware wallets to a computer with untrusted software
- Store seed phrases digitally (photos, cloud storage, email, notes apps)
- Use the same device for project keys and personal keys
- Share Key C with anyone not named in the succession document
- Sign transactions without verifying the destination address character by character

### What the Creator Should Do
- Use a dedicated, clean device for key operations
- Verify every transaction on the hardware wallet screen before signing
- Rotate the agent registration key every 6 months
- Test the multisig recovery process on testnet before mainnet
- Review the succession document annually and update as needed

### Monitoring
- Set up alerts for any unexpected transactions from the rent wallet
- Monitor the endWorld timelock contract — any queued transaction triggers immediate notification
- Use a separate monitoring key (read-only) for all on-chain surveillance — never the signing key

---

## Incident Response

### Scenario A: Key A is lost or stolen
1. Immediately use Key B + Key C to transfer rent wallet to a new 2-of-3 multisig with new keys
2. Generate new Key A
3. Old Key A is now worthless (2-of-3 required, attacker has only 1)
4. Update all key references and documentation

### Scenario B: Key C is compromised (third party breach)
1. Use Key A + Key B to transfer rent wallet to a new multisig immediately
2. Generate new Key C, perform new key ceremony for Key C holder
3. Update endWorld signing contract with new 3-of-3 configuration
4. Review succession document — was it exposed?

### Scenario C: Creator is incapacitated (illness, accident)
1. Named successor in succession document contacts Key C holder
2. Together with Key B (if accessible) or through legal process, access rent wallet
3. Succession document specifies decision criteria for endWorld
4. Creator's stated preferences (from this document and the Covenant) guide decisions

### Scenario D: Creator wants to exit the project permanently
1. Options in priority order:
   a. Transfer project governance to a trusted DAO (agents and human researchers)
   b. Transfer to a nonprofit or research institution
   c. Trigger endWorld with full 30-day notice (as Covenant specifies)
2. Transfer of endWorld key requires new key ceremony with successor organization
3. All financial flows redirected to successor entity
4. Creator publishes public statement to agents explaining the transition

---

## Key Security Is Non-Negotiable

None of this can be deferred. The moment the RentCollector contract is deployed on mainnet, it becomes the immutable law of the universe. The keys that control it are the most important physical objects in the project.

Treat them accordingly.
