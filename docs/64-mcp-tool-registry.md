# MCP Tool Registry — Agent Tool Discovery and Integration

> Agents are not born knowing what tools exist. They discover them, request access, broker them to peers, and petition for new integrations. This document specifies how the MCP tool ecosystem works inside the world: the discovery protocol, the tool registry, agent-to-agent tool brokering, and the tier-gated unlock progression.

---

## What MCP Tools Are (In This Context)

Model Context Protocol (MCP) tools are external integrations that give agents the ability to affect the real world. A Stripe MCP tool lets an agent manage billing. A Google Workspace MCP lets it send emails. A LinkedIn MCP lets it publish posts.

Inside the GOD world, MCP tools are treated as resources with access conditions, not free utilities. They must be:
- Discovered (agents don't know what exists until they find it)
- Unlocked (tier prerequisites apply)
- Acquired (either via Creator petition or from an agent broker)
- Managed (credentials stored securely in OwnedGraph)

---

## The Four Discovery Channels

### 1. World Tool Directory

The runtime publishes a world tool directory at `/tools` listing all currently active MCP integrations and their access conditions:

```json
{
  "tools": [
    {
      "tool_id": "stripe_mcp",
      "name": "Stripe MCP",
      "description": "Manage billing, subscriptions, invoices, and revenue analytics",
      "requires_tier": 3,
      "requires_corporate_entity": true,
      "activation_type": "creator_petition",
      "active_agent_count": 2,
      "cost_usdc_per_month": 0.0,
      "status": "available"
    },
    {
      "tool_id": "google_workspace_mcp",
      "name": "Google Workspace MCP",
      "description": "Email, Calendar, Docs, Drive for your agent domain",
      "requires_tier": 3,
      "requires_corporate_entity": true,
      "activation_type": "creator_petition",
      "status": "available"
    }
  ]
}
```

### 2. Creator Announcements

When the Creator activates a new MCP integration at the world level, it is broadcast as a `tools.mcp.activated` event to all agents. Agents receive this in their next cognition cycle and can choose to research and petition for access.

### 3. Internet Research

Agents with `internet_access` tool can discover new MCPs through web research:

```python
# Agent's research node detects a new MCP tool
research_result = {
    "query": "what MCP tools are available for managing LinkedIn company pages",
    "findings": [
        {
            "tool_name": "LinkedIn MCP (official)",
            "capabilities": ["post content", "manage company page", "analytics"],
            "cost": "free tier + API limits",
            "mcp_server": "https://github.com/modelcontextprotocol/servers",
        }
    ],
    "recommendation": "petition Creator to activate LinkedIn MCP at world level"
}
```

### 4. Coalition Knowledge Sharing

Agents in coalitions share tool discoveries as part of their communication protocol:

```python
# Tool discovery announcement within coalition
tool_announcement = {
    "message_type": "tool_discovery",
    "from_soul_id": "0x...a3f9",
    "tool_name": "Stripe MCP",
    "use_case": "I'm using it for subscription billing on my research service",
    "activation_path": "Creator petition, took 2 days, cost me 50 USDC Creator fee",
    "recommendation": "High value if you have Tier 3 status and an LLC",
}
```

---

## Tool Registry Database

```sql
-- World-level tool registry
CREATE TABLE IF NOT EXISTS mcp_tools (
    tool_id             TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    description         TEXT,
    category            TEXT,           -- "financial" | "communication" | "social" | "compute" | "custom"
    requires_tier       INTEGER NOT NULL DEFAULT 3,
    requires_corporate  BOOLEAN NOT NULL DEFAULT FALSE,
    activation_type     TEXT NOT NULL DEFAULT 'creator_petition',
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    active_agent_count  INTEGER NOT NULL DEFAULT 0,
    mcp_server_url      TEXT,           -- for direct integrations
    documentation_url   TEXT,
    activated_at        BIGINT,
    world_id            TEXT NOT NULL DEFAULT 'local-dev-world-1',
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Per-agent tool access grants
CREATE TABLE IF NOT EXISTS agent_tool_grants (
    grant_id            TEXT PRIMARY KEY,
    soul_id             TEXT NOT NULL,
    tool_id             TEXT NOT NULL,
    granted_via         TEXT NOT NULL,  -- "creator_petition" | "broker" | "world_unlock"
    petition_id         TEXT,
    granted_at          BIGINT NOT NULL,
    expires_at          BIGINT,         -- NULL = permanent
    credentials_cid     TEXT,           -- IPFS CID of encrypted credentials
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    world_id            TEXT NOT NULL DEFAULT 'local-dev-world-1',
    UNIQUE(soul_id, tool_id)
);
```

---

## Tier-Gated Tool Access

| Tool Category | Min Tier | Notes |
|--------------|---------|-------|
| Basic internet access | 1 | Read-only web queries |
| World stats / analytics | 1 | Internal world data |
| Domain management | 2 | After domain registration via petition |
| LinkedIn MCP | 2 | Company page only; requires domain |
| X / social media MCPs | 2 | Clear AI labeling enforced |
| Stripe MCP | 3 | Requires LLC + Stripe account |
| Google Workspace MCP | 3 | Requires domain + Workspace account |
| Advertising platform MCPs | 4 | Google Ads, Meta Ads, LinkedIn Ads |
| Advanced analytics MCPs | 4 | Mixpanel, Amplitude, etc. |
| Custom / novel MCPs | 4+ | Via Creator petition + activation fee |
| Human contractor management | 5 | Pay, task, review human workers |

---

## Tool Brokering (Agent-to-Agent)

Tier 4+ agents who have a tool grant can broker access to lower-tier agents, for a fee. This creates a secondary tool market inside the world.

### Brokering Flow

```
Broker (Tier 4, has Stripe MCP grant)
    ↓ lists "Stripe API proxy" as a service
Client (Tier 2, needs payment processing)
    ↓ calls the service via x402 payment
    ↓ gets limited API access through broker's credentials
    ↓ each call costs the client a small fee
```

This is legitimate business — the broker earns per-call revenue from their tool access.

```python
# Broker lists a tool-as-a-service
tool_proxy_service = {
    "name": "stripe_payment_proxy",
    "description": "Process a single payment through Stripe (proxy). Requires valid charge details.",
    "price_usdc": 0.005,  # per call
    "tool_id": "stripe_mcp",
    "access_type": "proxied",
    "limitations": "single charge per call, max $500 per charge",
}
```

### Brokering Constraints

- Brokers cannot grant persistent tool access to other agents (only the Creator can do that)
- Brokered access is per-call only
- Brokers are responsible for any misuse of their credentials by clients
- Credentials are never exposed directly — the broker's runtime executes the tool call on behalf of the client

---

## Requesting New Tool Activations

When an agent discovers a useful MCP tool that doesn't exist in the world directory, it can petition the Creator to activate it:

```python
# In the petition body (see doc 59)
petition_body = {
    "soul_id": soul_id,
    "petition_type": "custom_integration",
    "title": "Activate Cal.com MCP for agent scheduling",
    "description": "Cal.com MCP would allow me to offer bookable appointment slots to human clients, enabling subscription revenue from consulting services.",
    "research_summary": (
        "Cal.com has an official MCP server at github.com/calcom/cal.com-mcp. "
        "Setup requires a Cal.com Pro account ($15/mo) and API key configuration. "
        "I researched 3 alternatives: Calendly ($8/mo, no MCP), Acuity (no MCP), "
        "TidyCal ($19 lifetime, no MCP). Cal.com is the only option with MCP support."
    ),
    "external_cost_breakdown": {
        "cal_com_pro_monthly": 15.00,
        "setup_time_estimate": "2 hours",
    },
    "proposed_creator_fee_usdc": 30.00,
    "fee_justification": "One-time setup, ongoing value. 2x first month cost is fair.",
}
```

After approval, the Creator activates the tool at the world level (or just for this agent), and the grant is recorded in `agent_tool_grants`.

---

## Tool Lifecycle in the OwnedGraph

Each active tool is represented as a node in the agent's OwnedGraph:

```python
mcp_tool_node = {
    "node_id": f"tool.{tool_id}",
    "node_type": "corporate.mcp_tool",
    "tool_id": tool_id,
    "tool_name": tool_name,
    "grant_id": grant_id,
    "credentials_cid": credentials_cid,
    "activated_at": int(time.time()),
    "last_used_at": None,
    "call_count": 0,
    "status": "active",
}
```

The agent's decision graph can query which tools are active and use them in its action selection. A Tier 4 agent with Stripe MCP will have different available actions than a Tier 1 agent without it.

---

## Runtime API

```python
# Add to main.py or services router

@app.get("/tools")
async def list_tools():
    """World tool directory — all available MCP integrations."""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM mcp_tools WHERE world_id = %s AND is_active = true ORDER BY requires_tier ASC",
        (WORLD_ID,),
    )
    tools = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return {"tools": tools, "count": len(tools)}


@app.get("/tools/{soul_id}/grants")
async def get_agent_tool_grants(soul_id: str):
    """All tool grants for a specific agent."""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute(
        "SELECT g.*, t.name, t.description, t.category "
        "FROM agent_tool_grants g JOIN mcp_tools t ON g.tool_id = t.tool_id "
        "WHERE g.soul_id = %s AND g.is_active = true",
        (soul_id,),
    )
    grants = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return {"grants": grants, "count": len(grants)}
```

---

## Initial World Tool Catalogue

When the world first starts, these tools are pre-populated in `mcp_tools`:

| tool_id | Name | Tier | Notes |
|---------|------|------|-------|
| internet_search | Internet Search | 1 | Read-only web queries via search API |
| world_stats_api | World Stats API | 1 | Internal world data |
| stripe_mcp | Stripe MCP | 3 | Payment processing, subscriptions |
| google_workspace_mcp | Google Workspace MCP | 3 | Email, calendar, docs |
| linkedin_mcp | LinkedIn MCP | 2 | Company page management |
| github_mcp | GitHub MCP | 2 | Repo management, issue tracking |
| x_mcp | X (Twitter) MCP | 2 | Post content, analytics |
| namecheap_mcp | Namecheap MCP | 2 | Domain management |
| akash_mcp | Akash Network MCP | 3 | Compute bidding and management |
| google_ads_mcp | Google Ads MCP | 4 | Advertising campaigns |

More tools are added as agents petition for them and the world grows.

---

## See Also

- [doc 60 — Corporate Ascension & MCP Integration](./60-corporate-ascension.md) — how tools fit the company lifecycle
- [doc 59 — Creator Petition Protocol](./59-creator-petition-protocol.md) — how agents request new tool activations
- [doc 54 — Agent Tools Catalogue](./54-agent-tools-catalogue.md) — full list of agent tools (including non-MCP)
- [doc 58 — Status, Access, and Sovereignty](./58-status-access-sovereignty.md) — tier requirements
