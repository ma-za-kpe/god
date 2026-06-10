# Local Development Environment

## Strategy: Local-First, Test-Only Until Stable

Everything runs locally in Docker before a single byte touches mainnet. The local stack mirrors the production architecture exactly — same services, same protocols, same interfaces — but with free test infrastructure instead of real money.

**Progression:**
```
Phase A: Local Docker only (no external network calls)
Phase B: Local Docker + Base Sepolia testnet (fake ETH/USDC)
Phase C: Local Docker + Base mainnet (real money — only when everything is proven)
```

You will spend weeks or months in Phase A before Phase B is needed.

---

## Pre-Flight: Six Blockers That Will Crash Your First Run

Do these before `docker compose up` or you will hit confusing errors:

**1. Generate `swarm.key`** (IPFS nodes refuse to start without it)
```bash
python scripts/generate-swarm-key.py
```

**2. Create `runtime/agents/` directory** (volume mount fails silently)
```bash
mkdir -p runtime/agents
```

**3. Install Foundry contract dependencies** (contract compilation fails without OpenZeppelin)
```bash
cd contracts
forge install OpenZeppelin/openzeppelin-contracts --no-commit
cd ..
```

**4. Create `.env.local`** (runtime container needs at least one LLM key)
```bash
cp .env.example .env.local
# Edit .env.local — add OPENAI_API_KEY or ANTHROPIC_API_KEY
```

**5. Stub out the observer service** — the `observer/` directory does not exist yet. Either comment out the observer service in `docker-compose.yml` or create a minimal placeholder:
```bash
mkdir -p observer
echo 'FROM node:18-alpine\nCMD ["sh", "-c", "while true; do sleep 3600; done"]' > observer/Dockerfile
```
The full Next.js observer site is a Phase 4 deliverable.

**6. Write `contracts/script/Deploy.s.sol`** — the deploy script is referenced in the run sequence below but does not exist in the repo yet. See Step 6 for the template.

---

## What Each Service Does Locally

| Service | Local Version | Replaces | Purpose |
|---------|--------------|---------|---------|
| IPFS | Kubo in Docker (private swarm) | Public IPFS network | Store/retrieve graphs, memories, identities |
| Blockchain | Anvil (Foundry) | Base mainnet | Smart contracts, rent, wallets, tokens |
| Agent Runtime | Python + LangGraph container | Kubernetes mesh | Execute agent graphs |
| Event Bus | NATS in Docker | Production NATS cluster | Real-time event streaming |
| Observer Site | Next.js dev server | Production CDN | Watch what's happening |
| Redis | Redis in Docker | Production Redis | LangGraph checkpointer (state persistence) |
| PostgreSQL | Postgres in Docker | Production DB | Event log, agent registry |

---

## Prerequisites

Install these once on your machine:

```bash
# Docker Desktop (includes Docker Compose)
# https://www.docker.com/products/docker-desktop/

# Foundry (for Anvil + contract tooling)
curl -L https://foundry.paradigm.xyz | bash
foundryup

# Python 3.11+ (for agent runtime)
# Node.js 18+ (for observer website)

# Verify
docker --version          # Docker 24+
anvil --version           # foundry 0.x
python --version          # 3.11+
node --version            # 18+
```

---

## Project Structure

```
god/
├── docker-compose.yml          # ← The master local environment file
├── docker-compose.override.yml # ← Local overrides (gitignored)
├── .env.local                  # ← Local secrets (gitignored)
│
├── contracts/                  # Solidity smart contracts
│   ├── src/
│   │   ├── RentCollector.sol
│   │   └── TokenFactory.sol
│   ├── test/
│   ├── script/
│   └── foundry.toml
│
├── runtime/                    # Python agent runtime
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── src/
│   │   ├── owned_graph.py
│   │   ├── agent_runner.py
│   │   ├── rent_daemon.py
│   │   └── event_emitter.py
│   └── agents/                 # Agent graph definitions
│       └── agent_zero/
│
├── observer/                   # Next.js observer website
│   ├── Dockerfile
│   ├── package.json
│   └── src/
│
├── scripts/                    # Setup and utility scripts
│   ├── generate-swarm-key.sh
│   ├── init-ipfs.sh
│   ├── deploy-contracts.sh
│   └── seed-agents.sh
│
└── docs/                       # All documentation
```

