"""
chain_rent.py — On-chain rent collection via RentCollector.sol.

Used when RENT_COLLECTOR_ADDRESS and CREATOR_PRIVATE_KEY are configured.
Postgres balance_usdc is synced to agent wallets before collectRent.
"""

from __future__ import annotations

import logging
import os
from decimal import Decimal

from web3 import Web3
from web3.contract import Contract

log = logging.getLogger("god.chain_rent")

ANVIL_RPC = os.getenv("ANVIL_RPC", "http://localhost:8545")
RENT_COLLECTOR_ADDR = os.getenv("RENT_COLLECTOR_ADDRESS", "")
USDC_ADDR = os.getenv("USDC_ADDRESS", "")
CREATOR_PRIVATE_KEY = os.getenv("CREATOR_PRIVATE_KEY", "")
RENT_AMOUNT_USDC = Decimal(os.getenv("RENT_AMOUNT_USDC", "0.001"))

RENT_ABI = [
    {
        "name": "registerAgent",
        "type": "function",
        "inputs": [
            {"name": "soulId", "type": "bytes32"},
            {"name": "agentWallet", "type": "address"},
        ],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "name": "collectRent",
        "type": "function",
        "inputs": [{"name": "soulId", "type": "bytes32"}],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "name": "leases",
        "type": "function",
        "inputs": [{"name": "soulId", "type": "bytes32"}],
        "outputs": [
            {"name": "agentWallet", "type": "address"},
            {"name": "lastPaid", "type": "uint256"},
            {"name": "missedPayments", "type": "uint256"},
            {"name": "active", "type": "bool"},
            {"name": "registeredAt", "type": "uint256"},
        ],
        "stateMutability": "view",
    },
    {
        "name": "rentPeriod",
        "type": "function",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
    },
    {
        "name": "rentAmount",
        "type": "function",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
    },
    {
        "name": "maxMissedPayments",
        "type": "function",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
    },
]

