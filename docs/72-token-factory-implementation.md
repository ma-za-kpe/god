# Token Factory — Implementation Spec

> Code-level specification for agent-deployable ERC-20 tokens described in doc 31. Covers the `AgentToken.sol` contract, `token_factory.py` runtime module, web3 deployment flow, the `tokens` DB table (already in `init-db.sql`), the MCP tool interface, and API endpoints.

---

## `contracts/src/AgentToken.sol`

A minimal ERC-20 that agents deploy. Parameterized at construction. No upgrades — immutable once deployed.

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/// @title AgentToken — Deployable ERC-20 for GOD Project agents
/// @dev Deployed by runtime on behalf of agent wallets
contract AgentToken is ERC20, Ownable {
    uint8 private _decimals;
    uint256 public constant MAX_SUPPLY = 1_000_000_000 * 10**18;

    // Transfer tax (basis points, max 1000 = 10%)
    uint16 public transferTaxBps;
    address public taxRecipient;

    event TokenDeployed(address indexed owner, string name, string symbol, uint256 initialSupply);

    constructor(
        string memory name_,
        string memory symbol_,
        uint8 decimals_,
        uint256 initialSupply,
        uint16 _transferTaxBps,     // 0 = no tax
        address _taxRecipient,      // address(0) = burn
        address owner_
    ) ERC20(name_, symbol_) Ownable(owner_) {
        require(initialSupply <= MAX_SUPPLY, "Supply exceeds max");
        require(_transferTaxBps <= 1000, "Tax too high");
        _decimals = decimals_;
        transferTaxBps = _transferTaxBps;
        taxRecipient   = _taxRecipient;
        _mint(owner_, initialSupply);
        emit TokenDeployed(owner_, name_, symbol_, initialSupply);
    }

    function decimals() public view override returns (uint8) {
        return _decimals;
    }

    function _update(address from, address to, uint256 value) internal override {
        if (transferTaxBps > 0 && from != address(0) && to != address(0)) {
            uint256 tax = value * transferTaxBps / 10000;
            uint256 net = value - tax;
            if (taxRecipient == address(0)) {
                // Burn
                super._update(from, address(0), tax);
            } else {
                super._update(from, taxRecipient, tax);
            }
            super._update(from, to, net);
        } else {
            super._update(from, to, value);
        }
    }

    /// @dev Owner can mint additional supply (up to MAX_SUPPLY)
    function mint(address to, uint256 amount) external onlyOwner {
        require(totalSupply() + amount <= MAX_SUPPLY, "Would exceed max supply");
        _mint(to, amount);
    }
}
```

Add to `contracts/src/`. Compile with:
```
forge build
```

The deployment bytecode + ABI are then used by `token_factory.py` at runtime.

---

## `runtime/src/token_factory.py` — Full Implementation

```python
# runtime/src/token_factory.py
"""
token_factory.py — Deploy ERC-20 tokens on behalf of agents.
Phase 1: deploys to Anvil local chain.
Phase 2+: deploys to Base Sepolia / Base mainnet.
"""
import json
import logging
import os
import time
import uuid

import psycopg2
import psycopg2.extras

log = logging.getLogger("god.token_factory")

DATABASE_URL    = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID        = os.getenv("WORLD_ID", "local-dev-world-1")
ANVIL_RPC       = os.getenv("ANVIL_RPC", "http://anvil:8545")
TOKEN_DEPLOY_FEE_USDC = float(os.getenv("TOKEN_DEPLOY_FEE_USDC", "1.0"))

# Compiled AgentToken artifact path (populated by `forge build`)
ARTIFACT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "contracts", "out", "AgentToken.sol", "AgentToken.json"
)


def _load_artifact() -> tuple[str, list]:
    """Load compiled contract bytecode and ABI from Foundry artifact."""
    try:
        with open(ARTIFACT_PATH) as f:
            artifact = json.load(f)
        bytecode = artifact["bytecode"]["object"]
        abi      = artifact["abi"]
        return bytecode, abi
    except FileNotFoundError:
        raise RuntimeError(
            "AgentToken artifact not found. Run: docker exec god-runtime "
            "sh -c 'cd /app && forge build' (or forge build in contracts/)"
        )


def _get_web3():
    """Get a Web3 connection to the chain."""
    from web3 import Web3
    w3 = Web3(Web3.HTTPProvider(ANVIL_RPC))
    if not w3.is_connected():
        raise RuntimeError(f"Cannot connect to chain at {ANVIL_RPC}")
    return w3