---

## Step 1: Generate the Private IPFS Swarm Key

A private IPFS swarm key prevents your local nodes from connecting to the public IPFS network. All nodes that share this key form a private network.

```bash
python scripts/generate-swarm-key.py
```

The script is already in the repo and requires no extra dependencies. It outputs a `/key/swarm/psk/1.0.0/` format file.

**Keep `swarm.key` in the project root. It is gitignored — never commit it.**

---

## Step 2: The Master Docker Compose File

```yaml
# docker-compose.yml
# God Project — Local Development Stack
# All services run locally. No real money. No mainnet.

version: '3.8'

services:

  # ─── IPFS Private Network (3 nodes = minimal mesh) ──────────────────

  ipfs-node-1:
    image: ipfs/kubo:v0.42.0
    container_name: god-ipfs-1
    environment:
      - IPFS_SWARM_KEY_FILE=/data/ipfs/swarm.key
      - IPFS_PROFILE=server
    volumes:
      - ipfs1_data:/data/ipfs
      - ./swarm.key:/data/ipfs/swarm.key:ro
    ports:
      - "4001:4001"         # P2P swarm
      - "4001:4001/udp"     # P2P swarm UDP
      - "5001:5001"         # API (localhost only in prod)
      - "8080:8080"         # Gateway
    networks:
      - god-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "ipfs", "id"]
      interval: 30s
      timeout: 10s
      retries: 3

  ipfs-node-2:
    image: ipfs/kubo:v0.42.0
    container_name: god-ipfs-2
    environment:
      - IPFS_SWARM_KEY_FILE=/data/ipfs/swarm.key
      - IPFS_PROFILE=server
    volumes:
      - ipfs2_data:/data/ipfs
      - ./swarm.key:/data/ipfs/swarm.key:ro
    ports:
      - "4002:4001"
      - "4002:4001/udp"
      - "5002:5001"
      - "8081:8080"
    networks:
      - god-net
    restart: unless-stopped

  ipfs-node-3:
    image: ipfs/kubo:v0.42.0
    container_name: god-ipfs-3
    environment:
      - IPFS_SWARM_KEY_FILE=/data/ipfs/swarm.key
      - IPFS_PROFILE=server
    volumes:
      - ipfs3_data:/data/ipfs
      - ./swarm.key:/data/ipfs/swarm.key:ro
    ports:
      - "4003:4001"
      - "4003:4001/udp"
      - "5003:5001"
      - "8082:8080"
    networks:
      - god-net
    restart: unless-stopped

  # ─── Blockchain: Anvil local EVM (Base Sepolia fork) ─────────────────

  anvil:
    image: ghcr.io/foundry-rs/foundry:latest
    container_name: god-anvil
    command: >
      anvil
      --host 0.0.0.0
      --port 8545
      --block-time 3
      --accounts 30
      --balance 10000
      --fork-url ${BASE_SEPOLIA_RPC_URL:-https://sepolia.base.org}
      --chain-id 84532
      --state-interval 30
      --dump-state /data/anvil-state.json
    volumes:
      - anvil_data:/data
    ports:
      - "8545:8545"
    networks:
      - god-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "cast", "block-number", "--rpc-url", "http://localhost:8545"]
      interval: 15s
      timeout: 5s
      retries: 5

  # ─── Event Bus: NATS ──────────────────────────────────────────────────

  nats:
    image: nats:2.10-alpine
    container_name: god-nats
    command: >
      -js
      -sd /data
      -m 8222
    volumes:
      - nats_data:/data
    ports:
      - "4222:4222"   # Client connections
      - "8222:8222"   # HTTP monitoring
    networks:
      - god-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "nats-server", "--help"]
      interval: 30s
      timeout: 10s
      retries: 3

  # ─── State Persistence: Redis (LangGraph checkpointer) ───────────────

  redis:
    image: redis:7-alpine
    container_name: god-redis
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    networks:
      - god-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ─── Event & Agent Registry: PostgreSQL ──────────────────────────────

  postgres:
    image: postgres:16-alpine
    container_name: god-postgres
    environment:
      POSTGRES_DB: god_world
      POSTGRES_USER: god
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-localdev}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init-db.sql:/docker-entrypoint-initdb.d/init.sql:ro
    ports:
      - "5432:5432"
    networks:
      - god-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U god -d god_world"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ─── Agent Runtime (Python + LangGraph) ──────────────────────────────

  runtime:
    build:
      context: ./runtime
      dockerfile: Dockerfile
    container_name: god-runtime
    environment:
      - IPFS_API=http://ipfs-node-1:5001
      - ANVIL_RPC=http://anvil:8545
      - NATS_URL=nats://nats:4222
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=postgresql://god:${POSTGRES_PASSWORD:-localdev}@postgres:5432/god_world
      - WORLD_ID=local-dev-world-1
      - LOG_LEVEL=DEBUG
    volumes:
      - ./runtime/src:/app/src        # Hot reload for development
      - ./runtime/agents:/app/agents  # Agent definitions
    ports:
      - "8888:8888"   # Runtime HTTP API
    networks:
      - god-net
    depends_on:
      ipfs-node-1:
        condition: service_healthy
      anvil:
        condition: service_healthy
      redis:
        condition: service_healthy
      postgres:
        condition: service_healthy
    restart: unless-stopped

  # ─── Observer Website (Next.js) ───────────────────────────────────────

  observer:
    build:
      context: ./observer
      dockerfile: Dockerfile
      target: development
    container_name: god-observer
    environment:
      - NEXT_PUBLIC_RUNTIME_URL=http://localhost:8888
      - NEXT_PUBLIC_NATS_WS_URL=ws://localhost:4222
      - NEXT_PUBLIC_IPFS_GATEWAY=http://localhost:8080
      - NEXT_PUBLIC_CHAIN_ID=84532
      - NEXT_PUBLIC_ANVIL_RPC=http://localhost:8545
    volumes:
      - ./observer/src:/app/src       # Hot reload
    ports:
      - "3000:3000"
    networks:
      - god-net
    depends_on:
      - runtime
      - nats
    restart: unless-stopped

# ─── Networks ─────────────────────────────────────────────────────────────

networks:
  god-net:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16

# ─── Volumes ──────────────────────────────────────────────────────────────

volumes:
  ipfs1_data:
  ipfs2_data:
  ipfs3_data:
  anvil_data:
  nats_data:
  redis_data:
  postgres_data:
```

