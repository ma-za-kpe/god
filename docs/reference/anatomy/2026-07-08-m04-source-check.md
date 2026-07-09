# M04 Source Check: GraphRAG Retrieval And LOD Compiler

Date: 2026-07-08

Milestone: M04 bounded GraphRAG retrieval and level-of-detail compiler for
anatomy action bundles.

## Sources Checked

| Claim Used By M04 | Source |
| --- | --- |
| Neo4j GraphRAG for Python is Neo4j's first-party package for GraphRAG workflows, including graph search, vector search, and retrievers. | Neo4j GraphRAG Python Package developer guide: https://neo4j.com/developer/genai-ecosystem/graphrag-python/ |
| `VectorCypherRetriever` combines vector similarity with a Cypher traversal over the graph context. | Neo4j GraphRAG Python user guide: https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_rag.html |
| GraphRAG retrievers can operate over an already-populated Neo4j graph and use Cypher to enrich initial seed results. | Neo4j GraphRAG Python package repository/docs: https://github.com/neo4j/neo4j-graphrag-python |
| Vector indexes are available for later semantic seed retrieval, but dimensions should be explicit once embeddings exist. | Neo4j Cypher Manual, Vector indexes: https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/ |

## M04 Design Consequences

- Do not parse natural language in the compiler. The LLM supplies structured
  action intent and seed node ids; code validates and compiles the bounded
  working set.
- M04 mirrors the `VectorCypherRetriever` architecture without creating
  embeddings yet: semantic/LLM seed selection first, Cypher graph traversal
  second.
- The compiler must cap node count per action bundle. Full-body actions such as
  `run` cannot dump the body graph into LLM context.
- Missing anatomy seeds become diagnostics, not fake nodes.
- Unsupported capabilities become diagnostics. This preserves the rule that
  code owns schema/validation while the LLM owns intent.
- Vector indexes are deferred until M04 has real embeddings and source-backed
  dimensions for action/node text.