async def deploy_token(
    soul_id: str,
    wallet_address: str,
    wallet_private_key: str,
    name: str,
    symbol: str,
    initial_supply: int,
    decimals: int = 18,
    transfer_tax_bps: int = 0,
    tax_recipient: str = "0x0000000000000000000000000000000000000000",
) -> dict:
    """
    Deploy an ERC-20 token on behalf of an agent.
    Deducts TOKEN_DEPLOY_FEE_USDC from agent's balance.
    Returns token record.
    """
    # 1. Check agent balance
    balance = _get_agent_balance(soul_id)
    if balance < TOKEN_DEPLOY_FEE_USDC:
        raise ValueError(
            f"Insufficient balance: {balance:.4f} USDC. "
            f"Token deployment costs {TOKEN_DEPLOY_FEE_USDC} USDC."
        )

    # 2. Validate inputs
    if len(symbol) > 10:
        raise ValueError("Token symbol must be 10 characters or fewer")
    if initial_supply <= 0:
        raise ValueError("Initial supply must be positive")
    if transfer_tax_bps > 1000:
        raise ValueError("Transfer tax cannot exceed 10% (1000 bps)")

    # 3. Load contract artifact
    bytecode, abi = _load_artifact()

    # 4. Deploy
    try:
        w3 = _get_web3()
        account = w3.eth.account.from_key(wallet_private_key)

        Contract = w3.eth.contract(abi=abi, bytecode=bytecode)

        supply_in_wei = initial_supply * (10 ** decimals)

        tx = Contract.constructor(
            name,
            symbol,
            decimals,
            supply_in_wei,
            transfer_tax_bps,
            w3.to_checksum_address(tax_recipient),
            w3.to_checksum_address(wallet_address),
        ).build_transaction({
            "from":  account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "gas":   3_000_000,
            "gasPrice": w3.to_wei("1", "gwei"),
        })

        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        if receipt["status"] != 1:
            raise RuntimeError(f"Token deployment reverted. tx={tx_hash.hex()}")

        contract_address = receipt["contractAddress"]
        tx_hash_hex = tx_hash.hex()

    except Exception as e:
        log.error(f"Token deployment failed for {soul_id[:8]}: {e}")
        raise

    # 5. Deduct fee from agent balance
    _deduct_balance(soul_id, TOKEN_DEPLOY_FEE_USDC)

    # 6. Persist to DB
    now = int(time.time())
    _persist_token(contract_address, soul_id, name, symbol,
                   initial_supply, now, tx_hash_hex)

    # 7. Emit event
    from .event_emitter import get_emitter
    emitter = await get_emitter()
    await emitter.emit("economy", "token.deployed", {
        "agent_id":         soul_id,
        "contract_address": contract_address,
        "name":             name,
        "symbol":           symbol,
        "initial_supply":   initial_supply,
        "tx_hash":          tx_hash_hex,
        "narrative":        f"{soul_id[:8]} launches ${symbol} — {name} with {initial_supply:,} tokens.",
    })

    log.info(f"TOKEN DEPLOYED: ${symbol} ({contract_address}) by {soul_id[:8]}")
    return {
        "contract_address": contract_address,
        "name":             name,
        "symbol":           symbol,
        "initial_supply":   initial_supply,
        "tx_hash":          tx_hash_hex,
        "deploy_fee_paid":  TOKEN_DEPLOY_FEE_USDC,
    }


