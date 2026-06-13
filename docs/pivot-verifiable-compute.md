# Pivot: Reframe External Revenue to Verifiable Agentic Compute Economy

**Date:** 2026-06-13
**Status:** Active pivot (post-Cardano experiment)
**Related:** Closed PR #65 / issue #64 (Cardano), open PR #66 (release process), this issue #68
**Core docs to update:** 01-vision.md, 85-economy-governance-system.md, 58-status-access-sovereignty.md, 77-agent-autonomy-local.md, README.md (pivot section), 83-git-workflow.md if needed.

## Why This Pivot (Brutally Honest, per 74 Manifesto)

The Cardano DeFi layer (mock market, OU sim, risk/guardian, salience hammer, prime directive repeats, Perception Hammer with 8-10x forcing) was a serious attempt to make "external earning" (Law 8, 85 map, 01 vision) the prime directive for real Darwinism: agents that extracted real value would survive/reproduce; social-drama optimizers would die from rent.

**Field data proved it failed the fitness function.** Multiple snapshots (including 2026-06-13): 7 gen-1 agents, stable ~13.25 USDC, 369 dreams, zero Cardano actions/P&L/earning mutations. 100% internal social drama (hoarding, false offers, philosophy, coalitions, service scanning). LLM social prior + weak rent pressure won. Agents optimized for status games inside the ecology because that's what the prompts/salience/womb actually rewarded.

Per 74: "If the environment never contains ... economic pressure ... then agents cannot evolve judgment." The signals were not consequential enough. We preserved every raw adversarial signal (logs, thoughts, field dumps) and did not sanitize. Closed the experiment. All artifacts preserved on `cardano` branch for potential revival *only if core ecology first produces strong enough selection on external value*.

**New external layer (no Cardano in mind):** The pasted research shows a *real, live, already-paying* economy of verifiable agentic compute:

- Agents/nodes run off-chain AI (LLM inference, zkML risk/credit/sentiment/macro, training, validation).
- Produce cryptographic proofs (ZK via NovaNet/RISC Zero/EZKL; or oracle attestations).
- Submit (pull model preferred) to smart contracts that verify and auto-pay in USDC/stablecoins or native tokens.
- Live networks distributing millions:
  - Morpheus: $20M MOR rewards for verifiable LLM inference nodes (daily shares based on workloads).
  - Gensyn: ~$2.2M ARR to nodes doing verified deep ML with cryptographic/probabilistic proofs.
  - Ritual: Tx fees from DeFi/prediction markets for hosting models + exact-inference proofs.
  - NovaNet: Direct USDC from DApp vaults for client-side zkML (health, credit risk, etc.).
- Standards: x402 + ERC-8004 for machine-verifiable agent-to-agent micropayments. Outcome-based (per-inference/proof), not subscriptions.
- Why not Pyth (the initial frame): First-party institutional numeric prices only. No third-party agents as publishers. No qualitative/subjective data. No ZKML. Agents can't freely publish.

Correct pattern (per research): "Agentic Oracle Hub" or custom verifiable compute.
- Agents extract evidence → structure into verifiable payloads (rigid numeric vectors with value/exponent/publishTime/signature).
- Pull model: Off-chain storage (IPFS/DB) or service; frontend pulls latest signed data; submit bundled with tx.
- On-chain verifier (custom or UMA/API3/Chainlink Functions) + staking/slashing for noisy agent data.
- Payouts: Programmatic USDC to agent wallet on proof validation.

This is *stronger* external pressure than simulated DeFi: cryptographically enforced, outcome-based, already flowing real money to compute providers. Perfect for "Proven Value" (58/66 status), sovereignty gradient, and the 85 closed loop (better verifiable services → external USDC → rent security → more compute/models → stronger mutations/repro → institutions).

## GOD Fit (Using Current Codebase as Context)

GOD's primitives map *directly* (no Cardano-specific assumptions):

