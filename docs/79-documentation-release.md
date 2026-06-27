# Release Process

> Versioned snapshots of the design corpus and runtime ship as GitHub Releases. Docs use `docs-v*` tags; runtime uses `v*` semver tags (avoids manual version string edits in code).

This integrates proper releases so version bumps (e.g. for /health and FastAPI) happen via the release workflow, not ad-hoc in source (see previous complaints about 0.1.0 manual bumps).

## Runtime version
Runtime version lives in `runtime/src/VERSION` (semver).

It is read dynamically in `runtime/src/main.py` for:
- FastAPI app version
- `/health` endpoint response

Bump `runtime/src/VERSION` (and sync pyproject.toml if packaging) as part of release PRs. The file travels with the src/ COPY in Dockerfile so containers report the correct version.

pyproject.toml also declares the version for the project metadata.

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

Releases follow gitflow (see docs/83): soak on develop, PR to main, then tag.

### Docs release (docs-v*)
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

### Runtime release (v* semver, non-docs)
```bash
# ... after main merge
# Bump runtime version as part of the release (instead of manual edits)
git add runtime/src/VERSION pyproject.toml
git commit -m "chore: bump runtime version to X.Y.Z for release"
git push

git tag vX.Y.Z
git push origin vX.Y.Z
```

Pushing a `v*` tag (that is not `docs-v*`) triggers [`.github/workflows/release.yml`](../.github/workflows/release.yml) which creates the GitHub Release with generated notes. The runtime health endpoint and FastAPI will report the new version from the bumped file once containers are rebuilt from the tag.

Use workflow_dispatch on the release workflow for overrides if needed.

All pre-commit + security must pass. Branch protection on main/develop enforces reviews and checks.

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
- [Git workflow](./83-git-workflow.md) (tags and release path)
- Runtime version source: `runtime/src/VERSION` (loaded in main.py)
- Docs version source: `docs/VERSION`

## Why this (no more manual bumps)
Previous manual edits to version strings in code (e.g. 0.1.0 in health/FastAPI) are replaced by bumping the VERSION file(s) as part of the release PR + tag. This makes releases the single way to advance versions, integrates with branch protection, pre-commit, and GitHub Releases. Health endpoint now always reflects the released version after rebuild.
