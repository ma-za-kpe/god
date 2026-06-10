#!/usr/bin/env bash
# watch-ci.sh — wait for the latest pre-commit workflow on current branch (one shot).
# Usage: bash scripts/watch-ci.sh [workflow] [timeout_seconds]
set -euo pipefail

WORKFLOW="${1:-pre-commit.yml}"
TIMEOUT="${2:-600}"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI required" >&2
  exit 1
fi

echo "Watching latest run: workflow=${WORKFLOW} branch=${BRANCH} (timeout ${TIMEOUT}s)"

RUN_ID=""
for _ in $(seq 1 30); do
  RUN_ID="$(gh run list --branch "$BRANCH" --workflow "$WORKFLOW" --limit 1 --json databaseId --jq '.[0].databaseId' 2>/dev/null || true)"
  if [[ -n "$RUN_ID" && "$RUN_ID" != "null" ]]; then
    break
  fi
  sleep 2
done

if [[ -z "$RUN_ID" || "$RUN_ID" == "null" ]]; then
  echo "No workflow run found for branch ${BRANCH}. Open a PR or push to main to trigger CI." >&2
  exit 1
fi

gh run view "$RUN_ID" --json status,conclusion,url --jq '"status=" + .status + " conclusion=" + (.conclusion // "pending") + " url=" + .url'

if command -v timeout >/dev/null 2>&1; then
  timeout "$TIMEOUT" gh run watch "$RUN_ID" --exit-status
elif command -v gtimeout >/dev/null 2>&1; then
  gtimeout "$TIMEOUT" gh run watch "$RUN_ID" --exit-status
else
  gh run watch "$RUN_ID" --exit-status
fi
echo "CI finished: run ${RUN_ID}"
