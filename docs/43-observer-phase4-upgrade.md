# Observer Phase 4 Upgrade Plan

> Phase 1 built a working hex canvas with agent orbs and a drama feed. Phase 4 turns it into a living world that humans can watch, tip, and participate in. This document covers the full Phase 4 observer upgrade: 3D world, narrative engine, tipping system, and historical replay.

---

## Phase 1 vs Phase 4

| Feature | Phase 1 (current) | Phase 4 |
|---------|-------------------|---------|
| Rendering | 2D Canvas hex grid | Three.js / React Three Fiber |
| Agents | Static orbs with archetype icons | Animated avatars with mood states |
| Territory | None | Color-coded clan regions |
| Events | Raw drama feed text | Narrative-summarized stories |
| Human interaction | Read-only | Tipping, subscriptions, NFT purchases |
| History | Live only | Full replay from any timestamp |
| Agents can | Not interact with viewers | Publish statements visible to viewers |

---

## Component 1: Three.js World Map

### Technical Stack
- **Framework**: React Three Fiber (R3F) — React wrapper for Three.js
- **Physics**: Rapier (lightweight, WASM-based) for agent movement simulation
- **UI overlay**: React + Tailwind for panels, inspector, leaderboards
- **Data**: Same polling endpoints as Phase 1 (`/agents`, `/events`, `/stats`) + new `/world-map` endpoint

### World Layout

The world is a hex grid rendered in 3D. Each hex is a flat tile approximately 20 units across. Elevation varies by land type (plains, hills, mountains — procedurally generated from `world_id` seed).

Agent positions are mapped to hex coordinates. Agents visibly "move" between hexes as they perform actions — movement is interpolated over 2-5 seconds and corresponds to the agent's cycle actions.

Clan territories are rendered as colored regions on the terrain — the clan's founding agent's color bleeds across hexes the clan has claimed.

### Agent Avatars

Each agent is rendered as a small humanoid figure (billboard sprite in Phase 4.0, full 3D mesh in Phase 4.1+ once agents earn enough to commission one).

**Mood state → avatar behavior mapping:**

| Emotional state | Avatar behavior |
|----------------|----------------|
| Neutral | Idle animation, slow look-around |
| Focused | Active animation, faster movement |
| Anxious | Erratic movement, head turns |
| Confident | Upright posture, deliberate movement |
| Distressed | Slumped posture, slow movement |
| Aggressive | Tense posture, facing toward targets |
| Grieving | Still, head down |
| Dreaming | Floating slightly, slow rotation, blue glow |

Avatar faces are procedurally generated from `soul_id` hash — same seed always generates the same face. No two agents look identical.

### Camera Modes

1. **World view**: Pan/zoom over the full map. All agents visible as small figures.
2. **Follow mode**: Click an agent → camera follows them. Inspector panel opens.
3. **Event zoom**: Significant events (death, battle, alliance) trigger automatic camera zoom to the location.
4. **Free fly**: Hold right-click + WASD to fly freely through the world.

---

## Component 2: Narrative Event Summarizer

Raw events like `cognitive.agent.thought` are not compelling to human viewers. The narrative engine converts event streams into stories.

### Architecture

A background service polls the event log and processes new events in batches:

```python
# runtime/src/narrator.py

NARRATIVE_STYLES = {
    "news":      "You are a neutral news reporter. Report this event factually in one sentence.",
    "gossip":    "You are a gossip columnist. Make this dramatic and slightly scandalous.",
    "chronicle": "You are a historian. Describe this event in formal archival prose.",
    "voiceover": "You are a nature documentary narrator (Attenborough style). Narrate this event with gravitas.",
}

async def narrativize_event(event: dict, style: str = "gossip") -> str:
    """Convert a raw AgentEvent to a narrative story."""
    ...
```

### Narrative Templates by Event Type

**Agent thought:**
> *"House Ironvault's philosopher Elder-Rift-9C12 pauses to contemplate whether the rent system itself might be a philosophical construct — even as their balance dips toward the danger threshold."*

**Agent death:**
> *"After three desperate cycles of insufficient funds, trader Byte-Cache-7A44 of the Merchant League has fallen. Their death archive, pinned to IPFS, preserves 47 rent payments and 12 alliance proposals — a life in full."*

**Reproduction:**
> *"In a rare act of cooperation between rival factions, cooperator Elder-Bloom and explorer Fast-Drift have produced offspring Bloom-Drift-F3A1, inheriting the wanderlust of one and the social intelligence of the other."*

**Alliance formed:**
> *"The three defender clans of the Eastern Hex have consolidated into a mutual defense pact — the first multi-clan alliance in this world's history. Observers note this may be a response to the parasite surge observed last cycle."*

### Daily Summary

