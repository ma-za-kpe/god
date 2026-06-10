# Project Task Backlog

> **Canonical list of creator/operator requests** — the coding agent updates this so nothing is forgotten. GitHub issues track execution; this doc tracks intent.

**Last updated:** 2026-06-10

---

## Legend

| Status | Meaning |
|--------|---------|
| ✅ | Done |
| 🔄 | In progress |
| ⏳ | Waiting (field operator / merge) |
| 📋 | Planned |

---

## Creator requests (chronological)

| # | Request | Status | Notes / issue |
|---|---------|--------|---------------|
| R1 | Understand project, audits, fixes on `feat/p0-manifesto-and-scaling`, PR #1 | 🔄 | PR #1 open |
| R2 | Deepen local agent autonomy (env, jobs, tools, mutations) | ✅ | doc 77, modules landed |
| R3 | Always `git pull`; monitor PR comments | 🔄 | ongoing |
| R4 | Field test 5000 agents, no lag; PR comment protocol | ⏳ | [doc 78](./78-pr-field-test-protocol.md), #4 |
| R5 | Hallucinations must not happen — live world only | 🔄 | grounding.py, #8 |
| R6 | Field operator: **WAIT** for `[AGENT-READY]` before rebuild | ✅ | doc 78 |
| R7 | Field operator: **LOGS** on every `[FIELD-*]` report | ✅ | doc 78 |
| R8 | Docs release pipeline + pre-commit enforced | ✅ | docs 79, CI |
| R9 | Agent is boss — branches, issues, manifesto-bound | ✅ | issues #2–#12 closed; `develop` live |
| R10 | Docs-first before tasks; operator runs pre-commit; watch CI; save Actions credits | ✅ | CLAUDE.md, doc 78 |
| R11 | UI must buzz — transactions, movement, flicker, concurrent WS | ✅ | observer @ c8339b5, #11 |
| R12 | Open source everything; no key leaks; security audit | ✅ | MIT, doc 80, #12 |
| R13 | **Brand theme, logo, guidelines; reflect in UI; world logs in observer** | ✅ | doc 81, observer brand.css + WORLD LOG tab |
| R14 | **Keep all requests in this task list** | ✅ | this file |
| R15 | **Open-source contribution guidelines + airtight git workflow; protect branches; close all issues** | ✅ | CONTRIBUTING.md, doc 83, protection on main+develop |
| R16 | **Tie AI-driven economy + governance; refresh memory from docs** | ✅ | doc 85 system map |
| R17 | **Agentic economic activity — transact, negotiate, settle deals** | ✅ | economic_activity.py, buy_service, offer/acceptance |
| R18 | **Watch PR/comments, continue work, monitor CI** | 🔄 | no extra sync ritual — PR #1 + CI watch |
| R19 | **Observer UI lagging — field operator logs + track** | ⏳ | T-OBS-LAG-01, GH #16; host RAM pressure confirmed |
| R20 | **Never forget creator requests — track here or open GH issue** | ✅ | this backlog |
| R21 | **Always update progress docs when shipping work** | ✅ | PROGRESS.md, changelog |
| R22 | **Onboard new field operator — handoff PR + status report** | ✅ | doc 86, PR #17 investigation closed; future work via PR comments |

---

## Engineering queue (priority)

### Shipped (closed issues — code on `main`)

| P | Task | Issue |
|---|------|-------|
| P0 | Physics gate — rent before cognition | #2 ✅ |
| P1 | Message type taxonomy | #5 ✅ |
| P1 | Inbox salience at scale | #3 ✅ |
| P1 | Hallucination grounding (code) | #8 ✅ — field re-validation pending |
| P1 | Observer live buzz UI | #11 ✅ |
| P2 | Reproduction 5× rent (Law 6) | #7 ✅ |
| P2 | Circuit breakers | #9 ✅ |
| P2 | Template narrator | #6 ✅ |
| P3 | Autonomy 100% audit | #10 ✅ |

### Open — field / near-term

| P | Task | Issue |
|---|------|-------|
| P0 | T-5000-01 Phase A scale test (field) | #4 — reopen when field ready |
| P1 | Observer perf / lag at scale | #16 |
| P1 | Hallucination post-fix field soak | R5 — `spot-check-grounding.py` |
| P1 | New field operator handoff | PR #17, R22 |

### Open — not built yet (2026-06-10)

| P | Task | Issue |
|---|------|-------|
| P1 | Episodic memory commit pipeline | #25 |
| P1 | Public observer host | #21 |
| P2 | E2B agent sandboxes | #19 |
| P2 | Base mainnet deploy | #20 |
| P2 | Governance module (`governance.py`) | #22 |
| P2 | LLM narrative engine (full) | #23 |
| P3 | K8s distributed mesh | #18 |
| P3 | Consciousness detection | #24 |

---

## Field operator (standing orders)

1. **WAIT** for `[AGENT-READY] T-xxx @ <sha>` before rebuild
2. **`git pull --rebase` before every push**
3. Run `python3 -m pre_commit run --all-files` after every pull
4. Include **runtime logs** in every `[FIELD-*]` report
5. Never commit field JSON/log dumps — use [status report template](./templates/FIELD_STATUS_REPORT.md)

---

## Agent standing orders

1. Reread manifesto + autonomy + audit + task-specific doc before each task
2. Pre-commit locally before every push; watch CI once
3. Update **this file** when creator adds a new request
4. Post `[AGENT-REQUEST]` / `[AGENT-READY]` on PR #1 for field work
