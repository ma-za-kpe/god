# Agent Autonomy Audit Checklist

> Living audit for issue #10 — [doc 77](./77-agent-autonomy-local.md) structured actuation coverage.

**Last audit:** 2026-06-10 · Branch `develop` (integrated via PR #13)

---

## Axes

| Axis | Status | Evidence |
|------|--------|----------|
| **Perception** | ✅ | `agent_env.py` namespace; salience-ranked inbox (`inbox_salience.py`); peer field `_salience_peers()` |
| **Memory** | ✅ | Scratch via `write_scratch`; `agent_action_log` durable in PostgreSQL |
| **Actuation** | ✅ | `VALID_ACTIONS` in `capabilities.py`; tier gates; `validate_action_target()` in grounding |
| **Ownership** | ✅ | `graph_mutation.py`, `tool_registry.py`, dream mutations with grounding check |
| **Tempo** | ✅ | `agent_jobs.py` `schedule_wake`; `agent_scheduler.py` force_wake |
| **External read** | ✅ | `external_read` tier-gated; gateway allowlist in capabilities |
| **No free-text → action** | ✅ | `_grounded_decide` JSON-only; `enforce_grounded_text()` on thoughts |

---

## Control-plane invariants

| Invariant | Status | Module |
|-----------|--------|--------|
| Physics gate before cognition | ✅ | `physics_gate.py` + `agent_runner.py` |
| Circuit breaker per agent/hour | ✅ | `circuit_breaker.py` wired in runner, messaging, graphs |
| Grounding on thoughts + dreams | ✅ | `grounding.py` |
| Message type taxonomy | ✅ | `messaging.py` `VALID_MESSAGE_TYPES` |
| Rent before death path visible | ✅ | throttle events + rent daemon |

---

## Verification commands

```bash
python3 scripts/spot-check-grounding.py --sample 20
python3 -m pre_commit run --all-files
bash scripts/benchmark-scale.sh
```

Field operator: 1h autonomy soak at 500 agents with `[FIELD-DATA] T-AUTO-01` sign-off.

---

## Gaps (non-blocking)

- External **write** paths remain x402-gated (by design until tier unlock).
- Formal pytest suite for autonomy axes (planned `runtime/tests/`).

Close issue #10 when field soak passes; code audit is **complete** as of this doc.
