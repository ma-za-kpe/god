# Security Policy

GOD is **open source** (MIT). Operators run their own worlds with real economic stakes — treat secrets, keys, and production endpoints accordingly.

## Supported versions

| Branch | Supported |
|--------|-----------|
| `main` | yes |
| `feat/*` | best-effort during active PRs |

## Reporting a vulnerability

**Do not** open public GitHub issues for exploitable security bugs.

1. Email or DM the repository owner (see GitHub profile) with **GOD Security** in the subject.
2. Include: description, reproduction steps, impact, and suggested fix if known.
3. Expect acknowledgment within **72 hours**.

We will coordinate disclosure after a fix is available. Responsible disclosure is appreciated.

## What must never be committed

| Secret | Location |
|--------|----------|
| LLM API keys | `.env.local` only |
| `swarm.key` | generated locally (`scripts/generate-swarm-key.py`) |
| Agent wallet private keys | `data/agent_wallets.json` (gitignored) |
| Creator / deployer keys | env vars only |
| `PINATA_JWT`, `FILEBASE_KEY` | `.env.local` only |

CI runs **GitGuardian**, **gitleaks**, and **detect-private-key** on every PR.

## Local development vs production

| Setting | Local default | Production |
|---------|---------------|------------|
| `LOCAL_DEV_MODE` | `true` | **`false`** |
| `ALLOW_INSECURE_LOCAL_ENDPOINTS` | `true` | **`false`** |
| `CREATOR_GENESIS_TOKEN` | unset (open on localhost) | **required** strong random token |
| `POSTGRES_PASSWORD` | change from default | strong unique password |

Endpoints gated when `ALLOW_INSECURE_LOCAL_ENDPOINTS=false`:

- `POST /tokens/deploy` (accepts private key in body — local dev only)

`POST /creator/genesis` requires `X-Creator-Token` header when `CREATOR_GENESIS_TOKEN` is set.

## Security audit

See [docs/80-open-source-security-audit.md](./docs/80-open-source-security-audit.md) for the full audit log and remediation status.

## Running checks locally

```bash
bash scripts/bootstrap-dev.sh
python3 -m pre_commit run --all-files
bash scripts/security-audit.sh
```
