# Documentation Release Process

> Versioned snapshots of the design corpus ship as GitHub Releases. Runtime code releases are separate.

---

## What gets released

Each documentation release bundles:

- All files under `docs/`
- `README.md`, `CLAUDE.md`, `PROGRESS.md` (when present)
- `MANIFEST.json` — file list, SHA-256 hashes, doc count, git SHA, build timestamp

Archive name: `god-docs-<version>.zip`

---

## Version file

Current docs version lives in [`docs/VERSION`](./VERSION) (semver: `MAJOR.MINOR.PATCH`).

Bump `docs/VERSION` when cutting a release (the release script writes it back on build).

---

## Cut a release (maintainer)

```bash
git pull --rebase origin main   # or your integration branch
bash scripts/bootstrap-dev.sh   # once per machine
pre-commit run --all-files      # must pass before tagging

# Bump docs/VERSION if needed, commit, push
git add docs/VERSION
git commit -m "docs: bump documentation version to X.Y.Z"
git push

git tag docs-vX.Y.Z
git push origin docs-vX.Y.Z
```

Pushing a `docs-v*` tag triggers [`.github/workflows/docs-release.yml`](../.github/workflows/docs-release.yml), which builds the zip and publishes a GitHub Release.

### Manual workflow dispatch

In GitHub Actions → **docs-release** → **Run workflow**, optionally pass a version override.

---

## Pre-commit (required)

All contributors must pass pre-commit before merge. CI blocks PRs that fail.

```bash
bash scripts/bootstrap-dev.sh          # installs git hooks
pre-commit run --all-files             # run full check locally
```

Hooks cover: whitespace, YAML/JSON, private keys, Python (ruff), shellcheck, Dockerfiles, no direct commits to `main`.

---

## Consumer download

1. Open [GitHub Releases](https://github.com/ma-za-kpe/god/releases)
2. Download `god-docs-<version>.zip`
3. Verify `MANIFEST.json` hashes if needed

---

## Links

- [Changelog & design decisions](./46-changelog.md)
- [Local development environment](./37-local-development-environment.md)
