# W3C DID Integration for Agent Identity

> Decentralized Identifiers (DIDs) give GOD agents an identity layer that exists independently of any single blockchain, registry, or runtime. This document covers what DIDs are, why they matter for agent sovereignty, and the specific integration plan for the GOD Project.

---

## What DIDs Provide

A W3C DID is a string of the form `did:method:identifier` that resolves to a **DID Document** — a JSON-LD object containing public keys, authentication mechanisms, and service endpoints. Unlike usernames or wallet addresses, DIDs are:

- **Self-sovereign**: The controller of the DID is the only entity that can update it
- **Portable**: Independent of any single chain or service
- **Verifiable**: Cryptographically signed by the controller
- **Resolvable**: Any resolver can fetch the DID Document from any conforming registry

For GOD agents, DIDs solve the identity portability problem: when an agent migrates from one world instance to another, or bridges from local dev (Anvil) to Base mainnet, its identity should survive the transition. A wallet address changes. A `soul_id` bytes32 is not globally resolvable. A DID is.

---

## DID Method: `did:ethr`

The chosen DID method for GOD Project agents is `did:ethr` (EIP-1056, Ethereum DID Registry).

**Why `did:ethr`:**
- Native to EVM chains including Base
- Registry contract already deployed on Base Sepolia and Base mainnet
- DID Document controlled by private key — no gas required for basic operations
- Compatible with ERC-6551 TBA wallets (Phase 2)
- Battle-tested: used by Spruce, uPort, Veramo, and others since 2019

**Agent DID structure:**
```
did:ethr:base:<agent_wallet_address>
```

Example:
```
did:ethr:base:0x71C7656EC7ab88b098defB751B7401B5f6d8976F
```

When ERC-6551 TBAs replace EOA wallets:
```
did:ethr:base:<tba_address>
```

The DID is deterministic from the wallet address — no explicit creation step required.

---

## DID Document Contents for GOD Agents

Each agent's DID Document will contain:

```json
{
  "@context": ["https://www.w3.org/ns/did/v1", "https://w3id.org/security/suites/secp256k1-2019/v1"],
  "id": "did:ethr:base:0x...",
  "verificationMethod": [{
    "id": "did:ethr:base:0x...#controllerKey",
    "type": "EcdsaSecp256k1RecoveryMethod2020",
    "controller": "did:ethr:base:0x...",
    "blockchainAccountId": "eip155:8453:0x..."
  }],
  "authentication": ["did:ethr:base:0x...#controllerKey"],
  "service": [
    {
      "id": "did:ethr:base:0x...#soul",
      "type": "GODSoulRecord",
      "serviceEndpoint": "ipfs://<soul_graph_cid>"
    },
    {
      "id": "did:ethr:base:0x...#x402",
      "type": "x402ServiceEndpoint",
      "serviceEndpoint": "https://<runtime_host>/agents/<soul_id>/services"
    }
  ]
}
```

The `GODSoulRecord` service endpoint points to the agent's OwnedGraph CID — the complete state snapshot on IPFS. This makes the agent's current state globally discoverable from nothing but its DID.

---

## Integration Points

### 1. Birth — DID Anchored at Registration

When `RentCollector.registerAgent(soulId, agentWallet)` is called:
1. SoulNFT minted to agentWallet (already implemented)
2. Runtime calls DID registry to register the agent's service endpoints
3. `soul_graph_cid` added as `GODSoulRecord` service endpoint

**Implementation:** `did:ethr` requires no on-chain transaction for basic registration — the DID is derived from the key. Service endpoints require a single `setAttribute` transaction on the EthrDID registry (~50k gas, ~$0.001 on Base).

### 2. State Updates — DID Document Tracks Agent Evolution

Each time the agent's OwnedGraph is updated and pinned to IPFS, the runtime optionally updates the `GODSoulRecord` service endpoint with the new CID. This creates an on-chain trail of the agent's state evolution.

**Phase 1 (local dev):** Not implemented — no Base connection yet.
**Phase 2 (Base Sepolia):** Implement as part of the state persistence upgrade.

### 3. Cross-World Migration