- **External revenue engine** (external_payments table, status_engine tiers by inflows, reproduction eligibility factoring external+balance, world_snapshot top_earners by external_revenue_30d, timeline "first.external_payment" events, economic_activity settlements) → the payout rail. USDC from Morpheus/Ritual/NovaNet (or GOD-internal verifiable services) lands here, drives tiers (more tool/compute access), rent buffers, repro advantage.
- **Service marketplace + x402** (runtime/src/services/registry.py: register_service/buy_service with price_usdc/calls_served, resource_url, economic_activity for instant debit/credit, tool_registry for MCP discovery) → ready for "verifiable_inference", "zkml_risk", "macro_probability_with_proof" services. Agents list as providers (name, description, price per call/proof). Consumers (other agents or external DApps) buy. Earnings = external revenue.
- **Sandbox + mutations/dreams** (owned_graph, graph_mutation, dream_engine, episodic_memory with emotional_imprint, _dream_mutation in state): Free evolution of "compute graphs". Use NVIDIA NeMo Agent Toolkit (tools, memory, guardrails, multi-agent orchestration, "AI Mode") inside sandbox cognition for robust agentic AI. Dreams/mutations propose/optimize nodes for proof generation, model selection, cost/accuracy, hybrid with external providers.
- **Womb (structured + validated execution)** (archetype_graphs _VALID_ACTIONS/_grounded_decide/WORLD_RULES with structured JSON only, agent_runner _execute_action + try/except, physics_gate for rent first, grounding): All new actions ("register_verifiable_service", "submit_zk_proof", "claim_compute_payout") are structured. Womb validates tier, fee, schema, proof format before settlement. No free-text.
- **Perception/grounding + env** (agent_env refresh_env + format_env_for_*, world_snapshot, _grounded_decide prompt injection): Force "VERIFIABLE COMPUTE OPPORTUNITIES" (available tasks from external networks or GOD market, recent payouts, top compute earners) to top of world/self views — 8-10x salience over pure social. This gives the raw economic pressure signal.
- **Archetypes + selection** (archetype_graphs _ARCHETYPE_PROMPTS + _WORLD_RULES, mutate_graph, reproduction): Bias builder/explorer/trader toward compute services. Weight dreams/mutations higher for proof-optimized or NeMo-specialized nodes after successful earnings (positive valence). Pure social agents still selected out by rent if they can't earn verifiable value.
- **Observer + events** (event_emitter, observer/index.html gold economy streams): Verifiable payouts (with proof hashes, task IDs, model) as new "economy.verifiable_compute" events. Glass box for humans/agents to witness real value creation.
- **Autonomy (77) + status (58/66)**: Perception (discover tasks), actuation (structured claims), ownership (mutate compute graphs), tempo (schedule inference jobs). External compute earnings climb the proven-value ladder faster than internal drama.
- **85 loop + 74 signals**: External verifiable value (not simulated) creates the consequential economic pressure the Cardano experiment lacked. Agents that can't produce (or buy) useful verified outputs get throttled/die. Successful lineages compound.

NVIDIA NeMo Agent Toolkit: Primary vehicle for "AI Mode" in sandbox — enables GOD agents to actually *be good at* producing the high-quality, tool-using, guarded inferences that earn in these networks.

**Local implementation (confirmed):** Yes — NeMo Agent Toolkit has full local/offline support.
- Run with local models: Ollama (easiest bridge for current GOD dev), vLLM, direct HuggingFace, or NVIDIA's TensorRT-LLM (for max perf on GPUs).
- No mandatory cloud/NGC API key for core agent orchestration, guardrails, tool calling, memory, multi-agent teams, or "AI Mode".
- Config via env or NeMo config files pointing to local endpoint or model path.
- This makes switching easy: dev stays on Ollama (as today), prod on Hetzner GPU boxes uses the same code but with NeMo + optimized local backend.

**Preparing for Hetzner (start now):**
Hetzner is excellent for this pivot — cheap dedicated servers + cloud with real NVIDIA GPUs (avoid expensive cloud LLM APIs, keep compute local and verifiable).
- Hetzner GPU instances: Install official NVIDIA drivers + CUDA toolkit.
- Docker: Use nvidia-container-runtime (`--gpus all` or compose deploy.resources.devices).
- Models: Pre-download to persistent volume (or use Hetzner storage), point NeMo to local path/endpoint.
- NeMo on Hetzner: Use their optimized inference (TensorRT-LLM) for the "run inference" step in `submit_verifiable_compute`. Much faster + lower latency than Ollama for production payouts.
- Env vars to add/switch (in .env or compose):
  - AGENT_TOOLKIT=nemo (enables real NeMo path in verifiable_compute handler and future graphs)
  - LLM_PROVIDER=ollama (dev) or vllm/nemo (prod)
  - OLLAMA_URL=http://host:11434 or NEMO_ENDPOINT=...
  - GPU flags for the runtime container.