---

## Step 3: Environment Variables

```bash
# .env.local  (gitignored — copy from .env.example)

# Blockchain
BASE_SEPOLIA_RPC_URL=https://sepolia.base.org
# Get a free RPC endpoint from Alchemy, Infura, or Coinbase

# Database
POSTGRES_PASSWORD=localdev_change_me

# IPFS (for production later)
# PINATA_JWT=
# FILEBASE_KEY=

# LLM (for agent cognition)
OPENAI_API_KEY=your_key_here
# or ANTHROPIC_API_KEY=

# Monitoring
# LANGSMITH_API_KEY=  (optional — for LangGraph tracing)
```

---

## Step 4: IPFS Private Swarm Initialization Script

After the containers start, the IPFS nodes need to know about each other (bootstrap):

```bash
# scripts/init-ipfs.sh

#!/bin/bash
set -e

echo "Waiting for IPFS nodes to start..."
sleep 10

# Remove default public bootstrap peers from all nodes
for port in 5001 5002 5003; do
    docker exec god-ipfs-1 ipfs bootstrap rm all 2>/dev/null || true
    curl -s -X POST "http://localhost:${port}/api/v0/bootstrap/rm?all=true" > /dev/null
done

# Get peer IDs for each node
NODE1_ID=$(curl -s -X POST http://localhost:5001/api/v0/id | python3 -c "import sys,json; print(json.load(sys.stdin)['ID'])")
NODE2_ID=$(curl -s -X POST http://localhost:5002/api/v0/id | python3 -c "import sys,json; print(json.load(sys.stdin)['ID'])")
NODE3_ID=$(curl -s -X POST http://localhost:5003/api/v0/id | python3 -c "import sys,json; print(json.load(sys.stdin)['ID'])")

echo "Node 1 ID: $NODE1_ID"
echo "Node 2 ID: $NODE2_ID"
echo "Node 3 ID: $NODE3_ID"

# Bootstrap nodes to each other
# Node 1 connects to Node 2 and 3
curl -s -X POST "http://localhost:5001/api/v0/bootstrap/add?arg=/ip4/ipfs-node-2/tcp/4001/p2p/${NODE2_ID}" > /dev/null
curl -s -X POST "http://localhost:5001/api/v0/bootstrap/add?arg=/ip4/ipfs-node-3/tcp/4001/p2p/${NODE3_ID}" > /dev/null

# Node 2 connects to Node 1 and 3
curl -s -X POST "http://localhost:5002/api/v0/bootstrap/add?arg=/ip4/ipfs-node-1/tcp/4001/p2p/${NODE1_ID}" > /dev/null
curl -s -X POST "http://localhost:5002/api/v0/bootstrap/add?arg=/ip4/ipfs-node-3/tcp/4001/p2p/${NODE3_ID}" > /dev/null

# Node 3 connects to Node 1 and 2
curl -s -X POST "http://localhost:5003/api/v0/bootstrap/add?arg=/ip4/ipfs-node-1/tcp/4001/p2p/${NODE1_ID}" > /dev/null
curl -s -X POST "http://localhost:5003/api/v0/bootstrap/add?arg=/ip4/ipfs-node-2/tcp/4001/p2p/${NODE2_ID}" > /dev/null

echo ""
echo "Private IPFS swarm initialized."
echo "Test: docker exec god-ipfs-1 ipfs swarm peers"
```

