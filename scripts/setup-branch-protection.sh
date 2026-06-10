#!/usr/bin/env bash
# Configure GitHub branch protection for main + develop.
# Requires: gh CLI, repo admin. Idempotent best-effort.
set -euo pipefail

REPO="${GITHUB_REPO:-ma-za-kpe/god}"
OWNER="${REPO%%/*}"
NAME="${REPO##*/}"

if ! command -v gh >/dev/null 2>&1; then
  echo "ERROR: gh CLI required" >&2
  exit 1
fi

protect_branch() {
  local branch="$1"
  local payload
  echo "== Protecting ${branch} =="
  payload=$(cat <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["Run pre-commit hooks", "Secret scan (gitleaks)", "Python SAST (bandit)"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 0,
    "dismiss_stale_reviews": true
  },
  "restrictions": null,
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON
)
  if gh api "repos/${OWNER}/${NAME}/branches/${branch}/protection" -X PUT --input - <<<"${payload}"; then
    echo "OK: ${branch}"
  else
    echo "WARN: protection API failed for ${branch} — set rules manually in GitHub UI" >&2
  fi
}

for b in main develop; do
  if gh api "repos/${OWNER}/${NAME}/branches/${b}" >/dev/null 2>&1; then
    protect_branch "$b"
  else
    echo "SKIP: branch ${b} does not exist on remote yet"
  fi
done

echo "== Done. Verify in GitHub → Settings → Branches =="
