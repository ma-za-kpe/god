# Anatomy Node Avatar Roadmap

Status: active roadmap.

This roadmap turns `docs/93-anatomy-node-avatar-architecture.md` into strict,
testable milestones. We implement one milestone at a time. Before advancing to
the next milestone, the current milestone must be checked against the project
docs, anatomy references, current web sources, validation pipelines, and visual
evidence when a renderer is involved.

## Non-Negotiable Gate

Every milestone must end with:

- Source check against `docs/93-anatomy-node-avatar-architecture.md` and
  `docs/reference/anatomy/MANIFEST.md`.
- Current-source check for any external tool or anatomy claim that could have
  changed.
- Unit tests for the new behavior.
- Lint/build/compile checks for the touched stack.
- Browser-visible body morph/projection evidence. Early data milestones may use
  the anatomy projection route; renderer milestones must use the real avatar
  renderer. Restart the browser before capture and save screenshots.
- No silent degradation. Unsupported controls, missing nodes, missing sources,
  and renderer gaps must be explicit diagnostics.

## Key Stack

| Layer | Chosen Direction |
| --- | --- |
| Anatomy truth | Source-cited graph seeded from OpenStax, FIPAT TA2, FMA/Uberon-compatible ids, HRA-style cross-scale structure. |
| Graph database | Neo4j first, with Cypher constraints and vector indexes. Memgraph remains a performance candidate later. |
| Retrieval | Neo4j GraphRAG, VectorCypherRetriever-style hybrid semantic plus graph traversal. |
| LLM boundary | Structured tool/JSON contract. The LLM receives a bounded node registry and never invents anatomy nodes. |
| Movement and simulation | OpenSim/Moco and MuSkeMo first for skeleton/muscle mechanics; SOFA/FEBio later for soft tissue and organs. |
| Browser rendering | Three.js/GLB/VRM/TalkingHead projection first; Blender/MuSkeMo exports and simulation sidecars later. |
| Validation | TDD, provenance checks, graph invariants, action-bundle tests, renderer diagnostics, screenshots. |

## Milestones

| ID | Status | Goal | Exit Criteria |
| --- | --- | --- | --- |
| M01 | complete | Anatomy graph contract and provenance validator. | Python domain model exists; every node/edge requires source provenance; Neo4j export shape exists; LLM registry excludes invalid/unsupported nodes; tests pass; browser body morph evidence exists at `/anatomy-lab` and `artifacts/m01-anatomy-browser-morph.png`. |
| M02 | complete | Canonical seed graph for body, systems, head, knee, hand, and toe. | Seed data is source-cited from OpenStax, NCBI/StatPearls, and FIPAT TA2; tests cover head, knee, hand, and toe breakdown; browser body projection evidence exists at `artifacts/m02-anatomy-browser-morph.png` with timed-frame diff evidence. |
| M03 | complete | Neo4j local graph service and constraints. | Docker `anatomy-graph` Neo4j service exists; Community-safe indexes/constraints are generated; seed graph loads into Neo4j; Cypher validation passes locally; browser evidence exists at `artifacts/m03-anatomy-neo4j-morph.png`. |
| M04 | complete | GraphRAG retrieval and LOD compiler. | Queries such as `wave`, `run`, and `sweat on forehead` compile into bounded working sets; no million-node context dumps; tests prove LOD behavior; browser evidence exists at `artifacts/m04-anatomy-lod-morph.png` with timed-frame diff evidence. |
| M05 | next | LLM anatomy control contract. | LLM gets only valid handles; invented nodes are rejected; action plans include diagnostics and source-backed node ids; Ollama/local model path tested. |
| M06 | pending | Browser anatomy inspection renderer. | The browser can render graph-derived body/system/head/knee/toe layers; screenshots prove visible output; missing mappings degrade visibly. |
| M07 | pending | Motion projection bridge. | Anatomy action bundles map to existing avatar controls and OpenSim/MuSkeMo-ready controls; wave/sit/run have deterministic compiled plans. |
| M08 | pending | Soft tissue and microstructure materialization. | Skin patches, sweat glands, hair follicles, capillary beds, and render proxies use population templates and lazy materialization with tests. |
| M09 | pending | Continuous LLM-directed anatomy avatar loop. | LLM continuously changes anatomy-aware action bundles, camera, body, expression, clothing proxy, and visible layers; monitor proves audio/action/render sync. |
| M10 | pending | Production-quality validation harness. | One command validates graph, RAG, LLM contract, renderer, screenshots, logs, and diagnostics before any branch is considered green. |

## Milestone Discipline

Do not skip ahead. If a renderer milestone exposes a graph flaw, return to the
graph milestone and fix the contract. If an LLM milestone invents nodes, fix the
registry and validator. If a mature tool already solves a subproblem, build an
adapter instead of rebuilding the tool.

Every milestone must make the body visibly change in the browser at the
appropriate fidelity for that milestone. The change can be an anatomy projection
for graph/data milestones or the full avatar renderer for animation milestones,
but it must be screenshot-verified after restarting the browser.

The ambition remains explicit, large-scale anatomy addressability. The runtime
discipline is compiled working sets, lazy materialization, source provenance,
and strict projection into renderer/simulation capabilities.