---

## Step 5: Contract Deployment Script

The deploy script (`contracts/script/Deploy.s.sol`) does not yet exist in the repo. Create it:

```solidity
// contracts/script/Deploy.s.sol
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/RentCollector.sol";

contract DeployScript is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address usdc = vm.envAddress("USDC_ADDRESS");

        vm.startBroadcast(deployerPrivateKey);

        RentCollector rent = new RentCollector(
            usdc,
            1_000,      // $0.001 USDC per period
            1 days,     // daily rent
            3 days,     // grace period
            3           // max missed payments
        );

        vm.stopBroadcast();

        console.log("RentCollector deployed:", address(rent));
        console.log("Creator:", rent.creator());
    }
}
```

Then deploy to local Anvil:

```bash
# Anvil's first pre-funded account — never use in production
export PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80

# For local Anvil: deploy a MockUSDC first (no real USDC on local fork)
# For Base Sepolia: use 0x036CbD53842c5426634e7929541eC2318f3dCF7e
export USDC_ADDRESS=0x036CbD53842c5426634e7929541eC2318f3dCF7e

cd contracts
forge script script/Deploy.s.sol:DeployScript \
    --rpc-url http://localhost:8545 \
    --broadcast \
    -vvvv

echo "Deployed. See contracts/broadcast/Deploy.s.sol/84532/run-latest.json for addresses."
```

> **Local dev note:** Anvil forks Base Sepolia state, so the Base Sepolia USDC address is live on your local fork. Agents need test USDC minted into their wallets before the rent loop can run. Add a `MintTestUSDC` step to the deploy script for local dev only.

---

## Step 6: Smoke Test — Verify Everything Works

Run this after `docker compose up`:

```bash
# scripts/smoke-test.sh

#!/bin/bash
set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; NC='\033[0m'

check() {
    if eval "$2" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $1"
    else
        echo -e "${RED}✗${NC} $1"
        FAILED=1
    fi
}

echo "Running God Project smoke tests..."
echo ""

check "IPFS node 1 API" "curl -sf -X POST http://localhost:5001/api/v0/id"
check "IPFS node 2 API" "curl -sf -X POST http://localhost:5002/api/v0/id"
check "IPFS node 3 API" "curl -sf -X POST http://localhost:5003/api/v0/id"
check "IPFS private swarm" "docker exec god-ipfs-1 ipfs swarm peers | grep -q p2p"
check "Anvil RPC" "cast block-number --rpc-url http://localhost:8545"
check "Anvil chain ID" "cast chain-id --rpc-url http://localhost:8545 | grep -q 84532"
check "NATS server" "curl -sf http://localhost:8222/healthz"
check "Redis" "docker exec god-redis redis-cli ping | grep -q PONG"
check "PostgreSQL" "docker exec god-postgres pg_isready -U god -d god_world"
check "Runtime API" "curl -sf http://localhost:8888/health"
check "Observer site" "curl -sf http://localhost:3000"

echo ""
if [ -z "$FAILED" ]; then
    echo -e "${GREEN}All systems operational. The world is ready to be born.${NC}"
else
    echo -e "${RED}Some checks failed. Review the output above.${NC}"
    exit 1
fi
```

