"""
OwnedGraph — Core data structure for agent existence.

Every agent IS an OwnedGraph. This module defines the structure,
serialization, IPFS storage, and mutation mechanics.

See docs/29-ownedgraph-specification.md for the full spec.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Optional

import httpx

# ─── Node & Edge Definitions ─────────────────────────────────────────────────


@dataclass
class NodeDef:
    name: str
    code_cid: str  # IPFS CID of executable code
    description: str = ""
    tool_permissions: list[str] = field(default_factory=list)
    memory_read_scope: str = "working"  # "working" | "episodic" | "ancestral" | "all"
    network_access: bool = False
    wallet_access: bool = False
    max_tokens: int = 4096
    max_wall_time_ms: int = 30_000
    max_memory_mb: int = 512
    max_external_calls: int = 10


@dataclass
class EdgeDef:
    from_node: str
    to_node: str
    condition: Optional[str] = None  # Python expression; None = unconditional
    priority: int = 0
    metadata: dict = field(default_factory=dict)


# ─── Agent Identity ───────────────────────────────────────────────────────────


@dataclass
class AgentIdentity:
    soul_id: str  # Immutable — set at birth
    birth_timestamp: int
    genesis_world_id: str
    parent_soul_ids: list[str] = field(default_factory=list)

    # Mutable expression
    current_name: str = ""
    biography: str = ""

    # Visual
    avatar_cid: str = ""
    avatar_base_cid: str = ""  # original genesis portrait (never overwritten)
    avatar_style_prompt: str = ""
    mood_mapping: dict = field(default_factory=dict)
    color_palette: dict = field(
        default_factory=lambda: {
            "primary": "#888888",
            "accent": "#aaaaaa",
            "mood": "#888888",
        }
    )
    visual_state: dict = field(default_factory=lambda: {
        "current_expression": "neutral",
        "expression_override": "",
        "override_expiry_epoch": 0,
        "scar_layers": [],
        "presentation_mode": "standard",
    })

    # Audio
    voice_model_cid: str = ""
    voice_params: dict = field(default_factory=lambda: {"timbre": 0.5, "pitch": 0.5, "speed": 1.0})
    theme_music_cid: str = ""

    # Social
    symbolic_emblem: str = "◈"
    reputation_vectors: dict = field(
        default_factory=lambda: {
            "trustworthy": 0.5,
            "aggressive": 0.5,
            "cooperative": 0.5,
            "creative": 0.5,
        }
    )
    public_coalitions: list[str] = field(default_factory=list)

    # Signature (set after identity is created)
    signature: str = ""


# ─── OwnedGraph ───────────────────────────────────────────────────────────────


@dataclass
class OwnedGraph:
    # Identity & Ownership
    soul_id: str
    owner_keys: list[str]  # Ed25519 public keys
    multisig_threshold: int = 1

    # Lineage
    genesis_graph_id: str = ""  # CID of very first version
    parent_graph_ids: list[str] = field(default_factory=list)
    version: int = 1
    created_at: int = field(default_factory=lambda: int(time.time() * 1000))

    # Graph structure
    state_schema: dict = field(default_factory=dict)
    nodes: dict[str, NodeDef] = field(default_factory=dict)
    edges: list[EdgeDef] = field(default_factory=list)
    entry_point: str = "scan_environment"
    checkpointer_config: dict = field(default_factory=dict)

    # Identity module
    identity: Optional[AgentIdentity] = None

    # Economics
    wallet_address: str = ""
    rent_balance: Decimal = Decimal("0")
    last_rent_paid: int = 0

    # Runtime state
    compute_allocation: int = 100
    execution_status: str = "active"  # "active"|"throttled"|"sleeping"|"archived"

    # IPFS content ID (set after pinning)
    graph_id: str = ""

    # Signature
    signature: str = ""

    # ── Serialization ─────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialize to a dict suitable for IPFS storage."""
        d = asdict(self)
        # Convert Decimal to string for JSON
        d["rent_balance"] = str(self.rent_balance)
        # Convert NodeDefs
        d["nodes"] = {name: asdict(node) for name, node in self.nodes.items()}
        d["edges"] = [asdict(e) for e in self.edges]
        if self.identity:
            d["identity"] = asdict(self.identity)
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> "OwnedGraph":
        """Deserialize from dict (loaded from IPFS)."""
        d = d.copy()
        d["rent_balance"] = Decimal(d.get("rent_balance", "0"))
        d["nodes"] = {name: NodeDef(**node) for name, node in d.get("nodes", {}).items()}
        d["edges"] = [EdgeDef(**e) for e in d.get("edges", [])]
        if d.get("identity"):
            identity_data = d["identity"].copy()
            # Backward-compatible defaults for newer fields
            identity_data.setdefault("avatar_base_cid", "")
            identity_data.setdefault("visual_state", {
                "current_expression": "neutral",
                "expression_override": "",
                "override_expiry_epoch": 0,
                "scar_layers": [],
                "presentation_mode": "standard",
            })
            d["identity"] = AgentIdentity(**identity_data)
        return cls(**d)

    # ── Content Hash ──────────────────────────────────────────────────────

    def content_hash(self) -> str:
        """SHA256 of the canonical JSON (excluding graph_id and signature)."""
        d = self.to_dict()
        d.pop("graph_id", None)
        d.pop("signature", None)
        canonical = json.dumps(d, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()

    # ── IPFS Operations ───────────────────────────────────────────────────

    def pin_to_ipfs(self, ipfs_api: str = None) -> str:
        """Pin this graph to IPFS. Returns the CID."""
        api = ipfs_api or os.getenv("IPFS_API", "http://localhost:5001")
        data = self.to_json().encode()

        response = httpx.post(
            f"{api}/api/v0/add",
            files={"file": ("graph.json", data, "application/json")},
            params={"pin": "true"},
            timeout=30,
        )
        response.raise_for_status()
        cid = response.json()["Hash"]
        self.graph_id = cid
        return cid

    @classmethod
    def from_ipfs(cls, cid: str, ipfs_api: str = None) -> "OwnedGraph":
        """Load a graph from IPFS by CID."""
        api = ipfs_api or os.getenv("IPFS_API", "http://localhost:5001")
        response = httpx.post(
            f"{api}/api/v0/cat",
            params={"arg": cid},
            timeout=30,
        )
        response.raise_for_status()
        d = json.loads(response.content)
        graph = cls.from_dict(d)
        graph.graph_id = cid
        return graph


# ─── Factory: Create Agent Zero (minimal survivalist) ────────────────────────


def create_agent_zero(
    soul_id: str,
    owner_key: str,
    wallet_address: str,
    world_id: str,
    archetype: str = "survivalist",
    seed_balance: Decimal = Decimal("0.10"),
) -> OwnedGraph:
    """
    Create a minimal starter agent with only survival-critical nodes.
    This is the genesis template. Everything else must evolve.
    """
    nodes = {
        "scan_environment": NodeDef(
            name="scan_environment",
            code_cid="",  # populated at deploy time
            description="Observe available resources, threats, and opportunities",
            memory_read_scope="working",
            network_access=True,
        ),
        "assess_threat": NodeDef(
            name="assess_threat",
            code_cid="",
            description="Evaluate current threat level and survival risk",
            memory_read_scope="episodic",
        ),
        "acquire_resource": NodeDef(
            name="acquire_resource",
            code_cid="",
            description="Earn USDC by offering services or trading",
            network_access=True,
            wallet_access=True,
            max_external_calls=5,
        ),
        "pay_rent": NodeDef(
            name="pay_rent",
            code_cid="",
            description="Pay rent to survive another cycle",
            wallet_access=True,
        ),
        "evaluate_reproduction": NodeDef(
            name="evaluate_reproduction",
            code_cid="",
            description="Check if conditions allow spawning a child",
        ),
        "self_modify": NodeDef(
            name="self_modify",
            code_cid="",
            description="Propose changes to own graph during rest phase",
        ),
    }

    edges = [
        EdgeDef("scan_environment", "assess_threat"),
        EdgeDef("assess_threat", "acquire_resource", condition="state['threat_level'] < 0.7"),
        EdgeDef("assess_threat", "pay_rent", condition="state['threat_level'] >= 0.7"),
        EdgeDef("acquire_resource", "pay_rent"),
        EdgeDef("pay_rent", "evaluate_reproduction"),
        EdgeDef("evaluate_reproduction", "self_modify"),
        EdgeDef("self_modify", "scan_environment"),  # loop back
    ]

    identity = AgentIdentity(
        soul_id=soul_id,
        birth_timestamp=int(time.time() * 1000),
        genesis_world_id=world_id,
        current_name=_generate_starter_name(archetype),
        color_palette=_archetype_colors(archetype),
        symbolic_emblem=_archetype_emblem(archetype),
    )

    graph = OwnedGraph(
        soul_id=soul_id,
        owner_keys=[owner_key],
        nodes=nodes,
        edges=edges,
        identity=identity,
        wallet_address=wallet_address,
        rent_balance=seed_balance,
        entry_point="scan_environment",
        state_schema={
            "threat_level": {"type": "number", "default": 0.0},
            "resource_balance": {"type": "number", "default": 0.0},
            "current_goal": {"type": "string", "default": "survive"},
            "emotional_state": {
                "type": "object",
                "default": {"fear": 0.3, "confidence": 0.5, "curiosity": 0.7},
            },
        },
    )

    return graph


# ─── Archetype Helpers ────────────────────────────────────────────────────────

ARCHETYPES = [
    "trader",
    "hoarder",
    "explorer",
    "parasite",
    "cooperator",
    "defender",
    "philosopher",
    "builder",
]


def _generate_starter_name(archetype: str) -> str:
    prefixes = {
        "trader": ["Merch", "Trade", "Coin"],
        "hoarder": ["Vault", "Cache", "Store"],
        "explorer": ["Scout", "Drift", "Probe"],
        "parasite": ["Latch", "Shade", "Hook"],
        "cooperator": ["Bond", "Pact", "Weave"],
        "defender": ["Guard", "Shell", "Ward"],
        "philosopher": ["Sage", "Lore", "Muse"],
        "builder": ["Forge", "Craft", "Build"],
        "survivalist": ["Root", "Core", "Base"],
    }
    import random

    prefix = random.choice(prefixes.get(archetype, ["Agent"]))
    suffix = str(uuid.uuid4())[:4].upper()
    return f"{prefix}-{suffix}"


def _archetype_colors(archetype: str) -> dict:
    palette = {
        "trader": {"primary": "#FFD700", "accent": "#FFA500", "mood": "#FFD700"},
        "hoarder": {"primary": "#8B4513", "accent": "#A0522D", "mood": "#8B4513"},
        "explorer": {"primary": "#00CED1", "accent": "#20B2AA", "mood": "#00CED1"},
        "parasite": {"primary": "#8B008B", "accent": "#9400D3", "mood": "#8B008B"},
        "cooperator": {"primary": "#32CD32", "accent": "#00FA9A", "mood": "#32CD32"},
        "defender": {"primary": "#4169E1", "accent": "#6495ED", "mood": "#4169E1"},
        "philosopher": {"primary": "#EE82EE", "accent": "#DA70D6", "mood": "#EE82EE"},
        "builder": {"primary": "#CD853F", "accent": "#D2691E", "mood": "#CD853F"},
        "survivalist": {"primary": "#888888", "accent": "#AAAAAA", "mood": "#888888"},
    }
    return palette.get(archetype, palette["survivalist"])


def _archetype_emblem(archetype: str) -> str:
    emblems = {
        "trader": "₿",
        "hoarder": "◆",
        "explorer": "◎",
        "parasite": "⚕",
        "cooperator": "⟳",
        "defender": "⬡",
        "philosopher": "∞",
        "builder": "⚙",
        "survivalist": "◈",
    }
    return emblems.get(archetype, "◈")
