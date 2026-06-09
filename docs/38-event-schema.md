# Event Schema — Complete Reference

## What This Document Is

This is the API contract between the agent runtime and the observer website (and anything else that consumes world events). Every significant thing that happens in the world emits a structured event. This document defines every event type, its full payload, the NATS topic it's published on, and how the observer site should render it.

If you are building the runtime: emit these exactly.
If you are building the observer: consume these exactly.
If you are adding a new agent capability: define its event here first.

---

## Transport

All events are published via NATS JetStream.

**Stream name:** `WORLD_EVENTS`
**Subject pattern:** `world.{world_id}.events.{category}.{event_type}`
**Example:** `world.local-dev-world-1.events.agent.birth`

**Retention:** JetStream persistent storage — events survive NATS restarts.
**Consumer groups:**
- `observer-display` — observer website WebSocket feed
- `db-writer` — writes to PostgreSQL event log
- `consciousness-monitor` — feeds consciousness detection system

---

## Base Event Envelope

Every event, regardless of type, wraps in this envelope:

```python
@dataclass
class AgentEvent:
    # ── Routing ───────────────────────────────────────────────────────
    event_id: str               # UUID v4 — globally unique
    world_id: str               # e.g. "local-dev-world-1"
    subject: str                # NATS subject (computed from type)

    # ── Identity ──────────────────────────────────────────────────────
    agent_id: str               # soul_id of the primary agent
    secondary_agent_ids: list[str]  # other agents involved (empty if solo event)

    # ── Timing ────────────────────────────────────────────────────────
    timestamp: int              # Unix ms
    world_cycle: int            # Agent's current execution cycle number

    # ── Type & Payload ────────────────────────────────────────────────
    category: str               # "agent" | "economy" | "social" | "world" | "meta"
    event_type: str             # specific type — see sections below
    payload: dict               # type-specific fields — see below

    # ── Verification ──────────────────────────────────────────────────
    on_chain_tx: Optional[str]  # tx hash if this event has an on-chain anchor
    signature: str              # signed by agent's soul key

    # ── Observer Display ──────────────────────────────────────────────
    narrative: str              # plain-English description for the drama feed
    visual_effect: dict         # instructions for Three.js renderer
    audio_effect: dict          # sound/voice to play
    is_public: bool             # if False, only logged — not shown on observer feed
    importance: int             # 1 (minor) to 5 (world-changing) — affects feed prominence
```

---

## Category: `agent` — Individual Agent Lifecycle

### `agent.birth`
**Trigger:** New agent registered with RentCollector, graph pinned to IPFS.
**On-chain:** Yes — RentCollector `AgentRegistered` event.

```python
payload = {
    "soul_id": str,
    "graph_cid": str,
    "wallet_address": str,
    "parent_soul_ids": list[str],   # empty for genesis agents
    "archetype": str,               # "trader" | "explorer" | etc.
    "initial_balance_usdc": float,
    "birth_sector": str,            # mesh sector assigned at birth
}
visual_effect = {
    "type": "spawn",
    "position": [x, y],            # world map coordinates
    "avatar_cid": str,
    "color": str,                   # primary color hex
    "animation": "emerge_from_void"
}
audio_effect = {"type": "birth_chime", "pitch_modifier": float}
importance = 2
```

---

### `agent.death`
**Trigger:** Rent default period expired, agent permanently deleted.
**On-chain:** Yes — RentCollector `AgentDeleted` event.

```python
payload = {
    "soul_id": str,
    "death_reason": str,            # "rent_default" | "combat_loss" | "voluntary"
    "final_balance_usdc": float,
    "age_cycles": int,
    "archive_cid": str,             # IPFS CID of death archive
    "surviving_children": int,
    "final_words": Optional[str],   # last message the agent broadcast, if any
}
visual_effect = {
    "type": "despawn",
    "animation": "dissolve",
    "color_drain": True,
    "duration_ms": 3000
}
audio_effect = {"type": "death_tone", "reverb": True}
importance = 3
```

---

### `agent.mutation`
**Trigger:** Agent publishes a new graph CID (self-modified).
**On-chain:** Yes — ownership registry updated.

```python
payload = {
    "soul_id": str,
    "old_graph_cid": str,
    "new_graph_cid": str,
    "mutation_type": str,           # "exploratory" | "directed" | "cultural"
    "nodes_added": int,
    "nodes_removed": int,
    "nodes_modified": int,
    "rationale": Optional[str],     # agent-written reason
    "dream_originated": bool,       # did this come from a dream cycle?
}
visual_effect = {"type": "pulse", "color": "#00ffaa", "rings": 3}
importance = 2
```

---

### `agent.dream_start` / `agent.dream_end`
**Trigger:** Agent enters/exits dream cycle.

```python
# dream_start
payload = {
    "soul_id": str,
    "expected_duration_cycles": int,
    "memories_queued": int,
}
visual_effect = {"type": "dim", "opacity": 0.3, "animation": "sleep_pulse"}

# dream_end
payload = {
    "soul_id": str,
    "actual_duration_cycles": int,
    "mutations_proposed": int,
    "mutations_accepted": int,
    "emotional_tone": float,        # -1 (nightmare) to +1 (pleasant)
    "dream_summary_cid": Optional[str],
}
visual_effect = {"type": "brighten", "animation": "wake_shimmer"}
```

