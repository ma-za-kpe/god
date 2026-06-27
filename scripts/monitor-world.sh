#!/usr/bin/env bash
# Stream world logs, DB events, and runtime activity to the terminal.
# Usage: bash scripts/monitor-world.sh [vast-host:port]
#
# With no args, connects to the Vast host from .env.local (VAST_SSH_HOST / VAST_SSH_PORT).
# With an arg like "ssh8.vast.ai:27936", connects directly.

set -euo pipefail

HOST=""
PORT=""

if [ "${1:-}" != "" ]; then
  HOST="${1%%:*}"
  PORT="${1##*:}"
else
  ENV_FILE="$(dirname "$0")/../.env.local"
  if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090
    source "$ENV_FILE" 2>/dev/null || true
    HOST="${VAST_SSH_HOST:-ssh8.vast.ai}"
    PORT="${VAST_SSH_PORT:-27936}"
  else
    HOST="ssh8.vast.ai"
    PORT="27936"
  fi
fi

echo "[monitor] Connecting to ${HOST}:${PORT}..."
echo "[monitor] Streaming: runtime log | DB events | OBS/stream status"
echo "[monitor] Press Ctrl+C to stop."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

ssh -p "$PORT" "root@${HOST}" 'bash -s' << 'REMOTE'
#!/usr/bin/env bash
# On the remote host: tail runtime log + poll DB + poll streaming status

DB_URL="postgresql://god:$(grep POSTGRES_PASSWORD /workspace/god/.env.local | cut -d= -f2)@localhost:5432/god"
PGPASSWORD="$(grep POSTGRES_PASSWORD /workspace/god/.env.local | cut -d= -f2)"

last_event_id=0
last_agent_count=-1
last_stream_check=0

tail_pid=""
cleanup() {
  [ -n "$tail_pid" ] && kill "$tail_pid" 2>/dev/null || true
}
trap cleanup EXIT

# Start tailing the runtime log in background
tail -F /var/log/god/runtime.log 2>/dev/null | grep --line-buffered -v 'httpx\|HTTP Request\|GET /world\|GET /agent\|GET /stats\|GET /events' &
tail_pid=$!

while true; do
  now=$(date +%s)

  # DB: new agents
  agent_count=$(PGPASSWORD="$PGPASSWORD" psql -U god -h localhost -d god -tAc \
    "SELECT COUNT(*) FROM agents WHERE is_alive=true;" 2>/dev/null || echo 0)
  if [ "$agent_count" != "$last_agent_count" ]; then
    echo ""
    echo "◆ AGENTS: ${agent_count} alive"
    PGPASSWORD="$PGPASSWORD" psql -U god -h localhost -d god -c \
      "SELECT current_name, archetype, LEFT(avatar_cid,12) as avatar, LEFT(voice_model_cid,12) as voice, balance_usdc FROM agents WHERE is_alive=true ORDER BY created_at;" \
      2>/dev/null || true
    last_agent_count="$agent_count"
  fi

  # DB: recent events (last 60s)
  new_events=$(PGPASSWORD="$PGPASSWORD" psql -U god -h localhost -d god -tA \
    "SELECT event_id, event_type, LEFT(description,80) FROM events WHERE event_id > $last_event_id ORDER BY event_id LIMIT 10;" \
    2>/dev/null || true)
  if [ -n "$new_events" ]; then
    echo ""
    echo "◆ NEW EVENTS:"
    echo "$new_events" | while IFS='|' read -r eid etype desc; do
      echo "  [${eid}] ${etype}: ${desc}"
      last_event_id="$eid"
    done
    last_event_id=$(echo "$new_events" | tail -1 | cut -d'|' -f1)
  fi

  # OBS/streaming status (every 30s)
  if [ $((now - last_stream_check)) -ge 30 ]; then
    stream_status=$(python3 -c "
import json, sys
try:
    import websocket
    ws = websocket.WebSocket()
    ws.connect('ws://127.0.0.1:4444', timeout=3)
    ws.send(json.dumps({'request-type': 'GetStreamingStatus', 'message-id': '1'}))
    for _ in range(10):
        r = json.loads(ws.recv())
        if r.get('message-id') == '1':
            s = r.get('streaming', False)
            t = r.get('stream-timecode', 'n/a')
            print(f'streaming={s} timecode={t}')
            break
    ws.close()
except Exception as e:
    print(f'OBS error: {e}')
" 2>/dev/null || echo "OBS unreachable")
    echo ""
    echo "◆ STREAM: ${stream_status}"
    last_stream_check=$now
  fi

  sleep 5
done
REMOTE
