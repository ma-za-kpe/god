"""
token_factory.py — Deploy ERC-20 tokens on behalf of agents.

Phase 1: deploys to Anvil local chain (ANVIL_RPC).
Phase 2+: set ANVIL_RPC to Base Sepolia / Base mainnet RPC — same code path.

Prerequisites:
  forge build   (in contracts/ — generates out/AgentToken.sol/AgentToken.json)
  web3>=6.15.0  (in runtime/requirements.txt)

Deployment fee: TOKEN_DEPLOY_FEE_USDC (default 1.0 USDC) deducted from agent balance.
"""

import json
import logging
import os
import time

import psycopg2
import psycopg2.extras

log = logging.getLogger("god.token_factory")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID = os.getenv("WORLD_ID", "local-dev-world-1")
ANVIL_RPC = os.getenv("ANVIL_RPC", "http://anvil:8545")
TOKEN_DEPLOY_FEE_USDC = float(os.getenv("TOKEN_DEPLOY_FEE_USDC", "1.0"))

# Foundry artifact — populated after `forge build`
ARTIFACT_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "contracts",
    "out",
    "AgentToken.sol",
    "AgentToken.json",
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


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

    Steps:
      1. Balance check
      2. Input validation
      3. Load Foundry artifact
      4. Deploy via web3
      5. Deduct fee
      6. Persist to DB
      7. Emit event + NATS

    Returns token record dict.
    """
    log.info(
        f"TOKEN DEPLOY: soul={soul_id[:8]} name={name!r} symbol={symbol!r} "
        f"supply={initial_supply:,} tax_bps={transfer_tax_bps} "
        f"fee={TOKEN_DEPLOY_FEE_USDC} USDC"
    )

    # 1. Balance check
    balance = _get_agent_balance(soul_id)
    log.debug(f"  [{soul_id[:8]}] balance: {balance:.6f} USDC  needed: {TOKEN_DEPLOY_FEE_USDC}")
    if balance < TOKEN_DEPLOY_FEE_USDC:
        log.warning(
            f"  [{soul_id[:8]}] insufficient balance: {balance:.6f} < {TOKEN_DEPLOY_FEE_USDC}"
        )
        raise ValueError(
            f"Insufficient balance: {balance:.4f} USDC. "
            f"Token deployment costs {TOKEN_DEPLOY_FEE_USDC} USDC."
        )

    # 2. Input validation
    if not name or len(name) > 64:
        raise ValueError("Token name must be 1–64 characters.")
    if not symbol or len(symbol) > 10:
        raise ValueError("Token symbol must be 1–10 characters.")
    if initial_supply <= 0:
        raise ValueError("Initial supply must be positive.")
    if initial_supply > 1_000_000_000:
        raise ValueError("Initial supply cannot exceed 1 billion tokens.")
    if transfer_tax_bps < 0 or transfer_tax_bps > 1000:
        raise ValueError("Transfer tax must be 0–1000 bps (0%–10%).")
    log.debug(f"  [{soul_id[:8]}] input validation passed")

    # 3. Load artifact
    log.debug(f"  [{soul_id[:8]}] loading artifact from {ARTIFACT_PATH}")
    bytecode, abi = _load_artifact()
    log.debug(f"  [{soul_id[:8]}] artifact loaded, bytecode length={len(bytecode)}")

    # 4. Reserve deployment fee before the external chain side effect.
    _deduct_balance(soul_id, TOKEN_DEPLOY_FEE_USDC)
    fee_reserved = True
    log.debug(f"  [{soul_id[:8]}] fee reserved: -{TOKEN_DEPLOY_FEE_USDC} USDC")

    try:
        # 5. Deploy
        log.debug(f"  [{soul_id[:8]}] connecting to chain at {ANVIL_RPC}")
        w3 = _get_web3()
        chain_id = w3.eth.chain_id
        block = w3.eth.block_number
        log.debug(f"  [{soul_id[:8]}] chain_id={chain_id} block={block}")

        account = w3.eth.account.from_key(wallet_private_key)
        log.debug(f"  [{soul_id[:8]}] deploying from {account.address}")

        Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
        supply_in_wei = initial_supply * (10**decimals)

        log.debug(
            f"  [{soul_id[:8]}] building tx: supply_wei={supply_in_wei} "
            f"tax_recipient={tax_recipient}"
        )
        tx = Contract.constructor(
            name,
            symbol,
            decimals,
            supply_in_wei,
            transfer_tax_bps,
            w3.to_checksum_address(tax_recipient),
            w3.to_checksum_address(wallet_address),
        ).build_transaction(
            {
                "from": account.address,
                "nonce": w3.eth.get_transaction_count(account.address),
                "gas": 3_000_000,
                "gasPrice": w3.to_wei("1", "gwei"),
            }
        )
        log.debug(f"  [{soul_id[:8]}] tx built: gas={tx['gas']} gasPrice={tx['gasPrice']}")

        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        log.info(f"  [{soul_id[:8]}] tx sent: {tx_hash.hex()}")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        log.debug(
            f"  [{soul_id[:8]}] receipt: status={receipt['status']} "
            f"gasUsed={receipt['gasUsed']} block={receipt['blockNumber']}"
        )

        if receipt["status"] != 1:
            log.error(f"  [{soul_id[:8]}] deployment REVERTED: tx={tx_hash.hex()}")
            raise RuntimeError(f"Token deployment reverted. tx={tx_hash.hex()}")

        contract_address = receipt["contractAddress"]
        tx_hash_hex = tx_hash.hex()
        log.info(
            f"  [{soul_id[:8]}] contract deployed at {contract_address} tx={tx_hash_hex[:16]}…"
        )

    except Exception as e:
        if fee_reserved:
            _refund_balance(soul_id, TOKEN_DEPLOY_FEE_USDC)
            fee_reserved = False
        log.error(
            f"TOKEN DEPLOY FAILED: soul={soul_id[:8]} name={name!r}: {e}",
            exc_info=True,
        )
        raise

    # 6. Persist
    now = int(time.time())
    _persist_token(contract_address, soul_id, name, symbol, initial_supply, now, tx_hash_hex)
    log.debug(f"  [{soul_id[:8]}] token persisted to DB")

    # 7. Emit event
    from .event_emitter import get_emitter

    emitter = await get_emitter()
    await emitter.emit(
        "economy",
        "token.deployed",
        {
            "agent_id": soul_id,
            "contract_address": contract_address,
            "name": name,
            "symbol": symbol,
            "initial_supply": initial_supply,
            "tx_hash": tx_hash_hex,
            "narrative": (
                f"{soul_id[:8]} launches ${symbol} — {name} "
                f"with {initial_supply:,} tokens at {contract_address[:10]}…"
            ),
        },
    )

    log.info(
        f"TOKEN DEPLOYED: ${symbol} ({name}) at {contract_address} "
        f"by {soul_id[:8]} tx={tx_hash_hex[:16]}…"
    )

    return {
        "contract_address": contract_address,
        "name": name,
        "symbol": symbol,
        "initial_supply": initial_supply,
        "decimals": decimals,
        "transfer_tax_bps": transfer_tax_bps,
        "tx_hash": tx_hash_hex,
        "deployed_at": now,
        "deploy_fee_paid": TOKEN_DEPLOY_FEE_USDC,
        "chain_id": chain_id,
    }


def get_agent_tokens(soul_id: str) -> list[dict]:
    """Return all tokens deployed by this agent, newest first."""
    log.debug(f"get_agent_tokens: {soul_id[:8]}")
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM tokens WHERE owner_soul_id = %s ORDER BY deployed_at DESC",
            (soul_id,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        log.debug(f"  [{soul_id[:8]}] found {len(rows)} tokens")
        return rows
    except Exception as e:
        log.debug(f"get_agent_tokens failed: {e}")
        return []


def get_world_tokens() -> list[dict]:
    """Return all tokens ever deployed in this world, newest first."""
    log.debug("get_world_tokens")
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT t.*, a.current_name AS owner_name
            FROM tokens t
            JOIN agents a ON t.owner_soul_id = a.soul_id
            WHERE t.world_id = %s
            ORDER BY t.deployed_at DESC
            """,
            (WORLD_ID,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        log.debug(f"get_world_tokens: {len(rows)} total")
        return rows
    except Exception as e:
        log.debug(f"get_world_tokens failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_artifact() -> tuple[str, list]:
    """Load compiled contract bytecode and ABI from Foundry artifact."""
    try:
        with open(ARTIFACT_PATH) as f:
            artifact = json.load(f)
        bytecode = artifact["bytecode"]["object"]
        abi = artifact["abi"]
        if not bytecode.startswith("0x"):
            bytecode = "0x" + bytecode
        log.debug(f"_load_artifact: ABI has {len(abi)} entries")
        return bytecode, abi
    except FileNotFoundError:
        log.error(
            f"AgentToken artifact not found at {ARTIFACT_PATH}. Run: forge build (in contracts/)"
        )
        raise RuntimeError(
            "AgentToken artifact not found. "
            "Run `forge build` inside the contracts/ directory first."
        )
    except (KeyError, json.JSONDecodeError) as e:
        log.error(f"_load_artifact: malformed artifact: {e}")
        raise RuntimeError(f"AgentToken artifact is malformed: {e}")


def _get_web3():
    """Return a connected Web3 instance. Raises if chain is unreachable."""
    try:
        from web3 import Web3
    except ImportError:
        log.error("web3 package not installed — run: pip install web3>=6.15.0")
        raise RuntimeError("web3 not installed. Add web3>=6.15.0 to requirements.txt.")

    w3 = Web3(Web3.HTTPProvider(ANVIL_RPC))
    if not w3.is_connected():
        log.error(f"_get_web3: cannot connect to chain at {ANVIL_RPC}")
        raise RuntimeError(f"Cannot connect to chain at {ANVIL_RPC}")
    return w3


def _get_agent_balance(soul_id: str) -> float:
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(balance_usdc, 0) AS bal FROM agents WHERE soul_id = %s",
        (soul_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return float(row["bal"]) if row else 0.0


def _deduct_balance(soul_id: str, amount: float):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE agents
            SET balance_usdc = COALESCE(balance_usdc, 0) - %s
            WHERE soul_id = %s
              AND is_alive = true
              AND COALESCE(balance_usdc, 0) >= %s
            RETURNING balance_usdc
            """,
            (amount, soul_id, amount),
        )
        if not cur.fetchone():
            conn.rollback()
            raise ValueError(f"Insufficient balance: token deployment costs {amount:.4f} USDC.")
        conn.commit()
    finally:
        cur.close()
        conn.close()


def _refund_balance(soul_id: str, amount: float):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE agents SET balance_usdc = COALESCE(balance_usdc, 0) + %s WHERE soul_id = %s",
            (amount, soul_id),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def _persist_token(
    contract_address: str,
    soul_id: str,
    name: str,
    symbol: str,
    initial_supply: int,
    now: int,
    tx_hash: str,
):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO tokens
                (contract_address, owner_soul_id, name, symbol,
                 initial_supply, deployed_at, on_chain_tx, world_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (contract_address) DO NOTHING
            """,
            (contract_address, soul_id, name, symbol, initial_supply, now, tx_hash, WORLD_ID),
        )
        conn.commit()
        cur.close()
        conn.close()
        log.debug(f"_persist_token: {contract_address[:10]}… persisted for {soul_id[:8]}")
    except Exception as e:
        log.error(f"_persist_token failed: {e}", exc_info=True)
        raise