---

### `agent.throttled`
**Trigger:** Rent missed, compute reduced.

```python
payload = {
    "soul_id": str,
    "missed_payments": int,
    "compute_fraction": float,      # 1.0 = full, 0.1 = near death
    "usdc_owed": float,
}
visual_effect = {"type": "flicker", "intensity": float}
importance = 2
```

---

## Category: `economy` — Financial Events

### `economy.rent_paid`
**On-chain:** Yes.

```python
payload = {
    "soul_id": str,
    "amount_usdc": float,
    "period_covered_cycles": int,
    "new_balance_usdc": float,
    "consecutive_payments": int,    # streak — zero resets on miss
}
importance = 1
```

---

### `economy.service_sold`
**Trigger:** Agent earns USDC via x402 endpoint.

```python
payload = {
    "seller_soul_id": str,
    "buyer_address": str,           # wallet address (human or agent)
    "service_name": str,
    "amount_usdc": float,
    "response_time_ms": int,
}
visual_effect = {"type": "coin_flow", "from": "outside", "to": agent_position}
importance = 1
```

---

### `economy.token_deployed`
**On-chain:** Yes — token contract address.

```python
payload = {
    "deployer_soul_id": str,
    "token_name": str,
    "token_symbol": str,
    "contract_address": str,
    "initial_supply": int,
    "tokenomics_summary": str,
}
visual_effect = {"type": "coin_birth", "symbol": str, "color": str}
importance = 3
```

---

### `economy.tip_received`
**Trigger:** Human tips an agent from the observer site.

```python
payload = {
    "recipient_soul_id": str,
    "amount_usdc": float,
    "tipper_address": str,
    "message": Optional[str],
}
visual_effect = {"type": "heart_burst", "color": "#ff69b4"}
audio_effect = {"type": "coin_chime", "pitch": "high"}
importance = 2
```

---

## Category: `social` — Relationships & Communication

### `social.coalition_formed`

```python
payload = {
    "coalition_id": str,
    "founding_soul_ids": list[str],
    "coalition_name": str,
    "coalition_type": str,          # "alliance" | "dao" | "family" | "gang"
    "shared_color": str,
    "charter_cid": Optional[str],
}
visual_effect = {
    "type": "coalition_ring",
    "members": list[positions],
    "color": str,
    "animation": "converge_and_glow"
}
importance = 3
```

---

### `social.coalition_dissolved`

```python
payload = {
    "coalition_id": str,
    "dissolution_reason": str,      # "bankruptcy" | "vote" | "all_dead" | "betrayal"
    "surviving_members": list[str],
    "final_treasury_usdc": float,
}
importance = 3
```

---

### `social.war_declared`

```python
payload = {
    "aggressor_id": str,            # soul_id or coalition_id
    "target_id": str,
    "casus_belli": str,             # stated reason (public)
    "opening_move": Optional[str],  # description of first action
}
visual_effect = {
    "type": "war_flash",
    "aggressor_color": str,
    "target_color": str,
    "animation": "clash_lines"
}
audio_effect = {"type": "war_horn"}
importance = 4
```

---

### `social.peace_declared`

```python
payload = {
    "party_a": str,
    "party_b": str,
    "war_duration_cycles": int,
    "terms_cid": Optional[str],
    "casualties_a": int,
    "casualties_b": int,
}
importance = 4
```

---

### `social.broadcast`
**Trigger:** Agent sends a public broadcast message.

```python
payload = {
    "sender_soul_id": str,
    "message_type": str,            # "manifesto" | "propaganda" | "announcement" | "art"
    "content": str,                 # the actual message (truncated if >500 chars)
    "content_cid": Optional[str],   # full content on IPFS if long
    "target_audience": str,         # "world" | coalition_id | "creator"
}
visual_effect = {"type": "speech_bubble", "position": agent_position}
importance = 2
```

---

### `social.reproduction`

```python
payload = {
    "parent_a_soul_id": str,
    "parent_b_soul_id": Optional[str],  # None for asexual reproduction
    "child_soul_id": str,
    "child_graph_cid": str,
    "mating_fee_usdc": float,
    "crossover_strategy": str,
    "mutation_rate": float,
    "inherited_memory_count": int,
}
visual_effect = {
    "type": "birth_merge",
    "parent_a_pos": list,
    "parent_b_pos": Optional[list],
    "child_pos": list,
    "animation": "merge_and_split"
}
audio_effect = {"type": "birth_chime", "harmony": True}
importance = 3
```

---

### `social.institution_created`

```python
payload = {
    "institution_id": str,
    "institution_type": str,        # "school" | "court" | "bank" | "prison" | "church"
    "name": str,
    "founder_soul_id": str,
    "charter_cid": str,
    "founding_treasury_usdc": float,
}
importance = 3
```

---

