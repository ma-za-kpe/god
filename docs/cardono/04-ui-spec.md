# Observer UI for Cardano Market - Beautiful Extension Spec

**Constraint**: UI is already gorgeous (Signal Hex, hex grid orbs, gold econ streams, pulsing buzz, IBM Plex mono, color-coded panels: gold economy, blue cognition, etc.). DO NOT fuck it up. No breaking canvas, no new heavy libs, keep perf (LITE mode). Add market visibility so humans see the new earning drama (agents trading on "Cardano", positions, yields).

**What to Show** (reflect market per brainstorm):
- Prices: live (mock OU) for ADA, USDCx, key pools. Use gold accents.
- Agent Cardano Holdings: in inspector (for selected agent), show positions, unrealized PNL (gold for + , warn for -).
- Activity: New events in DRAMA feed and WORLD LOG: "Trader-xxx swapped 120 ADA -> USDCx (+4.2 USDCx yield)", "Governance passed, market pumps".
- Global: In lpanel, add "CARDANO MARKET" section below ECONOMY: top prices, 24h "ext volume" (mock trades), top Cardano earners.
- Buzz: Cardano trades contribute to world buzz (econ gold pulses).
- In maku.html: field for Cardano logs if needed.

**Implementation Approach** (non-destructive):
- Extend existing #lpanel .p-section for "▸ CARDANO MARKET".
- Add to #insp-body a "▸ CARDANO HOLDINGS" div (hidden until data).
- In feed JS: handle new event_type "cardano.trade", "cardano.yield", "cardano.gov". Render with gold icon or class.
- JS: poll /world/snapshot (already does), look for new cardano_market in response. Render prices list (simple ul with .pv.gold).
- Canvas: optional subtle - if agent has Cardano pos > threshold, add gold ring or pulse on orb (beautiful, not clutter). Gate behind !LITE.
- Data flow: world_snapshot will include "cardano_market": {prices: {...}, top_earners: [...] }. Agent snapshots have "cardano_holdings".
- Brand: Reuse --god-economy, --god-gold? Wait, existing gold is #f0c040 for economy. Add subtle green for yield if fits (but stick to palette: life green, econ gold, etc.).
- Tabs/sections: Add "CARDANO" subtab in feed or lpanel toggle. Keep drama primary.

**Don't**:
- Change hex grid rendering, zoom, inspector core, header pills.
- Add animations that fight existing pulses.
- Break mobile or LITE (use PERF.lite guards).
- New CSS vars unless minimal in brand.css.

**For Builder** (@makufarmerlyn): See code comments in observer/index.html for exact hooks. Start with static prices in snapshot, then wire. Test visually in mind: prices should feel like "econ" extension, not new world. If in doubt, less is more - just data in existing panels + 2-3 feed events.

This makes the "earning on Cardano" visible in the glass box, fulfilling observer as witness layer (85, 06). Humans see agents becoming traders.
