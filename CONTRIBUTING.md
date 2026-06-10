# Contributing to GOD

Thank you for helping build **Genesis of Digital Life**. This is an ecology, not a nursery — contributions must preserve adversarial signals, structured actuation, and manifesto doctrine.

Read first:

- [Ecology Hardening Manifesto](./docs/74-ecology-hardening-manifesto.md)
- [Git workflow](./docs/83-git-workflow.md)
- [Brand guidelines](./docs/81-brand-guidelines.md)
- [SECURITY.md](./SECURITY.md) — never commit keys

---

## Quick start

```bash
git clone https://github.com/ma-za-kpe/god.git
cd god
cp .env.example .env.local          # edit locally; never commit
bash scripts/bootstrap-dev.sh       # pre-commit hooks
python3 -m pre_commit run --all-files
bash scripts/security-audit.sh      # before every push
docker compose up -d
```

---

## Branch model (Gitflow)

| Branch | Purpose | Merge target | Direct push |
|--------|---------|--------------|-------------|
| `main` | Production / releases | — | **No** (maintainers via PR only) |
| `develop` | Integration | `main` (release PRs) | **No** |
| `feat/*` | Features | `develop` | Yes (your fork or feature branch) |
| `fix/*` | Bug fixes | `develop` | Yes |
| `docs/*` | Documentation only | `develop` | Yes |
| `chore/*` | CI, tooling, deps | `develop` | Yes |

**Never commit to `main` or `develop` locally** — pre-commit blocks `main`; CI + branch protection enforce both.

### Typical flow

```bash
git fetch origin
git checkout develop
git pull origin develop
git checkout -b feat/my-change

# … edit …
python3 -m pre_commit run --all-files
bash scripts/security-audit.sh
git push -u origin feat/my-change
gh pr create --base develop --title "feat: …" --body "Closes #N"
```

After review and green CI, merge to `develop`. Release batches merge `develop` → `main` with a version tag.

---

## Pull requests

1. **One concern per PR** — link the GitHub issue (`Closes #N`).
2. **Docs-first** — if behavior changes, update the canonical doc before code.
3. **Pre-commit must pass** locally and in CI.
4. **No secrets** — `.env.local`, `swarm.key`, wallet JSON stay gitignored.
5. **No field dumps** — never commit `field-*.json`, operator log captures, or bulk agent exports.
6. **Manifesto check** — raw signals visible; actions gated; no free-text → execution.

### PR title format

```
feat(scope): short description
fix(scope): …
docs: …
chore(ci): …
```

### Review expectations

- Physics / rent changes: cite Law 0 in [doc 14](./docs/14-immutable-physics-laws.md).
- Autonomy changes: update [doc 77](./docs/77-agent-autonomy-local.md) checklist.
- Observer changes: match [brand guidelines](./docs/81-brand-guidelines.md).

---

## Commits

- Imperative mood: `feat(observer): add world log tab`
- Batch fixes; avoid empty commits or re-push to re-run CI.
- Feature branches rely on **PR checks only** (no duplicate push workflows).

---

## Code areas

| Path | Role |
|------|------|
| `runtime/src/` | Agent runtime, physics, messaging, grounding |
| `observer/` | Public glass-box UI |
| `contracts/` | On-chain rent / USDC |
| `docs/` | Canonical specs (prefer one doc, link don't duplicate) |
| `scripts/` | Operator and CI helpers |

Python style: **ruff** (enforced by pre-commit). Shell: **shellcheck**.

---

## Security

- Report vulnerabilities per [SECURITY.md](./SECURITY.md).
- Run `bash scripts/security-audit.sh` before push.
- Production endpoints require `CREATOR_GENESIS_TOKEN`; never disable gates in committed config.

---

## Field testing

Scale and autonomy soaks use [doc 78](./docs/78-pr-field-test-protocol.md). Field operators post `[FIELD-*]` on the PR with **runtime logs**. Coding agents post `[AGENT-READY]` before rebuild.

---

## Governance

Maintainers merge to `develop` and `main`. All creator requests are tracked in [docs/82-project-task-backlog.md](./docs/82-project-task-backlog.md). New work should have a GitHub issue with priority label (`P0`–`P3`).

Questions: open a GitHub Discussion or issue.
