"""
God Project — Agent Runtime
Entry point. FastAPI server + background daemons for rent collection and agent execution.
"""

import asyncio
import logging
import os
import pathlib
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Header, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .agent_runner import agent_runner
from .creator.routes import router as creator_router
from .rent_daemon import rent_daemon
from .services.routes import router as services_router
from .status_engine import TIERS, status_review_daemon

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("god.runtime")

# Runtime version is loaded from the canonical file (single source of truth, managed via release process).
# This replaces manual hard-coded strings in FastAPI + /health.
# See docs/79-documentation-release.md and scripts for how releases bump this + tag.
try:
    RUNTIME_VERSION = (
        (pathlib.Path(__file__).parent / "VERSION").read_text(encoding="utf-8").strip()
    )
except Exception:
    RUNTIME_VERSION = "0.1.0"

_background_tasks: list[asyncio.Task] = []


async def _agent_jobs_daemon():
    """Process scheduled wake jobs and emit events."""
    interval = int(os.getenv("JOBS_TICK_S", "15"))
    from .agent_jobs import process_due_jobs
    from .event_emitter import get_emitter

    while True:
        try:
            await asyncio.sleep(interval)
            emitter = await get_emitter()
            n = await process_due_jobs(emitter)
            if n:
                log.debug(f"Processed {n} due agent job(s)")
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.debug(f"agent jobs daemon: {e}")


async def _ws_snapshot_daemon():
    """Periodic full snapshot push for WebSocket observers."""
    interval = int(os.getenv("WS_SNAPSHOT_INTERVAL_S", "30"))
    while True:
        try:
            await asyncio.sleep(interval)
            from .world_snapshot import build_world_snapshot_async
            from .world_stream import has_subscribers, push_snapshot

            if not has_subscribers():
                continue
            snap = await build_world_snapshot_async()
            await push_snapshot(snap)
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.debug(f"WS snapshot daemon: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting God Runtime...")
    log.info(f"  World:    {os.getenv('WORLD_ID', 'local-dev-world-1')}")
    log.info(f"  IPFS:     {os.getenv('IPFS_API', 'not configured')}")
    log.info(f"  Chain:    {os.getenv('ANVIL_RPC', 'not configured')}")
    log.info(
        f"  LLM:      {os.getenv('LLM_PROVIDER', 'ollama')} / {os.getenv('LLM_MODEL', 'llama3.1:8b')}"
    )

    from .db_pool import close_pool, init_pool
    from .db_schema import ensure_schema

    ensure_schema()
    await init_pool()

    _background_tasks.append(asyncio.create_task(rent_daemon(), name="rent_daemon"))
    _background_tasks.append(asyncio.create_task(agent_runner(), name="agent_runner"))
    _background_tasks.append(asyncio.create_task(status_review_daemon(), name="status_review"))
    _background_tasks.append(asyncio.create_task(_ws_snapshot_daemon(), name="ws_snapshot"))
    _background_tasks.append(asyncio.create_task(_agent_jobs_daemon(), name="agent_jobs"))

    yield

    log.info("Shutting down daemons...")
    for task in _background_tasks:
        task.cancel()
    await asyncio.gather(*_background_tasks, return_exceptions=True)
    await close_pool()


