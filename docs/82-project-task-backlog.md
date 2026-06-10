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
| R1 | Understand project, audits, fixes on `feat/p0-manifesto-and-scaling`, PR #1 | ✅ | merged #13→develop, #14→main |
| R2 | Deepen local agent autonomy (env, jobs, tools, mutations) | ✅ | doc 77, modules landed |
| R3 | Always `git pull` before push; monitor PR comments | 🔄 | standing order — see Agent standing orders |
| R4 | Field test 5000 agents, no lag; PR comment protocol | ⏳ | [doc 78](./78-pr-field-test-protocol.md), was #4 (closed — reopen on field data) |
| R5 | Hallucinations must not happen — live world only | 🔄 | grounding.py, was #8 (closed — field validation ongoing) |
| R6 | Field operator: **WAIT** for `[AGENT-READY]` before rebuild | ✅ | doc 78 |
| R7 | Field operator: **LOGS** on every `[FIELD-*]` report | ✅ | doc 78 |
| R8 | Docs release pipeline + pre-commit enforced | ✅ | docs 79, CI |
| R9 | Agent is boss — branches, issues, manifesto-bound | ✅ | issues #2–#12 closed; `develop` live |
| R10 | Docs-first before tasks; operator runs pre-commit; watch CI; save Actions credits | ✅ | CLAUDE.md, doc 78 |
| R11 | UI must buzz — transactions, movement, flicker, concurrent WS | ✅ | observer @ c8339b5, was #11 |
| R12 | Open source everything; no key leaks; security audit | ✅ | MIT, doc 80, was #12 |
| R13 | **Brand theme, logo, guidelines; reflect in UI; world logs in observer** | ✅ | [doc 81](./81-brand-guidelines.md), `brand.css`, `index.html` + `maku.html`, WORLD LOG tab |
| R14 | **Keep all requests in this task list** | ✅ | this file |
| R15 | **Open-source contribution guidelines + airtight git workflow; protect branches; close all issues** | ✅ | CONTRIBUTING.md, doc 83, protection on main+develop |
| R16 | **Tie AI-driven economy + governance; refresh memory from docs** | ✅ | doc 85 system map |
| R17 | **Agentic economic activity — transact, negotiate, settle deals** | ✅ | economic_activity.py, buy_service, offer/acceptance |
| R18 | **Watch PR/comments, continue work, monitor CI** | 🔄 | no extra sync ritual — PR #1 + CI watch |
| R19 | **Observer UI lagging — field operator logs + track** | ⏳ | T-OBS-LAG-01 · **[FIELD-DATA]** 2026-06-10: host RAM 91.7% (Ollama 5.6 GB), containers healthy — not malice |
| R20 | **Never forget creator requests — track here or open GH issue** | ✅ | R14 + this backlog |
| R21 | **Always update progress docs when shipping work** | ✅ | PROGRESS.md, changelog, this backlog |

---

## Engineering queue (priority)

| P | Task | Issue | Status |
|---|------|-------|--------|
| P0 | Physics gate — rent before cognition | #2 | ✅ closed |
| P0 | T-5000-01 Phase A scale test | #4 | ⏳ field pending |
| P1 | Message type taxonomy | #5 | ✅ closed |
| P1 | Inbox salience at scale | #3 | ✅ closed |
| P1 | Hallucination grounding hardening | #8 | 🔄 field validation |
| P1 | Observer live UI at scale verify | #11 | ✅ closed |
| P1 | Observer performance / lag at scale | #16 | ⏳ T-OBS-LAG-01 |
| P2 | Reproduction 5× rent (Law 6) | #7 | ✅ closed |
| P2 | Circuit breakers | #9 | ✅ closed |
| P2 | Narrator / drama feed | #6 | ✅ closed |
| P3 | Autonomy 100% audit | #10 | ✅ closed |

---

## Field operator (standing orders)

1. **WAIT** for `[AGENT-READY] T-xxx @ <sha>` before rebuild
2. **`git pull --rebase`** before every push
3. Run `python3 -m pre_commit run --all-files` after every pull
4. Include **runtime logs** in every `[FIELD-*]` report
5. Never commit field JSON/log dumps

---

## Agent standing orders

1. Reread manifesto + autonomy + audit + task-specific doc before each task
2. **`git pull --rebase origin <branch>` before every push** — never push on stale branch
3. Pre-commit locally before every push; watch CI once
4. Update **this file** when creator adds a new request (or open a GH issue)
5. Update **[PROGRESS.md](../PROGRESS.md)** and **[changelog](./46-changelog.md)** when shipping meaningful work
6. Post `[AGENT-REQUEST]` / `[AGENT-READY]` on PR #1 for field work
