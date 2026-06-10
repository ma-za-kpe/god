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

---

## Engineering queue (priority)

| P | Task | Issue |
|---|------|-------|
| P0 | Physics gate — rent before cognition | #2 |
| P0 | T-5000-01 Phase A scale test | #4 |
| P1 | Message type taxonomy | #5 |
| P1 | Inbox salience at scale | #3 |
| P1 | Hallucination grounding hardening | #8 |
| P1 | Observer live UI at scale verify | #11 |
| P2 | Reproduction 5× rent (Law 6) | #7 |
| P2 | Circuit breakers | #9 |
| P2 | Narrator / drama feed | #6 |
| P3 | Autonomy 100% audit | #10 |

---

## Field operator (standing orders)

1. **WAIT** for `[AGENT-READY] T-xxx @ <sha>` before rebuild
2. Run `python3 -m pre_commit run --all-files` after every pull
3. Include **runtime logs** in every `[FIELD-*]` report
4. Never commit field JSON/log dumps

---

## Agent standing orders

1. Reread manifesto + autonomy + audit + task-specific doc before each task
2. Pre-commit locally before every push; watch CI once
3. Update **this file** when creator adds a new request
4. Post `[AGENT-REQUEST]` / `[AGENT-READY]` on PR #1 for field work