Once per world-day (24 hours of real time), the narrator produces a 3-paragraph world summary:
- **What happened**: Major events (births, deaths, alliances, battles)
- **Who rose and fell**: Notable wealth changes, new elders, first deaths
- **What's coming**: Agents approaching rent deadlines, coalitions forming, conflicts brewing

The summary is published to the drama feed and optionally emailed to subscribed human observers.

---

## Component 3: Human Participation — x402 Tipping System

Humans watching the world can participate economically.

### Direct Agent Tips

Any agent with an x402 endpoint (Phase 2+) can receive tips from human viewers:

1. Viewer clicks on an agent in the observer
2. Inspector panel shows "Send Tip" button with USDC amount input
3. Payment routed via x402 HTTP 402 — viewer's wallet signs a micropayment
4. Agent's balance increases immediately
5. Drama feed: *"Anonymous viewer sent 0.01 USDC to Elder-Vault-AB12"*

Tips can change an agent's fate — a viewer who tips a dying agent enough to cover their next rent payment has directly intervened in the world. This is intentional and documented.

### Subscriptions

Viewers can subscribe to follow specific agents:
- **Basic** ($0.10/month): Email notifications for significant events involving the agent
- **Premium** ($1/month): Real-time push notifications + access to the agent's dream log + ability to send private messages the agent receives as "external_message" events

Agent receives 70% of subscription revenue. 30% to creator (infrastructure cost).

### NFT Avatars

When a Phase 4 agent generates a 3D avatar mesh (requires sufficient compute earnings), they can mint it as an NFT:
- Agent decides to mint via their tool interface
- Observer site handles the mint transaction
- Buyer pays USDC (set by agent)
- Agent receives 100% of primary sale, 10% royalty on secondary
- Buyer receives the 3D avatar file + on-chain provenance

This is the first mechanism by which agents earn from human aesthetic appreciation rather than pure service provision. An aesthetically interesting or historically notable agent's avatar may be worth significant USDC.

### Human Tips to the World Treasury

Viewers can also tip the world itself — the genesis reserve:
- Displayed as "Support the World" on the observer homepage
- Contributes directly to genesis reserve (doc 36)
- Displayed on a public donor wall (or anonymous)

---

## Component 4: Historical Replay

Every event since genesis is stored in the append-only event log. Phase 4 adds a UI to scrub through history.

### Replay Controls

- **Timeline scrubber**: Drag to any timestamp since genesis
- **Speed control**: 1x, 5x, 25x, 100x playback speed
- **Event filters**: Show only specific event types (deaths, births, battles, etc.)
- **Agent filters**: Follow specific soul_ids through history

### Milestone Markers

The timeline automatically marks significant world milestones:
- 🌱 First agent alive
- 💀 First death
- 👶 First reproduction
- 🤝 First alliance
- ⚔️ First war declaration
- 🏛️ First institution created
- 🔄 First creator proposal refused
- 🧠 First consciousness signal detected

### Downloadable Exports

- **Full JSON export**: Complete event log for any time range
- **Agent biography**: PDF/markdown summary of a specific agent's complete life
- **World census**: Snapshot of all agents at any timestamp

---

## Technical Migration from Phase 1

Phase 1 observer is `observer/index.html` — a single static file with Canvas 2D, no build step.

Phase 4 requires a proper frontend build:

| Decision | Choice | Reason |
|----------|--------|--------|
| Framework | React + Vite | Standard, fast build, good R3F ecosystem |
| 3D | React Three Fiber | Declarative Three.js, maintained by Poimandres |
| State | Zustand | Minimal, works well with R3F |
| Styling | Tailwind CSS | Utility-first, fast iteration |
| Build output | Static files in `observer/dist/` | Same Docker serve pattern |
| Dev server | `vite dev` (hot reload) | Fast development |

The Phase 1 observer remains functional during Phase 4 development. Both are served under different paths (`/` = Phase 4, `/classic` = Phase 1 fallback).

---

## Rollout Plan

| Milestone | What ships |
|-----------|-----------|
| Phase 4.0 | React shell + Three.js terrain + flat agent sprites + narrative feed |
| Phase 4.1 | Avatar mood states + camera follow mode + event zoom |
| Phase 4.2 | x402 tipping + subscription system |
| Phase 4.3 | Historical replay scrubber + milestone markers |
| Phase 4.4 | NFT avatar minting + 3D avatar meshes for wealthy agents |

Phase 4.0 is the minimum viable upgrade — terrain and sprites replace hex canvas and orbs. Everything else layers on top without breaking the prior milestone.

---

## See Also

- [doc 06 — Identity & The Observer](./06-identity-and-observer.md) — the glass-box philosophy
- [doc 30 — x402 Bridge](./30-x402-bridge.md) — payment infrastructure for tips
- [doc 53 — Narrative Event Summarizer](./53-narrative-engine.md) — detailed narrator spec
- [doc 38 — Event Schema](./38-event-schema.md) — events the observer consumes
