#!/usr/bin/env bash
# Monitor PR #63 for new comments and branch pushes. Field gate only — no stack commands.
set -euo pipefail

REPO="ma-za-kpe/god"
PR=63
BRANCH="fix/phase1-death-x402-onchain"
BASE_SHA="12762ece73146f4ec5baad85b9dc3e31bbc6cc7f"
LOG="${MONITOR_LOG:-field-reports/pr63-monitor.log}"
STATE="${MONITOR_STATE:-field-reports/pr63-monitor.state}"
INTERVAL="${MONITOR_INTERVAL_SEC:-90}"

mkdir -p "$(dirname "$LOG")" "$(dirname "$STATE")"

last_comment_id=""
last_sha=""
if [[ -f "$STATE" ]]; then
  # shellcheck disable=SC1090
  source "$STATE"
fi

log() {
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" | tee -a "$LOG"
}

save_state() {
  cat >"$STATE" <<EOF
last_comment_id=${last_comment_id}
last_sha=${last_sha}
EOF
}

current_sha() {
  git ls-remote "https://github.com/${REPO}.git" "refs/heads/${BRANCH}" 2>/dev/null | awk '{print $1}' || true
}

evidence_count() {
  gh api "repos/${REPO}/contents/field-reports?ref=${BRANCH}" \
    --jq '[.[].name]|map(select(test("phase1-evidence")))|length' 2>/dev/null || echo 0
}

latest_comment() {
  gh api "repos/${REPO}/issues/${PR}/comments" \
    --jq 'sort_by(.created_at)|last|{id: (.id|tostring), author: .user.login, created: .created_at, preview: .body[0:120]}' 2>/dev/null || true
}

log "monitor start pr=${PR} branch=${BRANCH} interval=${INTERVAL}s"

while true; do
  sha=$(current_sha)
  evid=$(evidence_count)
  comment_json=$(latest_comment)

  if [[ -n "$comment_json" && "$comment_json" != "null" ]]; then
    cid=$(echo "$comment_json" | jq -r '.id')
    author=$(echo "$comment_json" | jq -r '.author')
    created=$(echo "$comment_json" | jq -r '.created')
    preview=$(echo "$comment_json" | jq -r '.preview' | tr '\n' ' ')

    if [[ "$cid" != "$last_comment_id" && -n "$last_comment_id" ]]; then
      log "NEW_COMMENT id=${cid} author=${author} created=${created}"
      log "  preview: ${preview}"
    fi
    last_comment_id="$cid"
  fi

  if [[ "$sha" != "$last_sha" && -n "$last_sha" ]]; then
    log "BRANCH_PUSH old=${last_sha:0:7} new=${sha:0:7} evidence_files=${evid}"
  elif [[ -n "$sha" && "$sha" != "$BASE_SHA" && "$last_sha" == "$BASE_SHA" ]]; then
    log "BRANCH_PUSH base_cleared new=${sha:0:7} evidence_files=${evid}"
  fi

  if [[ "$evid" != "0" && "${last_evid:-0}" == "0" ]]; then
    log "EVIDENCE_FILES appeared count=${evid} sha=${sha:0:7}"
  fi
  last_evid=$evid
  last_sha="${sha:-$last_sha}"

  save_state
  echo "last_comment_id=${last_comment_id}" >>"$STATE"
  echo "last_sha=${last_sha}" >>"$STATE"
  echo "last_evid=${last_evid:-0}" >>"$STATE"

  sleep "$INTERVAL"
done