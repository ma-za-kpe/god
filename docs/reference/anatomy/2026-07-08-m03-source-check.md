# M03 Source Check: Neo4j Local Graph Service

Date: 2026-07-08

Milestone: M03 local Neo4j graph service, schema, load script, and Cypher
validation checks for the sourced anatomy graph.

## Sources Checked

| Claim Used By M03 | Source |
| --- | --- |
| Neo4j Docker supports explicit versioned images, persistent `/data` volume mounts, port `7474`/`7687`, and `NEO4J_AUTH` for initial credentials. | Neo4j Operations Manual, Getting started with Neo4j in Docker: https://neo4j.com/docs/operations-manual/current/docker/introduction/ |
| Neo4j Docker Compose deployments should persist data/log/config/plugin paths and avoid hardcoded secrets for production. | Neo4j Operations Manual, Deploy a Neo4j standalone server using Docker Compose: https://neo4j.com/docs/operations-manual/current/docker/docker-compose-standalone/ |
| Neo4j recommends explicit Docker image versions for custom/development images. | Neo4j Operations Manual, Docker configuration: https://neo4j.com/docs/operations-manual/current/docker/configuration/ |
| Cypher supports idempotent `CREATE CONSTRAINT ... IF NOT EXISTS` uniqueness constraints. Existence, type, and key constraints are Enterprise-only. | Neo4j Cypher Manual, Constraints syntax: https://neo4j.com/docs/cypher-manual/current/schema/syntax/ |
| Cypher supports idempotent range/text indexes with `IF NOT EXISTS`; range indexes are the default search-performance index. | Neo4j Cypher Manual, Create indexes: https://neo4j.com/docs/cypher-manual/current/indexes/search-performance-indexes/create-indexes/ |
| Vector indexes are available for later GraphRAG work and should use explicit dimensions, but M03 does not create embeddings yet. | Neo4j Cypher Manual, Vector indexes: https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/ |

## M03 Design Consequences

- Use an explicit Neo4j image instead of `latest`. The current Docker docs show
  `neo4j:2026.06.0` as an example, but that tag did not resolve from Docker Hub
  during validation on 2026-07-08. `neo4j:5.26-community` resolved and is pinned
  for M03 because M03 only needs Community-safe uniqueness constraints and
  search indexes.
- Run the local `anatomy-graph` Neo4j profile with `NEO4J_AUTH=none` and
  loopback-only ports. This avoids committed default credentials. Production or
  shared-network deployments must use an external secret manager or uncommitted
  environment override.
- Keep Neo4j behind the `anatomy-graph` Compose profile so normal observer
  work does not pull or start it accidentally.
- Use Community-safe uniqueness constraints and search indexes only.
- Do not pretend Community can enforce all required fields. Python validation
  remains authoritative for source provenance and required anatomy fields, and
  generated Cypher validation queries report missing fields after load.
- Relationship identity is explicit through `graph_key` so repeated local loads
  are idempotent.
- Vector indexes are deferred until the M04 GraphRAG milestone creates real
  embeddings and dimensions.
