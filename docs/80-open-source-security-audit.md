# Open Source & Security Audit

> **Date:** 2026-06-10
> **Scope:** Repository hygiene, secret leakage, endpoint exposure, dependency surface
> **License:** MIT (see [LICENSE](../LICENSE))
> **Status:** Initial audit + remediations on `develop` (merged via PR #13 / #1)

---

## Executive summary

The project is now **explicitly open source** under MIT. Documentation, runtime, contracts, observer, and scripts are intended for public collaboration.

**No production secrets were found in tracked source.** Remaining risks are **operational** (operators committing `.env.local`, exposing local-only endpoints on the public internet) — addressed via gitignore, CI scanners, and production env gates.

| Area | Grade | Notes |
|------|-------|-------|
| License & openness | **A** | MIT added; README signpost |
| Secret scanning (CI) | **A-** | GitGuardian + gitleaks + detect-private-key |
| Git hygiene | **B+** | Field dumps removed; `.claude/` gitignored |
| Endpoint hardening | **B** | Local-only gates added; genesis token optional |
| Dependency audit | **B** | `pip-audit` in CI; pin in Docker |
| Wallet key handling | **C+** | Local JSON store — documented; not for production |

---

## Audit findings

### ✅ Clean

- **`.env.local` / `swarm.key` / `data/agent_wallets.json`** — gitignored; not in history on current branch
- **API keys in code** — read from `os.getenv()` only; `.env.example` uses empty placeholders
- **Anvil test key in README** — public Foundry default (account #0); allowlisted in gitleaks (not a leak)
- **Ecology docs** — no credentials in markdown corpus

### ⚠️ Fixed in this audit

| ID | Finding | Remediation |
|----|---------|-------------|
| S1 | Field operator JSON/log dumps committed | Removed from git; expanded `.gitignore` |
| S2 | `.claude/settings.local.json` tracked | Gitignored; removed from index |
| S3 | `POST /tokens/deploy` accepts raw private key | Gated by `ALLOW_INSECURE_LOCAL_ENDPOINTS` |
| S4 | `POST /creator/genesis` destructive, no auth | `CREATOR_GENESIS_TOKEN` + `X-Creator-Token` when set |
| S5 | No LICENSE file | MIT [LICENSE](../LICENSE) |
| S6 | No security reporting path | [SECURITY.md](../SECURITY.md) |

### ⚠️ Accepted local-dev debt (documented, not for production)

| ID | Finding | Mitigation |
|----|---------|------------|
| L1 | `wallet_store.py` stores agent private keys on disk | `chmod 600`; path gitignored; production → HSM/MPC per doc 24 |
| L2 | `ENABLE_EXTERNAL_FETCH=true` default | Allowlist localhost only; disable in production |
| L3 | Postgres password default `localdev` | Documented change required for prod |
| L4 | Observer on `localhost:8888` no auth | Public read-only by design (doc 06); do not expose without firewall |

### 🔲 Future work

- Signed container images for releases
- `CREATOR_GENESIS_TOKEN` required when `LOCAL_DEV_MODE=false` (hard fail)
- Rate-limit public observer WebSocket at edge
- `pip-audit` / `forge` dependency pinning in SBOM
- Optional: bounty program after mainnet

---

## Enforcement stack

| Layer | Tool |
|-------|------|
| Pre-commit | `detect-private-key`, gitleaks |
| PR CI | pre-commit, GitGuardian, gitleaks, bandit, pip-audit |
| Operator | `bash scripts/security-audit.sh` before push |
| Runtime | `runtime/src/security.py` env gates |

---

## Operator checklist (before going public on the internet)

```bash
# 1. Never commit secrets
cp .env.example .env.local   # fill keys locally only

# 2. Production env
LOCAL_DEV_MODE=false
ALLOW_INSECURE_LOCAL_ENDPOINTS=false
CREATOR_GENESIS_TOKEN=<openssl rand -hex 32>
POSTGRES_PASSWORD=<strong>

# 3. Scan
bash scripts/security-audit.sh
```

---

## Branch protection

After `develop` exists on GitHub, run `bash scripts/setup-branch-protection.sh` (requires `gh` + admin). See [git workflow](./83-git-workflow.md).

---

## Links

- [Creator key security](./24-creator-key-security.md)
- [Human threat model](./33-human-threat-model.md)
- [Ecology manifesto](./74-ecology-hardening-manifesto.md)