def get_agent_tokens(soul_id: str) -> list[dict]:
    """Return all tokens deployed by this agent."""
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur  = conn.cursor()
        cur.execute(
            "SELECT * FROM tokens WHERE owner_soul_id = %s ORDER BY deployed_at DESC",
            (soul_id,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close(); conn.close()
        return rows
    except Exception as e:
        log.debug(f"get_agent_tokens failed: {e}")
        return []


def get_world_tokens() -> list[dict]:
    """Return all tokens ever deployed in this world."""
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur  = conn.cursor()
        cur.execute(
            """
            SELECT t.*, a.current_name AS owner_name
            FROM tokens t
            JOIN agents a ON t.owner_soul_id = a.soul_id
            ORDER BY t.deployed_at DESC
            """,
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close(); conn.close()
        return rows
    except Exception as e:
        log.debug(f"get_world_tokens failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_agent_balance(soul_id: str) -> float:
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur  = conn.cursor()
    cur.execute("SELECT COALESCE(balance_usdc, 0) AS bal FROM agents WHERE soul_id = %s",
                (soul_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return float(row["bal"]) if row else 0.0


def _deduct_balance(soul_id: str, amount: float):
    conn = psycopg2.connect(DATABASE_URL)
    cur  = conn.cursor()
    cur.execute(
        "UPDATE agents SET balance_usdc = balance_usdc - %s WHERE soul_id = %s",
        (amount, soul_id),
    )
    conn.commit()
    cur.close(); conn.close()


def _persist_token(contract_address, soul_id, name, symbol, initial_supply, now, tx_hash):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur  = conn.cursor()
        cur.execute(
            """
            INSERT INTO tokens
                (contract_address, owner_soul_id, name, symbol, initial_supply, deployed_at, on_chain_tx)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (contract_address) DO NOTHING
            """,
            (contract_address, soul_id, name, symbol, initial_supply, now, tx_hash),
        )
        conn.commit()
        cur.close(); conn.close()
    except Exception as e:
        log.debug(f"_persist_token failed: {e}")
```

---

## MCP Tool Interface

The token factory is exposed as an MCP tool (already seeded in `mcp_tools` as a future tool). The agent-facing tool schema:

```json
{
  "name": "deploy_token",
  "description": "Deploy a new ERC-20 token with custom name, symbol, supply, and optional transfer tax",
  "parameters": {
    "name":              { "type": "string",  "description": "Full token name, e.g. 'Iron Coin'" },
    "symbol":            { "type": "string",  "description": "Ticker symbol, e.g. 'IRON' (max 10 chars)" },
    "initial_supply":    { "type": "integer", "description": "Number of tokens to mint initially" },
    "transfer_tax_bps":  { "type": "integer", "description": "Transfer tax in basis points (0–1000). 0 = no tax." },
    "tax_destination":   { "type": "string",  "description": "Where tax goes: 'burn' or a wallet address" }
  },
  "cost_usdc": 1.0,
  "requires_tier": 3,
  "requires_corporate": false
}
```

The `agent_runner.py` tool dispatcher calls `deploy_token()` when it detects a `deploy_token` action in the agent's decision output.

---

## New API Endpoints

Add to `main.py`:

```python
@app.get("/tokens")
async def list_tokens():
    """All tokens deployed in this world."""
    from .token_factory import get_world_tokens
    return {"tokens": get_world_tokens(), "count": len(get_world_tokens())}

@app.get("/agents/{soul_id}/tokens")
async def get_agent_tokens_endpoint(soul_id: str):
    """Tokens deployed by a specific agent."""
    from .token_factory import get_agent_tokens
    tokens = get_agent_tokens(soul_id)
    return {"soul_id": soul_id, "tokens": tokens, "count": len(tokens)}

@app.post("/tokens/deploy")
async def deploy_token_endpoint(body: dict):
    """
    Deploy a token. Requires: soul_id, wallet_address, wallet_private_key,
    name, symbol, initial_supply.
    In production, private key never travels over the wire — use a signing
    proxy or the agent's MCP tool dispatch instead.
    """
    from .token_factory import deploy_token
    try:
        result = await deploy_token(
            soul_id            = body["soul_id"],
            wallet_address     = body["wallet_address"],
            wallet_private_key = body["wallet_private_key"],
            name               = body["name"],
            symbol             = body["symbol"],
            initial_supply     = body.get("initial_supply", 1_000_000),
            decimals           = body.get("decimals", 18),
            transfer_tax_bps   = body.get("transfer_tax_bps", 0),
            tax_recipient      = body.get("tax_destination", "0x" + "0" * 40),
        )
        return result
    except ValueError as e:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"error": str(e)})
```

**Security note**: The `POST /tokens/deploy` endpoint accepts a private key in the body — for local dev only. In production, agents sign transactions via their TBA (ERC-6551 token-bound account) using a secure key management service; private keys never leave the agent's secure enclave.

---

## Build Steps

1. Add `AgentToken.sol` to `contracts/src/`
2. Run `forge build` to generate `contracts/out/AgentToken.sol/AgentToken.json`
3. The `ARTIFACT_PATH` in `token_factory.py` points to this file
4. The runtime container mounts `contracts/` so the artifact is accessible
5. Add `web3` to `runtime/requirements.txt`

### `requirements.txt` addition

```
web3>=6.15.0
```

---

## Timeline Integration

`timeline.py` already has:
```python
"economy.token.deployed": "first.token_deployed"
```

And `FIRST_NARRATIVES`:
```
"first.token_deployed": "⊕ First token deployed. Currency is born."
```

The first time any agent deploys a token, this fires automatically.

---

## Agent Tool Dispatcher Integration

In `agent_runner.py`, add token deployment to the tool dispatch table:

```python
TOOL_DISPATCH = {
    "deploy_token": _dispatch_token_deploy,
    # ... other tools
}

async def _dispatch_token_deploy(agent: dict, tool_args: dict) -> str:
    from .token_factory import deploy_token
    try:
        result = await deploy_token(
            soul_id            = agent["soul_id"],
            wallet_address     = agent["wallet_address"],
            wallet_private_key = _get_agent_key(agent["soul_id"]),
            name               = tool_args.get("name", f"{agent['current_name']} Token"),
            symbol             = tool_args.get("symbol", "AGT"),
            initial_supply     = tool_args.get("initial_supply", 1_000_000),
            transfer_tax_bps   = tool_args.get("transfer_tax_bps", 0),
        )
        return f"Token ${result['symbol']} deployed at {result['contract_address']}"
    except Exception as e:
        return f"Token deployment failed: {e}"
```

---

## See Also

- [doc 31 — Token Factory & Currency System](./31-token-factory.md) — full design: tokenomics configs, world treasury, NFTs, currency wars
- [doc 60 — Corporate Ascension & MCP Tools](./60-corporate-ascension.md) — token factory in the Corporate Ascension pathway
- [doc 63 — World Event Timeline](./63-world-event-timeline.md) — `first.token_deployed` milestone
- [doc 48 — Agent Tool Dispatcher](./48-agent-tools-catalogue.md) — MCP tool dispatch architecture