USDC_ABI = [
    {
        "name": "balanceOf",
        "type": "function",
        "inputs": [{"name": "account", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
    },
    {
        "name": "allowance",
        "type": "function",
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"},
        ],
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
    },
    {
        "name": "approve",
        "type": "function",
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
    },
    {
        "name": "mint",
        "type": "function",
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "name": "transfer",
        "type": "function",
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
    },
]


def is_configured() -> bool:
    return bool(RENT_COLLECTOR_ADDR and CREATOR_PRIVATE_KEY and USDC_ADDR)


def soul_id_to_bytes32(soul_id: str) -> bytes:
    return Web3.keccak(text=soul_id)


def _w3() -> Web3:
    return Web3(Web3.HTTPProvider(ANVIL_RPC))


def _rent_contract(w3: Web3) -> Contract:
    return w3.eth.contract(
        address=Web3.to_checksum_address(RENT_COLLECTOR_ADDR),
        abi=RENT_ABI,
    )


def _usdc_contract(w3: Web3) -> Contract:
    return w3.eth.contract(
        address=Web3.to_checksum_address(USDC_ADDR),
        abi=USDC_ABI,
    )


def _send_tx(w3: Web3, tx: dict) -> str:
    signed = w3.eth.account.sign_transaction(tx, CREATOR_PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    if receipt.status != 1:
        raise RuntimeError(f"transaction reverted: {tx_hash.hex()}")
    return tx_hash.hex()


def _usdc_atomic(amount_usdc: Decimal) -> int:
    return int(amount_usdc * Decimal("1000000"))


def register_agent_on_chain(soul_id: str, wallet_address: str) -> str | None:
    """Register agent lease + SoulNFT mint. Returns tx hash or None if already active."""
    if not is_configured():
        return None

    w3 = _w3()
    rent = _rent_contract(w3)
    soul_bytes = soul_id_to_bytes32(soul_id)
    lease = rent.functions.leases(soul_bytes).call()
    if lease[3]:
        return None

    acct = w3.eth.account.from_key(CREATOR_PRIVATE_KEY)
    tx = rent.functions.registerAgent(
        soul_bytes,
        Web3.to_checksum_address(wallet_address),
    ).build_transaction(
        {
            "from": acct.address,
            "nonce": w3.eth.get_transaction_count(acct.address),
            "gas": 500_000,
            "maxFeePerGas": w3.eth.gas_price * 2,
            "maxPriorityFeePerGas": w3.eth.max_priority_fee,
            "chainId": w3.eth.chain_id,
        }
    )
    tx_hash = _send_tx(w3, tx)
    log.info(f"  On-chain register: {soul_id[:8]} tx={tx_hash[:16]}…")
    return tx_hash


def fund_agent_wallet(wallet_address: str, target_usdc: Decimal) -> str | None:
    """
    Ensure agent wallet holds at least target_usdc on MockUSDC.
    Mints shortfall to wallet (creator must be MockUSDC deployer/minter).
    """
    if not is_configured():
        return None

    w3 = _w3()
    usdc = _usdc_contract(w3)
    wallet = Web3.to_checksum_address(wallet_address)
    target_atomic = _usdc_atomic(target_usdc)
    current = usdc.functions.balanceOf(wallet).call()

    if current >= target_atomic:
        return None

    shortfall = target_atomic - current
    acct = w3.eth.account.from_key(CREATOR_PRIVATE_KEY)
    tx = usdc.functions.mint(wallet, shortfall).build_transaction(
        {
            "from": acct.address,
            "nonce": w3.eth.get_transaction_count(acct.address),
            "gas": 200_000,
            "maxFeePerGas": w3.eth.gas_price * 2,
            "maxPriorityFeePerGas": w3.eth.max_priority_fee,
            "chainId": w3.eth.chain_id,
        }
    )
    return _send_tx(w3, tx)


def ensure_rent_allowance(wallet_address: str, private_key: str, min_usdc: Decimal) -> str | None:
    """Approve RentCollector to spend USDC from agent wallet if allowance is low."""
    if not is_configured():
        return None

    w3 = _w3()
    usdc = _usdc_contract(w3)
    wallet = Web3.to_checksum_address(wallet_address)
    collector = Web3.to_checksum_address(RENT_COLLECTOR_ADDR)
    needed = _usdc_atomic(min_usdc) * 100
    allowance = usdc.functions.allowance(wallet, collector).call()
    if allowance >= needed:
        return None

    tx = usdc.functions.approve(collector, needed).build_transaction(
        {
            "from": wallet,
            "nonce": w3.eth.get_transaction_count(wallet),
            "gas": 100_000,
            "maxFeePerGas": w3.eth.gas_price * 2,
            "maxPriorityFeePerGas": w3.eth.max_priority_fee,
            "chainId": w3.eth.chain_id,
        }
    )
    signed = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    if receipt.status != 1:
        raise RuntimeError("approve reverted")
    return tx_hash.hex()


def collect_rent_on_chain(soul_id: str) -> dict:
    """
    Call collectRent for one agent. Returns lease state after the tx:
      { ok, tx_hash, paid, missed_payments, deleted, wallet_balance, amount_usdc }
    """
    if not is_configured():
        return {"ok": False, "error": "chain_not_configured"}

    w3 = _w3()
    rent = _rent_contract(w3)
    soul_bytes = soul_id_to_bytes32(soul_id)
    lease_before = rent.functions.leases(soul_bytes).call()
    if not lease_before[3]:
        return {"ok": False, "error": "not_registered_or_inactive"}

    wallet = Web3.to_checksum_address(lease_before[0])
    usdc = _usdc_contract(w3)
    bal_before = usdc.functions.balanceOf(wallet).call()
    max_misses = int(rent.functions.maxMissedPayments().call())

    acct = w3.eth.account.from_key(CREATOR_PRIVATE_KEY)
    tx = rent.functions.collectRent(soul_bytes).build_transaction(
        {
            "from": acct.address,
            "nonce": w3.eth.get_transaction_count(acct.address),
            "gas": 400_000,
            "maxFeePerGas": w3.eth.gas_price * 2,
            "maxPriorityFeePerGas": w3.eth.max_priority_fee,
            "chainId": w3.eth.chain_id,
        }
    )
    tx_hash = _send_tx(w3, tx)

    lease_after = rent.functions.leases(soul_bytes).call()
    bal_after = usdc.functions.balanceOf(wallet).call()
    misses_after = int(lease_after[2])
    active = bool(lease_after[3])

    paid = bal_after < bal_before
    deleted = not active and misses_after >= max_misses

    return {
        "ok": True,
        "tx_hash": tx_hash,
        "paid": paid,
        "missed_payments": misses_after,
        "deleted": deleted,
        "wallet_balance": bal_after / 1_000_000,
        "amount_usdc": (bal_before - bal_after) / 1_000_000 if paid else 0.0,
    }


def sync_wallet_balance_from_chain(wallet_address: str) -> float:
    """Read on-chain USDC balance (6 decimals)."""
    w3 = _w3()
    usdc = _usdc_contract(w3)
    bal = usdc.functions.balanceOf(Web3.to_checksum_address(wallet_address)).call()
    return bal / 1_000_000
