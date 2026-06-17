"""Property-based and unit tests for the Broadcast-Quality Banter Engine.

IMPORTANT: This file must NOT be present in the Docker container during test
execution. It exists in version control for IDE discovery and documentation,
but causes import shadowing when pytest adds tests/ to sys.path (tests/banter/
would shadow src/banter/). The test workflow removes it after docker cp:

    docker cp runtime/tests god-runtime:/app/tests
    docker exec god-runtime rm -f /app/tests/banter/__init__.py
"""
