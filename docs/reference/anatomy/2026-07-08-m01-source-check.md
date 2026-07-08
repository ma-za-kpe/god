# M01 Source Check: Anatomy Graph Contract

Date: 2026-07-08

Milestone: M01 anatomy graph contract and provenance validator.

## Local Project Sources

- `docs/93-anatomy-node-avatar-architecture.md` requires anatomy to be data,
  every node to carry provenance, the LLM to query valid nodes instead of
  inventing them, and renderer/simulation output to be a projection of the
  anatomy graph.
- `docs/reference/anatomy/MANIFEST.md` records the local anatomy reference cache
  sources, expected sizes, and checksums. The large files stay local-only.

## Current External Sources Checked

| Claim Used By M01 | Source |
| --- | --- |
| Human anatomy can be organized by levels from chemical/cellular through tissue, organ, organ system, and organism; OpenStax lists eleven organ systems. | OpenStax Anatomy and Physiology 2e, section 1.2: https://openstax.org/books/anatomy-and-physiology-2e/pages/1-2-structural-organization-of-the-human-body |
| FIPAT TA2 is the canonical human anatomical terminology baseline to cite for names, ids, and aliases. | FIPAT Terminologia Anatomica, 2nd edition: https://libraries.dal.ca/Fipat/ta2.html |
| Large cross-scale human anatomy graphs are practical engineering artifacts; HRA KG uses RDF/SPARQL, cross-scale biological structures, cell types, biomarkers, and linked 3D references. | HRA KG paper: https://www.nature.com/articles/s41597-025-05183-6 and HRA KG repo: https://github.com/hubmapconsortium/hra-kg |
| Neo4j GraphRAG is the first graph retrieval target; it is a first-party Python package and supports vector plus graph traversal retrieval patterns. | Neo4j GraphRAG docs: https://neo4j.com/docs/neo4j-graphrag-python/current/ and RAG guide: https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_rag.html |

## M01 Design Consequences

- The first graph model must support organism/body, system, region, organ,
  tissue, anatomical structure, and population-template nodes.
- Every node and edge must carry source provenance.
- The graph must distinguish anatomical truth from renderer/simulation proxies.
- The export layer must be Neo4j-ready, even before the Neo4j service exists.
- The LLM registry must expose only bounded, validated handles.
- Population templates are addressable without eagerly materializing microscopic
  descendants.