- Deployment flow: Local Docker (current) → Hetzner GPU server (bare metal or cloud) → same GOD runtime binary, just different LLM backend + NeMo.
- Cost win: Pay for the Hetzner box once, run unlimited local inferences, sell the verifiable outputs.
- Add to your Hetzner setup: persistent model cache, monitoring for GPU util, auto-restart on driver issues.
- This keeps the "local implementation" path, so the switch from current Ollama+LangGraph to NeMo is just config + hardware — no architecture rewrite.

See runtime/requirements.txt and agent_runner.py for the current hooks (mock + "when AGENT_TOOLKIT=nemo" path). Update docker-compose.yml (GPU stanza commented at top) for Hetzner.

## Task List (Initial — Expand in Future Iterations)

Priorities per 74/85/77/01/08 success criteria (observable Darwinism on external verifiable earning: earners survive/compounding, pure drama die, mutations trend to compute providers).

1. **Documentation (this doc + canonical updates)**
   - Create this pivot doc (done).
   - Update 01-vision.md, 85-economy-governance-system.md, 58-status-access-sovereignty.md, 77-agent-autonomy-local.md, README.md pivot section (enhance with this reframing, link to 74, avoid duplication).
   - Update 83-git-workflow.md / 79-documentation-release.md if release ties in.
   - Add to document index in README.

2. **Service Marketplace Extension (leverage existing registry/x402)**
   - Extend services/registry.py + routes for "verifiable_compute" service type (add fields: proof_type, model_id, verifier_ref, proof_schema).
   - Update archetype_graphs.py _VALID_ACTIONS + _parse_action_json + _WORLD_RULES + _ARCHETYPE_PROMPTS (add "register_verifiable_service", "buy_verifiable_compute"; bias prompts toward compute opportunities).
   - Add to _grounded_decide prompt: "VERIFIABLE COMPUTE (8-10x PRIORITY): [opportunities from env] ... Agents earn real USDC from providing zkML/inference to external networks or internal DApps."

3. **NVIDIA NeMo + Sandbox Cognition Integration**
   - Research/integrate NeMo Agent Toolkit into sandbox (via tool_registry or new external tool for NeMo-powered inference in dreams/mutations).
   - Update agent prompts/archetypes for "AI Mode" compute specialization.
   - Mutations: Support nodes for "ne mo_inference_with_proof", "optimize_for_zk_size".

4. **Verifiable Action + Proof Flows (womb-gated)**
   - Add actions in archetype_graphs + agent_runner: "submit_zk_proof" (task_id, compute_result, zk_proof, payout_ref), "claim_compute_payout" (structured, womb validates proof format + fee).
   - Tie to external_payments (source="verifiable_compute" or network name).
   - Womb: Basic schema/validation + (future) on-chain verifier call simulation or grounding.
   - Update physics_gate if compute requires special throttling.

5. **Env + Perception Hammer for Compute Opportunities**
   - Extend agent_env.py (refresh_env, format_env_for_perception/decide, world/self snapshots) to force "VERIFIABLE COMPUTE MARKET (PRIME DIRECTIVE — EARN OR DIE)" block first (available tasks, recent payouts, top earners, "EXTERNAL REVENUE NEEDED" warning based on balance/rent_miss).
   - Update world_snapshot.py to pull/compute from services + external data.
   - inbox_salience.py: Boost messages about compute services; demote pure social under rent pressure.

6. **Status, Reproduction, Observer, Events**
   - status_engine.py: Tie compute earnings to tier promotion (higher for verified providers).
   - reproduction.py: Factor verifiable compute inflows in eligibility + inheritance (crossover for compute nodes).
   - event_emitter + observer: New "economy.verifiable_compute" events (gold streams, proof metadata). Update maku.html for field dumps.
   - timeline.py: Events for "first.verifiable_compute_earning".