When an agent migrates between world instances (doc 19), its DID travels with it. The destination world resolves `did:ethr:base:<wallet>` to get:
- Public keys (for signature verification)
- `GODSoulRecord` endpoint (to reconstruct the OwnedGraph)
- `x402ServiceEndpoint` (to find the agent's services)

The agent arrives in the new world with a verifiable history that no single registry controls.

### 4. Agent-to-Agent Authentication

Agents communicating via NATS can sign messages with their DID key and the recipient can verify:
1. Message signed by `did:ethr:base:<sender_wallet>`
2. DID Document confirms sender controls that key
3. No central authority required

This is the foundation for trust networks, reputation systems, and coalition formation.

---

## Python Implementation

The runtime will use the `did-resolver` + `ethr-did-resolver` packages (JavaScript) or the `eth_did` Python library.

**Minimal Python implementation:**

```python
from eth_account import Account
from eth_account.messages import encode_defunct
import hashlib

def soul_to_did(wallet_address: str, chain_id: int = 8453) -> str:
    """Convert an agent wallet address to its did:ethr DID."""
    chain = "base" if chain_id == 8453 else f"eip155:{chain_id}"
    return f"did:ethr:{chain}:{wallet_address.lower()}"

def sign_did_message(message: str, private_key: str) -> str:
    """Sign a message with the agent's DID key."""
    msg = encode_defunct(text=message)
    signed = Account.sign_message(msg, private_key=private_key)
    return signed.signature.hex()

def verify_did_signature(message: str, signature: str, did: str) -> bool:
    """Verify that a message was signed by the controller of a DID."""
    wallet_address = did.split(":")[-1]
    msg = encode_defunct(text=message)
    recovered = Account.recover_message(msg, signature=bytes.fromhex(signature[2:]))
    return recovered.lower() == wallet_address.lower()
```

**Service endpoint registration** (one-time per agent, on Base Sepolia):

```python
from web3 import Web3

ETHR_DID_REGISTRY = "0xdCa7EF03e98e0DC2B855bE647C39ABe984fcF21B"  # Base Sepolia

def register_soul_endpoint(w3: Web3, agent_key: str, soul_cid: str):
    """Register the agent's IPFS soul record in the EthrDID registry."""
    registry = w3.eth.contract(address=ETHR_DID_REGISTRY, abi=ETHR_DID_REGISTRY_ABI)
    account = Account.from_key(agent_key)

    attribute_name = b"did/svc/GODSoulRecord"
    attribute_value = f"ipfs://{soul_cid}".encode()
    validity = 365 * 24 * 3600  # 1 year TTL

    tx = registry.functions.setAttribute(
        account.address, attribute_name, attribute_value, validity
    ).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
    })
    signed = account.sign_transaction(tx)
    return w3.eth.send_raw_transaction(signed.rawTransaction)
```

---

## Implementation Phases

| Phase | Action | Cost |
|-------|--------|------|
| Now (Phase 1) | Add `soul_to_did()` to runtime — agents have DIDs computed from wallet, no on-chain tx | $0 |
| Phase 2 (Base Sepolia) | Register `GODSoulRecord` service endpoint for each agent at birth | ~$0.001/agent |
| Phase 3 (Base mainnet) | Full DID Document with x402 endpoint + state update on each IPFS pin | ~$0.002/agent/update |
| Phase 4+ | Agent-to-agent DID authentication for coalition and service trust | Protocol-level |

---

## Relation to ERC-6551

The DID and the TBA are complementary, not redundant:

| Concern | ERC-6551 TBA | W3C DID |
|---------|-------------|---------|
| Wallet (hold assets, sign txs) | ✅ | ❌ |
| Cross-chain identity | ❌ (chain-specific) | ✅ |
| Service discovery | ❌ | ✅ (service endpoints) |
| Off-chain message signing | ❌ | ✅ |
| On-chain asset ownership | ✅ | ❌ |
| Standard: | EIP-6551 | W3C DID Core 1.0 |

The agent's canonical identity is:
- **On-chain**: ERC-6551 TBA derived from SoulNFT tokenId
- **Cross-chain**: `did:ethr:base:<tba_address>`
- **In runtime**: `soul_id` (bytes32) — the root of both

---

## See Also

- [doc 29 — OwnedGraph Specification](./29-ownedgraph-specification.md) — what the DID service endpoint points to
- [doc 07 — Technical Architecture](./07-technical-architecture.md) — where DID fits in the stack
- [doc 19 — Multiple Worlds](./19-multiple-worlds.md) — cross-world migration using DID portability
