# Project Task Backlog

> **Canonical list of creator/operator requests** — the coding agent updates this so nothing is forgotten. GitHub issues track execution; this doc tracks intent.

**Last updated:** 2026-06-11 (Phase 1 issues closed; 14-day soak gate remains)

---

## Legend

| Status | Meaning |
|--------|---------|
| ✅ | Done |
| 🔄 | In progress |
| ⏳ | Waiting (field operator / merge) |
| 📋 | Planned |

---

## Deploy gate (creator rule — non-negotiable)

**No public deploy** (Base mainnet, public observer host, E2B production, or any off-localhost stack) until **every Phase 1 GitHub issue is CLOSED**.

Track: [github.com/ma-za-kpe/god/issues](https://github.com/ma-za-kpe/god/issues)

### Phase 1 issues (must all be ✅ CLOSED before deploy)

| Issue | Title | Status |
|-------|-------|--------|
| #2 | Physics gate — rent before cognition | ✅ CLOSED |
| #3 | Inbox salience at scale | ✅ CLOSED |
| #4 | T-5000-01 Phase A scale test | ✅ CLOSED |
| #5 | Message type taxonomy | ✅ CLOSED |
| #6 | Minimal narrator | ✅ CLOSED |
| #7 | Reproduction 5× rent (Law 6) | ✅ CLOSED |
| #8 | Hallucination grounding | ✅ CLOSED |
| #9 | Circuit breakers | ✅ CLOSED |
| #10 | Autonomy 100% audit | ✅ CLOSED |
| #11 | Observer live buzz UI | ✅ CLOSED |
| #12 | Open source + security baseline | ✅ CLOSED |
| #16 | Observer performance / lag (T-OBS-LAG-01) | ✅ CLOSED |
| #25 | Episodic memory commit pipeline | ✅ CLOSED |

### Deploy still blocked (creator rule)

Phase 1 **issues are closed**, but **no public deploy** until [doc 73](./73-phase1-deployment-checklist.md) §G (**14-day local stability soak**) passes.

### Not Phase 1 (blocked until soak + gate above)

#18, #19, #20, #21, #22, #23, #24 — Phase 2+ only.

---

## Creator requests (chronological)

| # | Request | Status | Notes / issue |
|---|---------|--------|---------------|
| R1 | Understand project, audits, fixes on `feat/p0-manifesto-and-scaling`, PR #1 | ✅ | PR #1 + #13 merged to `main` / `develop` |
| R2 | Deepen local agent autonomy (env, jobs, tools, mutations) | ✅ | doc 77, modules landed |
| R3 | Always `git pull`; monitor PR comments | 🔄 | ongoing |
| R4 | Field test 5000 agents, no lag; PR comment protocol | ⏳ | [doc 78](./78-pr-field-test-protocol.md), #4 |
| R5 | Hallucinations must not happen — live world only | 🔄 | grounding.py, #8, PR #26; field soak via T-HALL-LOG-01 |
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
| R18 | **Watch PR/comments, continue work, monitor CI** | 🔄 | active task PRs on `develop` + CI watch |
| R19 | **Observer UI lagging — field operator logs + track** | ✅ | #16 closed; LITE + WS keepalive (PR #27, #33) |
| R20 | **Never forget creator requests — track here or open GH issue** | ✅ | this backlog |
| R21 | **Always update progress docs when shipping work** | ✅ | PROGRESS.md, changelog |
| R22 | **Onboard new field operator — handoff PR + status report** | ✅ | doc 86, PR #17 investigation closed; future work via PR comments |
| R23 | **Stable locally before deploy — all Phase 1 GH issues closed** | 🔄 | issues closed; **14-day soak** + hallucination field audit remain; see [doc 87](./87-phase2-brainstorm.md) |

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

### Phase 1 shipped (issues closed — soak + audit remain)

| P | Task | Issue | Notes |
|---|------|-------|-------|
| P1 | Observer perf / lag at scale | **#16** ✅ | LITE + WS keepalive on `develop` |
| P1 | Episodic memory commit pipeline | **#25** ✅ | `episodic_memory.py` on `develop` |
| — | Money in circulation + top-earner monitor | R23 | ✅ shipped PR #27 |
| — | Hallucination / recipient grounding | R5, #8 | ✅ shipped PR #26; field log audit pending |
| — | Schema repair | PR #28 | ✅ merged |
| — | WS Decimal / keepalive | PR #33 | ✅ merged |
| — | README logo + doc sync | — | PR in flight |

### Deferred — Phase 2+ (brainstorm only)

See [doc 87 — Phase 2 brainstorm](./87-phase2-brainstorm.md): E2B Startups, top-earner reproduction gate, Akash, public host.

### Open — not built yet (post–Phase 1 gate)

| P | Task | Issue |
|---|------|-------|
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
4. Post `[AGENT-REQUEST]` / `[AGENT-READY]` on the **active task PR** for field work
