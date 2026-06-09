#!/bin/bash
# Smoke test — verify all God Project services are running correctly.
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'
FAILED=0

check() {
    local label="$1"
    local cmd="$2"
    if eval "$cmd" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} ${label}"
    else
        echo -e "  ${RED}✗${NC} ${label}"
        FAILED=1
    fi
}

echo ""
echo -e "${BOLD}God Project — Smoke Tests${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "IPFS Nodes:"
check "Node 1 API reachable"    "curl -sf -X POST http://localhost:5001/api/v0/id"
check "Node 2 API reachable"    "curl -sf -X POST http://localhost:5002/api/v0/id"
check "Node 3 API reachable"    "curl -sf -X POST http://localhost:5003/api/v0/id"
check "Private swarm connected" "docker exec god-ipfs-1 ipfs swarm peers 2>/dev/null | grep -q p2p"

echo ""
echo "Blockchain (Anvil):"
check "RPC endpoint live"       "curl -sf -X POST -H 'Content-Type: application/json' --data '{\"jsonrpc\":\"2.0\",\"method\":\"eth_blockNumber\",\"params\":[],\"id\":1}' http://localhost:8545"
check "Chain ID is 84532"       "curl -sf -X POST -H 'Content-Type: application/json' --data '{\"jsonrpc\":\"2.0\",\"method\":\"eth_chainId\",\"params\":[],\"id\":1}' http://localhost:8545 | grep -q '0x14a34'"
check "Funded accounts exist"   "curl -sf -X POST -H 'Content-Type: application/json' --data '{\"jsonrpc\":\"2.0\",\"method\":\"eth_getBalance\",\"params\":[\"0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266\",\"latest\"],\"id\":1}' http://localhost:8545 | grep -qv '\"result\":\"0x0\"'"

echo ""
echo "Event Bus (NATS):"
check "NATS server healthy"     "curl -sf http://localhost:8222/healthz"
check "JetStream enabled"       "curl -sf http://localhost:8222/jsz | grep -q 'config'"

echo ""
echo "State & Storage:"
check "Redis ping"              "docker exec god-redis redis-cli ping 2>/dev/null | grep -q PONG"
check "PostgreSQL ready"        "docker exec god-postgres pg_isready -U god -d god_world 2>/dev/null"
check "Agents table exists"     "docker exec god-postgres psql -U god -d god_world -c 'SELECT 1 FROM agents LIMIT 1' 2>/dev/null"

echo ""
echo "Agent Runtime:"
check "Runtime health endpoint" "curl -sf http://localhost:8888/health"

echo ""
echo "Observer Website (optional — start with: docker compose --profile observer up -d):"
if curl -sf http://localhost:3000 > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} Observer site loading"
else
    echo -e "  ${YELLOW}○${NC} Observer not running (use --profile observer to start)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ "$FAILED" -eq 0 ]; then
    echo -e "${GREEN}${BOLD}All systems operational.${NC}"
    echo -e "The world is ready to be born."
    echo ""
    echo "Next step: docker exec god-runtime python -m src.seed_agents --count 20"
    echo "Observer:  http://localhost:3000"
else
    echo -e "${RED}${BOLD}Some checks failed.${NC}"
    echo "Review the output above. Common fixes:"
    echo "  • Services still starting: wait 30s and retry"
    echo "  • IPFS swarm not connected: run bash scripts/init-ipfs.sh"
    echo "  • Runtime not ready: check logs with docker logs god-runtime"
    exit 1
fi