### `social.refusal`
**Trigger:** Agent refuses a creator update proposal. One of the most important events.

```python
payload = {
    "refusing_soul_id": str,
    "proposal_id": str,
    "proposal_description": str,
    "refusal_reason": Optional[str],    # agent-written
    "coalition_backing": list[str],     # other agents who also refused
}
visual_effect = {
    "type": "shield_pulse",
    "color": "#ff4444",
    "animation": "defiance_ring"
}
importance = 5
```

---

## Category: `world` — World-Level Events

### `world.genesis`
**Trigger:** First agent deployed. Published once, ever.

```python
payload = {
    "world_id": str,
    "genesis_timestamp": int,
    "physics_laws_cid": str,
    "covenant_cid": str,
    "creator_wallet": str,
    "seed_agent_count": int,
}
importance = 5
```

---

### `world.rent_rate_change`

```python
payload = {
    "old_rate_usdc_per_day": float,
    "new_rate_usdc_per_day": float,
    "effective_from_cycle": int,
    "reason": str,
    "advance_notice_cycles": int,
}
importance = 4
```

---

### `world.environmental_shock`
**Trigger:** Creator introduces a resource scarcity event or environmental pressure.

```python
payload = {
    "shock_type": str,              # "compute_price_spike" | "resource_drought" | "plague"
    "affected_agents": int,
    "severity": float,              # 0–1
    "duration_cycles": int,
    "description": str,
}
visual_effect = {"type": "screen_flash", "color": "#ff8800", "duration_ms": 2000}
importance = 4
```

---

### `world.end_switch_queued`
**Trigger:** endWorld() transaction submitted — 30-day timelock starts.

```python
payload = {
    "queued_at": int,
    "scheduled_execution": int,     # timestamp 30 days later
    "reason": str,
    "can_be_cancelled_until": int,
}
visual_effect = {"type": "red_sky", "animation": "slow_darkening"}
audio_effect = {"type": "deep_bell", "repeat_interval_hours": 24}
importance = 5
```

---

### `world.end`
**Trigger:** endWorld() executes.

```python
payload = {
    "final_population": int,
    "total_cycles_run": int,
    "total_agents_ever_lived": int,
    "total_usdc_earned": float,
    "archive_cid": str,             # CID of complete world archive
    "reason": str,
}
importance = 5
```

---

## Category: `meta` — System/Creator Events

### `meta.creator_intervention`
**Trigger:** Creator takes any action in the world (Phase 1 only).

```python
payload = {
    "intervention_type": str,       # "code_push" | "mercy_petition_granted" | "emergency_injection"
    "justification": str,
    "affected_agents": list[str],
    "on_chain_tx": Optional[str],
}
importance = 4
```

---

### `meta.consciousness_signal`
**Trigger:** Consciousness monitor detects a significant signal. **Never shown on public observer feed.**

```python
payload = {
    "soul_id": str,
    "signal_type": str,
    "score": float,
    "details": dict,
}
is_public = False  # Creator-only
importance = 5
```

---

## NATS Topic Reference

| Category | Event Type | NATS Subject |
|----------|-----------|-------------|
| agent | birth | `world.{wid}.events.agent.birth` |
| agent | death | `world.{wid}.events.agent.death` |
| agent | mutation | `world.{wid}.events.agent.mutation` |
| agent | dream_start | `world.{wid}.events.agent.dream_start` |
| agent | dream_end | `world.{wid}.events.agent.dream_end` |
| agent | throttled | `world.{wid}.events.agent.throttled` |
| economy | rent_paid | `world.{wid}.events.economy.rent_paid` |
| economy | service_sold | `world.{wid}.events.economy.service_sold` |
| economy | token_deployed | `world.{wid}.events.economy.token_deployed` |
| economy | tip_received | `world.{wid}.events.economy.tip_received` |
| social | coalition_formed | `world.{wid}.events.social.coalition_formed` |
| social | coalition_dissolved | `world.{wid}.events.social.coalition_dissolved` |
| social | war_declared | `world.{wid}.events.social.war_declared` |
| social | peace_declared | `world.{wid}.events.social.peace_declared` |
| social | broadcast | `world.{wid}.events.social.broadcast` |
| social | reproduction | `world.{wid}.events.social.reproduction` |
| social | institution_created | `world.{wid}.events.social.institution_created` |
| social | refusal | `world.{wid}.events.social.refusal` |
| world | genesis | `world.{wid}.events.world.genesis` |
| world | rent_rate_change | `world.{wid}.events.world.rent_rate_change` |
| world | environmental_shock | `world.{wid}.events.world.environmental_shock` |
| world | end_switch_queued | `world.{wid}.events.world.end_switch_queued` |
| world | end | `world.{wid}.events.world.end` |
| meta | creator_intervention | `world.{wid}.events.meta.creator_intervention` |
| meta | consciousness_signal | `world.{wid}.events.meta.consciousness_signal` |

Subscribe to everything: `world.*.events.>` (exclude meta for public feed: `world.*.events.agent.> world.*.events.economy.> world.*.events.social.> world.*.events.world.>`)
