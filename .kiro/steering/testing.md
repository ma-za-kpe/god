# Testing Convention

Always run tests via `docker exec`. Never run pytest or test commands directly on the host.

Example:
```bash
docker exec <container_name> pytest runtime/tests/banter/ -v
```

This applies to all test execution — unit tests, property tests, integration tests, and the theater harness.
