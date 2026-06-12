# Implementation Status & Roadmap (as of now, lead perspective)

**Documented**: Full brainstorm captured in 00-05 + this. All from user pasted thoughts + my synthesis. Goals checked against canon (vision, 14 laws, 85 map, 74 manifesto, 58/77 autonomy, 30/56 x402/services).

**Built so far (skeleton by lead)**:
- Docs/cardono/ full set.
- [In progress via edits]: cardano_market.py stub (will have OU).
- Capabilities extended (in mind).
- UI hooks planned (comments for builder).
- No running done.

**For Builder (makufarmerlyn)**:
Follow PR desc in 05. Use comments in code for comms. Leverage 100% existing patterns (no new DB tables yet for mock holdings - use agent_env scratch or in-memory in cardano_market).
Prioritize: mock sim first (so agents can "trade" locally immediately), then UI visibility, then action wiring.
When real: swap mock with APIs, but keep same schemas.

**Roadmap**:
1. Mock + local earning among 8 (this PR).
2. Archetype specialization + mutations toward trading.
3. UI polish + feed integration.
4. Real Cardano (testnet first, WingRiders etc.).
5. Production: ext rev flows to tiers, agents ascend via earning.

Satisfied only when: agents can propose/execute mock trades safely, P&L affects survival/repro, UI shows it beautifully, all comments addressed, no breakage to autonomy/grounding/rent.

godspeed.
