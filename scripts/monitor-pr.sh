#!/usr/bin/env bash
# monitor-pr.sh — Poll a GitHub PR for activity (commits, reviews, CI, state).
# Usage: ./scripts/monitor-pr.sh [PR_NUMBER] [INTERVAL_SECONDS]
set -euo pipefail

PR="${1:-1}"
INTERVAL="${2:-300}"
LOG_DIR="${HOME}/.grok/plugin-data/pr-babysit"
LOG_FILE="${LOG_DIR}/monitor-pr-${PR}.log"
STATE_FILE="${LOG_DIR}/monitor-pr-${PR}-state.json"

mkdir -p "$LOG_DIR"

log() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$LOG_FILE"
}

init_state() {
  if [[ ! -f "$STATE_FILE" ]]; then
    echo '{"last_commit":"","last_updated":"","last_ci":"","last_state":"OPEN","last_review_count":0,"last_comment_count":0}' > "$STATE_FILE"
  fi
}

read_state() {
  python3 -c "import json; print(json.load(open('$STATE_FILE')).get('$1',''))" 2>/dev/null || echo ""
}

write_state() {
  python3 <<PY
import json, os
path = os.path.expanduser("$STATE_FILE")
data = json.load(open(path)) if os.path.exists(path) else {}
data.update($1)
json.dump(data, open(path, "w"), indent=2)
PY
}

check_pr() {
  local json
  json=$(gh pr view "$PR" --json title,state,updatedAt,commits,comments,reviews,statusCheckRollup,url,headRefName 2>/dev/null) || {
    log "ERROR: failed to fetch PR #$PR"
    return 1
  }

  local title state updated url branch
  title=$(echo "$json" | python3 -c "import sys,json; print(json.load(sys.stdin)['title'])")
  state=$(echo "$json" | python3 -c "import sys,json; print(json.load(sys.stdin)['state'])")
  updated=$(echo "$json" | python3 -c "import sys,json; print(json.load(sys.stdin)['updatedAt'])")
  url=$(echo "$json" | python3 -c "import sys,json; print(json.load(sys.stdin)['url'])")
  branch=$(echo "$json" | python3 -c "import sys,json; print(json.load(sys.stdin)['headRefName'])")

  local last_commit commit_count head_oid
  commit_count=$(echo "$json" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['commits']))")
  head_oid=$(echo "$json" | python3 -c "import sys,json; c=json.load(sys.stdin)['commits']; print(c[-1]['oid'] if c else '')")

  local review_count comment_count
  review_count=$(echo "$json" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['reviews']))")
  comment_count=$(echo "$json" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['comments']))")

  local ci_summary
  ci_summary=$(echo "$json" | python3 -c "
import sys, json
checks = json.load(sys.stdin).get('statusCheckRollup') or []
parts = []
for c in checks:
    name = c.get('name','?')
    concl = c.get('conclusion') or c.get('status','?')
    parts.append(f'{name}:{concl}')
print('; '.join(parts) if parts else 'no-checks')
")

  local prev_commit prev_updated prev_ci prev_state prev_reviews prev_comments
  prev_commit=$(read_state last_commit)
  prev_updated=$(read_state last_updated)
  prev_ci=$(read_state last_ci)
  prev_state=$(read_state last_state)
  prev_reviews=$(read_state last_review_count)
  prev_comments=$(read_state last_comment_count)

  local activity=0

  if [[ "$state" != "$prev_state" && -n "$prev_state" ]]; then
    log "STATE CHANGE: $prev_state → $state | $title"
    activity=1
  fi

  if [[ "$head_oid" != "$prev_commit" && -n "$prev_commit" ]]; then
    local msg
    msg=$(echo "$json" | python3 -c "import sys,json; c=json.load(sys.stdin)['commits']; print(c[-1].get('messageHeadline','') if c else '')")
    log "NEW COMMIT on $branch: ${msg:0:80} ($head_oid)"
    activity=1
  fi

  if [[ "$updated" != "$prev_updated" && -n "$prev_updated" && "$head_oid" == "$prev_commit" ]]; then
    log "PR UPDATED (no new commit): $updated"
    activity=1
  fi

  if [[ "$review_count" != "$prev_reviews" && -n "$prev_reviews" ]]; then
    log "REVIEWS: $prev_reviews → $review_count"
    activity=1
  fi

  if [[ "$comment_count" != "$prev_comments" && -n "$prev_comments" ]]; then
    log "COMMENTS: $prev_comments → $comment_count"
    activity=1
  fi

  if [[ "$ci_summary" != "$prev_ci" && -n "$prev_ci" ]]; then
    log "CI CHANGE: $prev_ci → $ci_summary"
    activity=1
  fi

  if [[ $activity -eq 0 ]]; then
    log "OK #$PR | $state | commits=$commit_count | CI: $ci_summary"
  fi

  write_state "{'last_commit': '$head_oid', 'last_updated': '$updated', 'last_ci': '''$ci_summary''', 'last_state': '$state', 'last_review_count': $review_count, 'last_comment_count': $comment_count}"

  if [[ "$state" == "MERGED" || "$state" == "CLOSED" ]]; then
    log "PR #$PR is $state — monitor stopping. $url"
    exit 0
  fi
}

init_state
log "Starting PR monitor: #$PR every ${INTERVAL}s → $LOG_FILE"
log "PR URL: $(gh pr view "$PR" --json url -q .url)"

while true; do
  check_pr || true
  sleep "$INTERVAL"
done