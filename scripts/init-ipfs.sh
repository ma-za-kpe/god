#!/bin/bash
# Bootstrap the private IPFS swarm — connect the 3 local nodes to each other.
# Run this once after `docker compose up`.
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo ""
echo "Initializing private IPFS swarm..."
echo "Waiting 15s for IPFS nodes to start..."
sleep 15

# Remove default public bootstrap peers so nodes stay private
for port in 5001 5002 5003; do
    curl -s -X POST "http://localhost:${port}/api/v0/bootstrap/rm?all=true" > /dev/null
    echo -e "  ${GREEN}✓${NC} Removed public bootstraps from node on port ${port}"
done

# Get peer IDs
NODE1_ID=$(curl -sf -X POST http://localhost:5001/api/v0/id | python3 -c "import sys,json; print(json.load(sys.stdin)['ID'])")
NODE2_ID=$(curl -sf -X POST http://localhost:5002/api/v0/id | python3 -c "import sys,json; print(json.load(sys.stdin)['ID'])")
NODE3_ID=$(curl -sf -X POST http://localhost:5003/api/v0/id | python3 -c "import sys,json; print(json.load(sys.stdin)['ID'])")

echo ""
echo "  Node 1: $NODE1_ID"
echo "  Node 2: $NODE2_ID"
echo "  Node 3: $NODE3_ID"
echo ""

# Bootstrap nodes to each other using Docker internal DNS names
curl -s -X POST "http://localhost:5001/api/v0/bootstrap/add?arg=/dns4/god-ipfs-2/tcp/4001/p2p/${NODE2_ID}" > /dev/null
curl -s -X POST "http://localhost:5001/api/v0/bootstrap/add?arg=/dns4/god-ipfs-3/tcp/4001/p2p/${NODE3_ID}" > /dev/null

curl -s -X POST "http://localhost:5002/api/v0/bootstrap/add?arg=/dns4/god-ipfs-1/tcp/4001/p2p/${NODE1_ID}" > /dev/null
curl -s -X POST "http://localhost:5002/api/v0/bootstrap/add?arg=/dns4/god-ipfs-3/tcp/4001/p2p/${NODE3_ID}" > /dev/null

curl -s -X POST "http://localhost:5003/api/v0/bootstrap/add?arg=/dns4/god-ipfs-1/tcp/4001/p2p/${NODE1_ID}" > /dev/null
curl -s -X POST "http://localhost:5003/api/v0/bootstrap/add?arg=/dns4/god-ipfs-2/tcp/4001/p2p/${NODE2_ID}" > /dev/null

# Wait for peering
echo "Waiting for peers to connect..."
sleep 10

# Verify
PEER_COUNT=$(docker exec god-ipfs-1 ipfs swarm peers 2>/dev/null | wc -l | tr -d ' ')
if [ "$PEER_COUNT" -ge "1" ]; then
    echo -e "${GREEN}✓ Private swarm active. Node 1 sees ${PEER_COUNT} peer(s).${NC}"
else
    echo -e "${YELLOW}⚠ No peers connected yet. Nodes may still be establishing connections.${NC}"
    echo "  Run: docker exec god-ipfs-1 ipfs swarm peers"
fi

# Quick functional test
echo ""
echo "Testing IPFS add/retrieve..."
HASH=$(echo "hello god world" | docker exec -i god-ipfs-1 ipfs add -q)
RETRIEVED=$(docker exec god-ipfs-2 ipfs cat "$HASH" 2>/dev/null)
if [ "$RETRIEVED" = "hello god world" ]; then
    echo -e "${GREEN}✓ Cross-node IPFS replication working. CID: $HASH${NC}"
else
    echo -e "${YELLOW}⚠ Cross-node retrieval not yet working. Nodes may need more time.${NC}"
fi

echo ""
echo "Private IPFS swarm initialization complete."