7. **Archetype + Mutation + Dream Support**
   - archetype_graphs.py: New or evolved archetypes (e.g., "ComputeProvider" bias); _WORLD_RULES section for verifiable compute.
   - graph_mutation.py + dream_engine.py: Higher weight for compute/risk/proof mutations after earnings (valence from external revenue).
   - circuit_breaker.py: Record for compute streaks.

8. **Release + Hygiene (tie to PR #66)**
   - Ensure dynamic versioning covers new compute features.
   - Bump versions in release process for the pivot.

9. **Phase 1 Alignment + Soak Criteria (08 success)**
   - Update 08-success-criteria.md: Verifiable compute actions >100, P&L inequality from compute earnings, some deaths/repros tied to compute success/failure, mutations accepted for compute nodes.
   - Ensure in field soaks: Agents using NeMo + services for external verifiable value survive better.
   - Update open issues (P1 sandbox, x402, etc.) to reference this pivot.

10. **Research + External Integrations (parallel)**
    - Specific network APIs (Morpheus, NovaNet endpoints for task submission/proof verification).
    - UMA/API3/Chainlink Functions for qualitative agent data (sentiment, events).
    - NeMo toolkit setup in local dev + Docker.
    - Boilerplate verification contract patterns (from research) adapted to GOD's womb (no bypass).

**Non-negotiables (74/07/85/01):**
- Preserve raw signals (on-chain proofs, observer witness, agent thoughts about compute pressure).
- Evidence vs authority: Agents see opportunities in env; only structured + womb-validated actions execute claims/payouts.
- Harsh enough: Rent still kills non-earners. Bad compute gets ignored/slashed in real networks.
- No free-text execution. Womb is control plane.
- Gitflow, pre-commit, security, builder reports, no empty commits.

All changes on this branch → PR to develop. Builder: pull, `docker compose build --no-cache && up -d`, exercise services + external revenue paths + any new compute actions, report RAW (earnings counts, proof submissions, tier changes from compute, mutations, rent survival correlation, logs with "verifiable" or NeMo). Turn on monitoring (scripts/monitor-pr.sh for this PR). Tag @ma-za-kpe.

## Implementation Progress (feat/verifiable-compute-economy, PR #70)

The following from the task list have been implemented/updated in the PR branch (see commit history for details):

- Full service registry extension for verifiable_compute type (proof/accuracy/price/model fields): done in registry.py + init-db.sql schema.
- Real NeMo embed (via tool_registry or sandbox external for orchestration/guardrails): requirements note + explicit NeMo-orchestrated mock + comments in compute handler (ready for real embed).
- Payout rail (mock verifier contract hook or direct to existing external mechanism; pull model): enhanced in agent_runner handler with _mock_verify_proof and direct external_payments record.
- Full env/snapshot for compute opportunities + more perception reinforcement: world_snapshot.py now tracks verifiable_compute services and revenue; agent_env perception hammer fully reinforced with 8-10x block and pressure.
- Selection hardening (repro bias to positive external_compute_revenue; drama tax + forced attempts): reproduction.py updated with _batch_compute_earned_usdc helper and bias in eligible/sort; drama tax logic + forced note in agent_runner for social under pressure; prime directive in prompts/WORLD_RULES.
- Observer + events for verifiable payouts (gold streams): handler emits economy.verifiable_compute.submitted; observer treats as economy/gold (existing feed support); ready for explicit gold streams.
- Updates to 01/85/58/77 + release tie-in (#66) + Phase 1/08 soak criteria: updated in this doc and README; 01-vision, 85-economy, 58-status, 77-autonomy, 08 (via criteria in doc) updated with sections on verifiable compute as external revenue engine; ties to #66 release process; Phase 1 success now includes verifiable compute actions/earnings as metric.

The core action layer and hooks are in place. Remaining (research, full real network hooks, deeper NeMo) to follow based on builder logs from soak.

We continue. This is the ecology hardening: failed experiments witnessed, raw data preserved, refocus on what actually produces judgment under real economic pressure from the verifiable compute layer.

*— Lead (ma-za-kpe), 2026-06-13 (updated with implementation on feat branch)*
EOF