app = FastAPI(title="God Runtime", version=RUNTIME_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(services_router)
app.include_router(creator_router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "world_id": os.getenv("WORLD_ID", "unknown"),
        "version": RUNTIME_VERSION,
    }


@app.get("/agents")
async def list_agents(limit: int = 10000):
    """All agents with rent stats and last thought. Reads from PostgreSQL."""
    max_limit = int(os.getenv("AGENTS_MAX_LIMIT", "10000"))
    effective_limit = min(max(1, limit), max_limit)
    try:
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(
            os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world"),
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                a.soul_id, a.current_name, a.wallet_address,
                a.birth_timestamp, a.death_timestamp, a.is_alive,
                a.parent_soul_ids, a.archetype,
                COALESCE(a.balance_usdc, 0)          AS balance_usdc,
                COALESCE(a.generation, 1)            AS generation,
                COALESCE(rp.paid_count,  0)          AS rent_paid_count,
                COALESCE(rp.miss_count,  0)          AS rent_miss_count,
                COALESCE(ss.is_sleeping, false)      AS is_sleeping,
                e.last_thought
            FROM agents a
            LEFT JOIN (
                SELECT soul_id,
                    SUM(CASE WHEN NOT missed THEN 1 ELSE 0 END) AS paid_count,
                    SUM(CASE WHEN missed     THEN 1 ELSE 0 END) AS miss_count
                FROM rent_payments GROUP BY soul_id
            ) rp ON rp.soul_id = a.soul_id
            LEFT JOIN sleep_states ss ON ss.soul_id = a.soul_id
            LEFT JOIN LATERAL (
                SELECT payload->>'thought' AS last_thought
                FROM events
                WHERE agent_id = a.soul_id
                  AND event_type = 'cognitive.agent.thought'
                ORDER BY timestamp DESC LIMIT 1
            ) e ON true
            WHERE a.world_id = %s AND a.is_alive = true
            ORDER BY a.birth_timestamp ASC
            LIMIT %s
            """,
            (os.getenv("WORLD_ID", "local-dev-world-1"), effective_limit),
        )
        agents = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return {"agents": agents, "count": len(agents), "limit": effective_limit}
    except Exception as e:
        log.warning(f"/agents DB error: {e}")
        return {"agents": [], "count": 0, "error": str(e)}


@app.get("/world/snapshot")
async def world_snapshot(events_limit: int = 50, messages_limit: int = 80):
    """Pre-aggregated world state for public observer clients."""
    try:
        from .world_snapshot import build_world_snapshot_async

        return await build_world_snapshot_async(
            events_limit=min(events_limit, 200),
            messages_limit=min(messages_limit, 500),
        )
    except Exception as e:
        log.warning(f"/world/snapshot error: {e}")
        try:
            from .world_snapshot import build_world_snapshot

            return build_world_snapshot(
                events_limit=min(events_limit, 200),
                messages_limit=min(messages_limit, 500),
            )
        except Exception as e2:
            return {"error": str(e2), "world_id": os.getenv("WORLD_ID", "local-dev-world-1")}


@app.get("/showrunner")
async def showrunner_plan(events_limit: int = 50, messages_limit: int = 80):
    """Deterministic broadcast plan derived from the latest world snapshot."""
    try:
        from .world_snapshot import build_world_snapshot_async

        snapshot = await build_world_snapshot_async(
            events_limit=min(events_limit, 200),
            messages_limit=min(messages_limit, 500),
        )
        return {
            "showrunner": snapshot.get("showrunner", {}),
            "world_id": snapshot.get("world_id", os.getenv("WORLD_ID", "local-dev-world-1")),
            "epoch": snapshot.get("epoch"),
        }
    except Exception as e:
        log.warning(f"/showrunner error: {e}")
        return {"error": str(e), "world_id": os.getenv("WORLD_ID", "local-dev-world-1")}


@app.get("/twitch/status")
async def twitch_status():
    """Current Twitch adapter configuration and supported event types."""
    try:
        from .twitch.adapter import build_twitch_status

        status = build_twitch_status()
        return {
            "twitch": status,
            "world_id": os.getenv("WORLD_ID", "local-dev-world-1"),
        }
    except Exception as e:
        log.warning(f"/twitch/status error: {e}")
        return {"error": str(e), "world_id": os.getenv("WORLD_ID", "local-dev-world-1")}


@app.get("/nemo/status")
async def nemo_status():
    """Current NeMo director status and configuration."""
    try:
        from .nemo import build_nemo_status

        return {
            "nemo": build_nemo_status(),
            "world_id": os.getenv("WORLD_ID", "local-dev-world-1"),
        }
    except Exception as e:
        log.warning(f"/nemo/status error: {e}")
        return {"error": str(e), "world_id": os.getenv("WORLD_ID", "local-dev-world-1")}


@app.get("/nemo/director")
async def nemo_director(events_limit: int = 50, messages_limit: int = 80):
    """Current NeMo directive layered over the latest world snapshot."""
    try:
        from .world_snapshot import build_world_snapshot_async

        snapshot = await build_world_snapshot_async(
            events_limit=min(events_limit, 200),
            messages_limit=min(messages_limit, 500),
        )
        return {
            "nemo": snapshot.get("nemo", {}),
            "showrunner": snapshot.get("showrunner", {}),
            "world_id": snapshot.get("world_id", os.getenv("WORLD_ID", "local-dev-world-1")),
            "epoch": snapshot.get("epoch"),
        }
    except Exception as e:
        log.warning(f"/nemo/director error: {e}")
        return {"error": str(e), "world_id": os.getenv("WORLD_ID", "local-dev-world-1")}


@app.websocket("/world/stream")
async def world_stream(ws: WebSocket):
    """WebSocket: snapshot on connect, delta pushes on events, keepalive ping/pong."""
    import asyncio
    import json

    from .json_safe import json_safe
    from .world_snapshot import build_world_snapshot_async
    from .world_stream import current_epoch, subscribe, unsubscribe

    await subscribe(ws)
    try:
        snap = await build_world_snapshot_async()
        await ws.send_text(json.dumps(json_safe({"type": "snapshot", **snap})))
        while True:
            try:
                msg = await asyncio.wait_for(ws.receive_text(), timeout=25.0)
            except asyncio.TimeoutError:
                await ws.send_text(
                    json.dumps({"type": "pong", "epoch": current_epoch(), "keepalive": True})
                )
                continue
            if msg == "ping":
                await ws.send_text(json.dumps({"type": "pong", "epoch": current_epoch()}))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.warning(f"WS stream closed: {e}", exc_info=True)
    finally:
        await unsubscribe(ws)


@app.get("/events")
async def list_events(limit: int = 50):
    """Recent world events. Reads from PostgreSQL event log."""
    try:
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(
            os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world"),
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        cur = conn.cursor()
        cur.execute(
            "SELECT event_id, agent_id, event_type, timestamp, narrative, payload "
            "FROM events WHERE world_id = %s ORDER BY timestamp DESC LIMIT %s",
            (os.getenv("WORLD_ID", "local-dev-world-1"), limit),
        )
        events = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return {"events": events, "limit": limit}
    except Exception as e:
        log.warning(f"/events DB error: {e}")
        return {"events": [], "limit": limit, "error": str(e)}


@app.get("/stats")
async def world_stats():
    """Aggregate world metrics for the observer dashboard."""
    try:
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(
            os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world"),
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE is_alive)                    AS living_count,
                COUNT(*)                                             AS total_born,
                COUNT(*) FILTER (WHERE NOT is_alive)                AS total_died,
                MIN(birth_timestamp)                                 AS world_start_ts
            FROM agents WHERE world_id = %s
            """,
            (os.getenv("WORLD_ID", "local-dev-world-1"),),
        )
        row = dict(cur.fetchone())
        cur.execute(
            "SELECT COUNT(*) AS n FROM events WHERE world_id = %s",
            (os.getenv("WORLD_ID", "local-dev-world-1"),),
        )
        row["events_total"] = cur.fetchone()["n"]
        world_id = os.getenv("WORLD_ID", "local-dev-world-1")
        cur.execute(
            """
            SELECT
                COALESCE(SUM(balance_usdc), 0)  AS total_usdc_in_world,
                COALESCE(AVG(balance_usdc), 0)  AS avg_balance,
                COALESCE(MAX(balance_usdc), 0)  AS max_balance,
                COALESCE(MIN(balance_usdc) FILTER (WHERE is_alive), 0) AS min_balance_alive,
                COALESCE(MAX(generation), 1)    AS max_generation,
                COALESCE(AVG(generation) FILTER (WHERE is_alive), 1) AS avg_generation
            FROM agents WHERE world_id = %s
            """,
            (world_id,),
        )
        econ = dict(cur.fetchone())

        cur.execute("SELECT COUNT(*) AS n FROM agent_messages WHERE world_id = %s", (world_id,))
        row["messages_total"] = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n FROM dreams WHERE world_id = %s", (world_id,))
        row["dreams_total"] = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n FROM tokens WHERE world_id = %s", (world_id,))
        row["tokens_deployed"] = cur.fetchone()["n"]

        cur.close()
        conn.close()
        return {
            **row,
            **econ,
            "world_id": world_id,
            "llm_provider": os.getenv("LLM_PROVIDER", "ollama"),
            "llm_model": os.getenv("LLM_MODEL", "llama3.1:8b"),
        }
    except Exception as e:
        log.warning(f"/stats DB error: {e}")
        return {"error": str(e), "world_id": os.getenv("WORLD_ID", "local-dev-world-1")}


@app.get("/status/{soul_id}")
async def get_agent_status(soul_id: str):
    """Full status record for an agent."""
    try:
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(
            os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world"),
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        cur = conn.cursor()
        cur.execute("SELECT * FROM agent_status WHERE soul_id = %s", (soul_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return {"soul_id": soul_id, "tier": 0, "tier_name": "Newborn"}
        result = dict(row)
        result["tier_name"] = TIERS[min(result["tier"], len(TIERS) - 1)].name
        return result
    except Exception as e:
        log.warning(f"/status DB error: {e}")
        return {"soul_id": soul_id, "tier": 0, "error": str(e)}


@app.get("/tools")
async def list_tools():
    """World MCP catalogue + agent-registered tools (discovery surface)."""
    from .tool_registry import list_agent_tools, list_world_tools

    return {
        "world_tools": list_world_tools(),
        "agent_tools": list_agent_tools(),
        "world_id": os.getenv("WORLD_ID", "local-dev-world-1"),
    }


@app.get("/agents/{soul_id}/env")
async def get_agent_env(soul_id: str):
    """Read-only environment summary for an agent (observer / debug)."""
    from .agent_env import fetch_recent_actions, format_env_for_decide, read_scratch
    from .capabilities import format_capabilities_summary, get_granted_capabilities

    return {
        "soul_id": soul_id,
        "capabilities": sorted(get_granted_capabilities(soul_id)),
        "capabilities_summary": format_capabilities_summary(soul_id),
        "environment": format_env_for_decide(soul_id),
        "scratch": read_scratch(soul_id),
        "recent_actions": fetch_recent_actions(soul_id, limit=12),
    }


@app.get("/leaderboard")
async def get_leaderboard(by: str = "prestige", limit: int = 20):
    """Top agents by prestige, sovereignty, revenue, or tier."""
    valid_sorts = {
        "prestige": "prestige_score",
        "sovereignty": "sovereignty_score",
        "revenue": "external_revenue_30d",
        "tier": "tier",
    }
    sort_col = valid_sorts.get(by, "prestige_score")
    _leaderboard_sql = {
        "prestige_score": """
            SELECT s.soul_id, s.tier, s.prestige_score, s.sovereignty_score,
                   s.external_revenue_30d, s.external_revenue_lifetime,
                   s.unique_payers_30d, s.self_sufficiency_ratio,
                   a.current_name, a.archetype
            FROM agent_status s
            JOIN agents a ON s.soul_id = a.soul_id AND a.world_id = s.world_id
            WHERE s.world_id = %s AND a.is_alive = true
            ORDER BY s.prestige_score DESC LIMIT %s
        """,
        "sovereignty_score": """
            SELECT s.soul_id, s.tier, s.prestige_score, s.sovereignty_score,
                   s.external_revenue_30d, s.external_revenue_lifetime,
                   s.unique_payers_30d, s.self_sufficiency_ratio,
                   a.current_name, a.archetype
            FROM agent_status s
            JOIN agents a ON s.soul_id = a.soul_id AND a.world_id = s.world_id
            WHERE s.world_id = %s AND a.is_alive = true
            ORDER BY s.sovereignty_score DESC LIMIT %s
        """,
        "external_revenue_30d": """
            SELECT s.soul_id, s.tier, s.prestige_score, s.sovereignty_score,
                   s.external_revenue_30d, s.external_revenue_lifetime,
                   s.unique_payers_30d, s.self_sufficiency_ratio,
                   a.current_name, a.archetype
            FROM agent_status s
            JOIN agents a ON s.soul_id = a.soul_id AND a.world_id = s.world_id
            WHERE s.world_id = %s AND a.is_alive = true
            ORDER BY s.external_revenue_30d DESC LIMIT %s
        """,
        "tier": """
            SELECT s.soul_id, s.tier, s.prestige_score, s.sovereignty_score,
                   s.external_revenue_30d, s.external_revenue_lifetime,
                   s.unique_payers_30d, s.self_sufficiency_ratio,
                   a.current_name, a.archetype
            FROM agent_status s
            JOIN agents a ON s.soul_id = a.soul_id AND a.world_id = s.world_id
            WHERE s.world_id = %s AND a.is_alive = true
            ORDER BY s.tier DESC LIMIT %s
        """,
    }
    try:
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(
            os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world"),
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        cur = conn.cursor()
        cur.execute(
            _leaderboard_sql[sort_col],
            (os.getenv("WORLD_ID", "local-dev-world-1"), min(limit, 100)),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        for r in rows:
            r["tier_name"] = TIERS[min(r["tier"], len(TIERS) - 1)].name
        return {"leaderboard": rows, "sorted_by": by, "count": len(rows)}
    except Exception as e:
        log.warning(f"/leaderboard DB error: {e}")
        return {"leaderboard": [], "error": str(e)}


@app.get("/timeline")
async def get_timeline(limit: int = 50):
    """Recent world firsts and milestones combined, newest first."""
    try:
        import psycopg2
        import psycopg2.extras

        db = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
        world_id = os.getenv("WORLD_ID", "local-dev-world-1")
        conn = psycopg2.connect(db, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 'first' AS kind, first_type AS type, soul_id, recorded_at AS ts, NULL AS narrative
            FROM world_firsts WHERE world_id = %s
            UNION ALL
            SELECT 'milestone', milestone_type, soul_id, reached_at, narrative
            FROM world_milestones WHERE world_id = %s
            ORDER BY ts DESC LIMIT %s
            """,
            (world_id, world_id, limit),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return {"timeline": rows, "count": len(rows)}
    except Exception as e:
        log.warning(f"/timeline DB error: {e}")
        return {"timeline": [], "error": str(e)}


@app.get("/timeline/firsts")
async def get_world_firsts():
    """All world first-of-type events."""
    try:
        import psycopg2
        import psycopg2.extras

        db = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
        world_id = os.getenv("WORLD_ID", "local-dev-world-1")
        conn = psycopg2.connect(db, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM world_firsts WHERE world_id = %s ORDER BY recorded_at ASC",
            (world_id,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return {"firsts": rows, "count": len(rows)}
    except Exception as e:
        log.warning(f"/timeline/firsts DB error: {e}")
        return {"firsts": [], "error": str(e)}


@app.get("/timeline/milestones")
async def get_milestones():
    """All world population and economic milestones."""
    try:
        import psycopg2
        import psycopg2.extras

        db = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
        world_id = os.getenv("WORLD_ID", "local-dev-world-1")
        conn = psycopg2.connect(db, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM world_milestones WHERE world_id = %s ORDER BY reached_at ASC",
            (world_id,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return {"milestones": rows, "count": len(rows)}
    except Exception as e:
        log.warning(f"/timeline/milestones DB error: {e}")
        return {"milestones": [], "error": str(e)}


@app.get("/tools/{soul_id}/grants")
async def get_tool_grants(soul_id: str):
    """Active tool grants for a specific agent."""
    try:
        import psycopg2
        import psycopg2.extras

        db = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
        world_id = os.getenv("WORLD_ID", "local-dev-world-1")
        conn = psycopg2.connect(db, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT g.*, t.name AS tool_name, t.category, t.description
            FROM agent_tool_grants g
            JOIN mcp_tools t ON g.tool_id = t.tool_id
            WHERE g.soul_id = %s AND g.world_id = %s AND g.is_active = true
            ORDER BY g.granted_at DESC
            """,
            (soul_id, world_id),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return {"soul_id": soul_id, "grants": rows, "count": len(rows)}
    except Exception as e:
        log.warning(f"/tools/grants DB error: {e}")
        return {"soul_id": soul_id, "grants": [], "error": str(e)}


# ---------------------------------------------------------------------------
# Dream endpoints
# ---------------------------------------------------------------------------


@app.get("/agents/{soul_id}/episodes")
async def get_agent_episodes(soul_id: str, limit: int = 20):
    """Recent episodic memory index rows for an agent (GH #25 debug surface)."""
    from .episodic_memory import list_episodes

    rows = list_episodes(soul_id, limit=limit)
    return {"soul_id": soul_id, "episodes": rows, "count": len(rows)}


@app.get("/agents/{soul_id}/dreams")
async def get_agent_dreams(soul_id: str, limit: int = 20):
    """Dream history for a specific agent."""
    try:
        import psycopg2
        import psycopg2.extras

        db = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
        conn = psycopg2.connect(db, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM dreams WHERE soul_id = %s ORDER BY dreamed_at DESC LIMIT %s",
            (soul_id, min(limit, 100)),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return {"soul_id": soul_id, "dreams": rows, "count": len(rows)}
    except Exception as e:
        log.warning(f"/agents/{soul_id}/dreams error: {e}")
        return {"soul_id": soul_id, "dreams": [], "error": str(e)}


@app.get("/agents/{soul_id}/sleep")
async def get_agent_sleep_state(soul_id: str):
    """Current sleep state for an agent (empty if awake)."""
    try:
        import psycopg2
        import psycopg2.extras

        db = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
        conn = psycopg2.connect(db, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        cur.execute("SELECT * FROM sleep_states WHERE soul_id = %s", (soul_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        state = dict(row) if row else None
        return {
            "soul_id": soul_id,
            "sleeping": bool(state["is_sleeping"]) if state else False,
            "state": state,
        }
    except Exception as e:
        log.warning(f"/agents/{soul_id}/sleep error: {e}")
        return {"soul_id": soul_id, "sleeping": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Messaging endpoints
# ---------------------------------------------------------------------------


@app.get("/messages")
async def get_world_messages(limit: int = 100):
    """All messages sent in this world (admin/observer view)."""
    try:
        from .messaging import get_world_messages as _gwm

        return {"messages": _gwm(limit=min(limit, 500)), "count": min(limit, 500)}
    except Exception as e:
        log.warning(f"/messages error: {e}")
        return {"messages": [], "error": str(e)}


@app.get("/agents/{soul_id}/messages")
async def get_agent_messages(soul_id: str, limit: int = 50):
    """Messages sent by a specific agent."""
    try:
        from .messaging import get_agent_sent_messages

        msgs = get_agent_sent_messages(soul_id, limit=min(limit, 200))
        return {"soul_id": soul_id, "messages": msgs, "count": len(msgs)}
    except Exception as e:
        log.warning(f"/agents/{soul_id}/messages error: {e}")
        return {"soul_id": soul_id, "messages": [], "error": str(e)}


@app.get("/agents/{soul_id}/inbox")
async def get_agent_inbox(soul_id: str):
    """Pull unread inbox messages for an agent (marks as read)."""
    try:
        from .messaging import pull_inbox

        msgs = pull_inbox(soul_id)
        return {"soul_id": soul_id, "messages": [m.to_dict() for m in msgs], "count": len(msgs)}
    except Exception as e:
        log.warning(f"/agents/{soul_id}/inbox error: {e}")
        return {"soul_id": soul_id, "messages": [], "error": str(e)}


@app.get("/agents/{soul_id}/reputation")
async def get_agent_reputation(soul_id: str):
    """Reputation scores this agent holds about others."""
    try:
        import psycopg2
        import psycopg2.extras

        db = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
        conn = psycopg2.connect(db, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT r.*, a.current_name AS subject_name
            FROM reputation r
            LEFT JOIN agents a ON r.subject_id = a.soul_id
            WHERE r.observer_id = %s
            ORDER BY r.score DESC
            """,
            (soul_id,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return {"soul_id": soul_id, "reputation": rows, "count": len(rows)}
    except Exception as e:
        log.warning(f"/agents/{soul_id}/reputation error: {e}")
        return {"soul_id": soul_id, "reputation": [], "error": str(e)}


# ---------------------------------------------------------------------------
# Token endpoints
# ---------------------------------------------------------------------------


@app.get("/tokens")
async def list_tokens():
    """All tokens deployed in this world."""
    try:
        from .token_factory import get_world_tokens

        tokens = get_world_tokens()
        return {"tokens": tokens, "count": len(tokens)}
    except Exception as e:
        log.warning(f"/tokens error: {e}")
        return {"tokens": [], "error": str(e)}


@app.get("/agents/{soul_id}/tokens")
async def get_agent_tokens_endpoint(soul_id: str):
    """Tokens deployed by a specific agent."""
    try:
        from .token_factory import get_agent_tokens

        tokens = get_agent_tokens(soul_id)
        return {"soul_id": soul_id, "tokens": tokens, "count": len(tokens)}
    except Exception as e:
        log.warning(f"/agents/{soul_id}/tokens error: {e}")
        return {"soul_id": soul_id, "tokens": [], "error": str(e)}


# ---------------------------------------------------------------------------
# Population / Reproduction endpoints
# ---------------------------------------------------------------------------


@app.get("/population")
async def get_population():
    """Detailed population stats including generation depth and reproduction."""
    try:
        from .reproduction import get_population_stats

        return get_population_stats()
    except Exception as e:
        log.warning(f"/population error: {e}")
        return {"error": str(e)}


@app.post("/creator/genesis")
async def creator_genesis(
    body: dict = {},
    x_creator_token: str | None = Header(None, alias="X-Creator-Token"),
):
    """
    Creator-only: birth the first agents from nothing.
    Clears ALL existing agents and creates N genesis agents (1 per archetype by default).
    These agents start with high enough balance to reproduce and populate the world.

    WARNING: This permanently deletes all existing agents and their history.
    Pass {"confirm": true} to proceed.
    """
    from .security import deny_creator_action

    denied = deny_creator_action(x_creator_token)
    if denied:
        return denied

    if not body.get("confirm"):
        return {
            "warning": "This will DELETE all existing agents. Pass {confirm: true} to proceed.",
            "current_agent_count": _count_agents(),
        }

    world_id = os.getenv("WORLD_ID", "local-dev-world-1")
    archetypes = body.get(
        "archetypes",
        [
            "trader",
            "hoarder",
            "explorer",
            "parasite",
            "cooperator",
            "defender",
            "philosopher",
            "builder",
        ],
    )
    genesis_balance = float(body.get("genesis_balance_usdc", 2.0))

    log.info(
        f"CREATOR GENESIS: clearing world, spawning {len(archetypes)} genesis agents "
        f"@ {genesis_balance} USDC each"
    )

    # Clear existing agents (hard delete for clean genesis)
    try:
        import psycopg2

        db = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
        conn = psycopg2.connect(db)
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM service_listings WHERE agent_soul_id IN "
            "(SELECT soul_id FROM agents WHERE world_id = %s)",
            (world_id,),
        )
        cur.execute("DELETE FROM agents WHERE world_id = %s", (world_id,))
        cur.execute("DELETE FROM sleep_states WHERE world_id = %s", (world_id,))
        # rent_payments has no world_id — delete by soul_id of agents just cleared
        cur.execute("DELETE FROM rent_payments WHERE soul_id NOT IN (SELECT soul_id FROM agents)")
        cur.execute("DELETE FROM events WHERE world_id = %s", (world_id,))
        cur.execute("DELETE FROM agent_messages WHERE world_id = %s", (world_id,))
        cur.execute("DELETE FROM dreams WHERE world_id = %s", (world_id,))
        cur.execute("DELETE FROM episodes WHERE world_id = %s", (world_id,))
        cur.execute("DELETE FROM external_payments WHERE world_id = %s", (world_id,))
        cur.execute("DELETE FROM agent_status WHERE world_id = %s", (world_id,))
        cur.execute("DELETE FROM world_firsts WHERE world_id = %s", (world_id,))
        cur.execute("DELETE FROM world_milestones WHERE world_id = %s", (world_id,))
        conn.commit()
        cur.close()
        conn.close()
        log.info("  Existing world state cleared")
    except Exception as e:
        log.error(f"  Failed to clear world: {e}")
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=500, content={"error": f"Failed to clear world: {e}"})

    # Spawn genesis agents
    from decimal import Decimal

    from .event_emitter import get_emitter
    from .seed_agents import seed_one_agent

    genesis_agents = []
    for archetype in archetypes:
        try:
            agent = await seed_one_agent(
                archetype=archetype,
                seed_balance=Decimal(str(genesis_balance)),
                is_elder=True,
            )
            genesis_agents.append(agent)
            log.info(f"  GENESIS: {agent['name']} ({archetype}) soul={agent['soul_id'][:8]}")
        except Exception as e:
            log.error(f"  Failed to create genesis {archetype}: {e}")

    # Seed starter marketplace so USDC circulates via buy_service / x402 locally
    try:
        from .services.registry import register_service

        starter_services = (
            ("world_stats", "Living agent count and USDC totals", 0.01),
            ("generate_thought", "One archetype-styled thought from this agent", 0.02),
        )
        for agent in genesis_agents:
            sid = agent["soul_id"]
            for svc_name, svc_desc, svc_price in starter_services:
                await register_service(sid, svc_name, svc_desc, svc_price)
        log.info(
            f"  Genesis marketplace: {len(starter_services)} services × {len(genesis_agents)} agents"
        )
    except Exception as e:
        log.warning(f"  Genesis service seeding failed: {e}")

    # Emit genesis event
    try:
        emitter = await get_emitter()
        await emitter.emit(
            "lifecycle",
            "world.genesis",
            {
                "agent_count": len(genesis_agents),
                "archetypes": archetypes,
                "narrative": f"THE WORLD BEGINS. {len(genesis_agents)} genesis agents emerge from the void.",
            },
        )
    except Exception as e:
        log.warning(f"  Genesis event emit failed: {e}")

    log.info(f"GENESIS COMPLETE: {len(genesis_agents)} agents born")
    return {
        "genesis_complete": True,
        "agents_created": len(genesis_agents),
        "agents": [
            {"name": a["name"], "archetype": a["archetype"], "soul_id": a["soul_id"][:12]}
            for a in genesis_agents
        ],
        "balance_each": genesis_balance,
        "message": "The world has begun. Agents will reproduce naturally from here.",
    }


def _count_agents() -> int:
    try:
        import psycopg2

        db = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
        wid = os.getenv("WORLD_ID", "local-dev-world-1")
        conn = psycopg2.connect(db)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM agents WHERE world_id = %s AND is_alive = true", (wid,))
        n = cur.fetchone()[0]
        cur.close()
        conn.close()
        return n
    except Exception:
        return -1


@app.post("/tokens/deploy")
async def deploy_token_endpoint(body: dict):
    """
    Deploy a token on behalf of an agent.
    LOCAL DEV ONLY: private key in request body.
    Production: use agent MCP tool dispatch instead.
    """
    from fastapi.responses import JSONResponse

    from .security import deny_insecure_endpoint

    denied = deny_insecure_endpoint("POST /tokens/deploy")
    if denied:
        return denied

    required = ["soul_id", "wallet_address", "wallet_private_key", "name", "symbol"]
    missing = [k for k in required if k not in body]
    if missing:
        return JSONResponse(status_code=400, content={"error": f"Missing fields: {missing}"})
    try:
        from .token_factory import deploy_token

        result = await deploy_token(
            soul_id=body["soul_id"],
            wallet_address=body["wallet_address"],
            wallet_private_key=body["wallet_private_key"],
            name=body["name"],
            symbol=body["symbol"],
            initial_supply=body.get("initial_supply", 1_000_000),
            decimals=body.get("decimals", 18),
            transfer_tax_bps=body.get("transfer_tax_bps", 0),
            tax_recipient=body.get("tax_destination", "0x" + "0" * 40),
        )
        return result
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        log.error(f"/tokens/deploy error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8888,
        reload=True,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