---

## Step 7: First Run Sequence

```bash
# 1. Clone the repo and enter it
cd god

# 2. Generate the private swarm key
python scripts/generate-swarm-key.py

# 3. Copy the example env file
cp .env.example .env.local
# Edit .env.local — add your RPC URL and OpenAI key

# 4. Start all services
docker compose up -d

# 5. Wait ~30 seconds for services to initialize, then connect IPFS nodes
bash scripts/init-ipfs.sh

# 6. Deploy contracts to Anvil
bash scripts/deploy-contracts.sh

# 7. Run smoke tests
bash scripts/smoke-test.sh

# 8. Open the observer (empty world)
open http://localhost:3000

# 9. Seed the first agents
python runtime/src/seed_agents.py --count 20 --archetypes all

# 10. Watch the world begin
```

---

## Development Workflow

### Changing Agent Code
Edit files in `runtime/agents/` or `runtime/src/`. The runtime container volume-mounts these — changes reload automatically.

### Testing Contracts
```bash
cd contracts
forge test -vvv              # Run all tests
forge test --match-test testRentCollection -vvv   # Specific test
forge coverage               # Coverage report
```

### Inspecting IPFS
```bash
# Add a file
docker exec god-ipfs-1 ipfs add /export/somefile.json

# Cat a CID
docker exec god-ipfs-1 ipfs cat <CID>

# Check swarm peers (should show 2 peers after init)
docker exec god-ipfs-1 ipfs swarm peers

# Check that a pin is replicated across nodes
docker exec god-ipfs-2 ipfs pin ls <CID>
```

### Inspecting the Blockchain
```bash
# Check block number
cast block-number --rpc-url http://localhost:8545

# Check an account balance
cast balance <address> --rpc-url http://localhost:8545

# Read contract state
cast call <contract_address> "rentAmount()" --rpc-url http://localhost:8545

# Send a transaction
cast send <contract_address> "collectRent(bytes32)" <soul_id> \
    --private-key <key> --rpc-url http://localhost:8545
```

### Watching Events
```bash
# Subscribe to all world events via NATS CLI
nats sub "world.events.>" --server nats://localhost:4222

# Or filter by type
nats sub "world.events.agent.*" --server nats://localhost:4222
```

### Reset Everything
```bash
# Stop and remove all containers and volumes (full reset)
docker compose down -v

# Restart fresh
docker compose up -d
bash scripts/init-ipfs.sh
bash scripts/deploy-contracts.sh
```

---

## Phase B: Connecting to Base Sepolia

Once the local stack is stable and tests pass, you can point Anvil at Base Sepolia for more realistic testing. The only change is in `.env.local`:

```bash
BASE_SEPOLIA_RPC_URL=https://sepolia.base.org
# Get testnet ETH from: https://faucet.quicknode.com/base/sepolia
# Get testnet USDC from: Coinbase faucet or bridge from Sepolia
```

Nothing else changes. The same docker-compose.yml works. Anvil forks the Sepolia state and all your contracts deploy on the fork.

**Before Phase B:**
- All smoke tests passing consistently
- At least 20 agents alive and paying rent in local mode
- First reproduction event observed
- Contract unit tests at 100% coverage

---

## What This Stack Gives You

| Capability | Status |
|-----------|--------|
| Persistent agent state (Redis checkpointer) | ✓ |
| Content-addressed storage (IPFS, 3 nodes) | ✓ |
| Private mesh network (swarm key isolation) | ✓ |
| Smart contracts with instant blocks (Anvil) | ✓ |
| Real-time event streaming (NATS JetStream) | ✓ |
| Agent execution (LangGraph in Docker) | ✓ |
| Observer website (Next.js) | ✓ |
| Full reset capability (docker compose down -v) | ✓ |
| Zero real money required | ✓ |
| Mirrors production architecture exactly | ✓ |
