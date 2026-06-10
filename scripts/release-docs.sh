#!/usr/bin/env bash
# release-docs.sh — bundle docs/ into a versioned zip for GitHub Releases.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
  VERSION="$(tr -d '[:space:]' < docs/VERSION)"
fi

if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
  echo "Invalid version: $VERSION (expected semver, e.g. 1.0.0)" >&2
  exit 1
fi

STAGING="dist/god-docs-${VERSION}"
ARCHIVE="dist/god-docs-${VERSION}.zip"
NOTES="dist/release-notes.md"

rm -rf "$STAGING" "$ARCHIVE"
mkdir -p "$STAGING" dist

copy_if_exists() {
  local src="$1"
  local dest="$2"
  if [[ -f "$src" ]]; then
    cp "$src" "$dest"
  fi
}

# Core documentation tree
cp -R docs/. "$STAGING/docs/"
copy_if_exists README.md "$STAGING/README.md"
copy_if_exists CLAUDE.md "$STAGING/CLAUDE.md"
copy_if_exists PROGRESS.md "$STAGING/PROGRESS.md"

GIT_SHA="$(git rev-parse HEAD)"
GIT_SHORT="$(git rev-parse --short HEAD)"
DOC_COUNT="$(find "$STAGING/docs" -name '*.md' | wc -l | tr -d ' ')"
BUILT_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

python3 - <<PY
import hashlib
import json
import pathlib

staging = pathlib.Path("${STAGING}")
files = []
for path in sorted(staging.rglob("*")):
    if not path.is_file():
        continue
    rel = path.relative_to(staging).as_posix()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    files.append({"path": rel, "sha256": digest, "bytes": path.stat().st_size})

manifest = {
    "name": "god-documentation",
    "version": "${VERSION}",
    "git_sha": "${GIT_SHA}",
    "git_short": "${GIT_SHORT}",
    "built_at": "${BUILT_AT}",
    "doc_count": int("${DOC_COUNT}"),
    "files": files,
}
(staging / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
PY

(
  cd dist
  zip -rq "$(basename "$ARCHIVE")" "$(basename "$STAGING")"
)

PREV_TAG="$(git describe --tags --match 'docs-v*' --abbrev=0 HEAD^ 2>/dev/null || true)"
LOG_RANGE=""
if [[ -n "$PREV_TAG" ]]; then
  LOG_RANGE="${PREV_TAG}..HEAD"
else
  LOG_RANGE="HEAD"
fi

{
  echo "# Documentation v${VERSION}"
  echo
  echo "- **Commit:** \`${GIT_SHORT}\`"
  echo "- **Built:** ${BUILT_AT}"
  echo "- **Documents:** ${DOC_COUNT} markdown files"
  echo "- **Archive:** \`god-docs-${VERSION}.zip\`"
  echo
  echo "## Changes since last docs release"
  echo
  if [[ -n "$PREV_TAG" ]]; then
    git log --pretty=format:'- %s (%h)' "$LOG_RANGE" -- docs/ README.md CLAUDE.md PROGRESS.md || true
  else
    echo "- Initial documentation release bundle"
  fi
  echo
} > "$NOTES"

echo "$VERSION" > docs/VERSION

echo "Built ${ARCHIVE} (${DOC_COUNT} docs, sha ${GIT_SHORT})"
