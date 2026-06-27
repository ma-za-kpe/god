"""
God Project — Agent Runtime
Entry point. FastAPI server + background daemons for rent collection and agent execution.
"""

import asyncio
import base64
import http.client
import json
import logging
import os
import pathlib
from contextlib import asynccontextmanager
from urllib.parse import urlparse

import httpx
import uvicorn
from fastapi import FastAPI, Header, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .agent_runner import agent_runner
from .creator.routes import router as creator_router
from .gpu import get_gpu_job_queue
from .health_checks import probe_tcp, probe_url
from .rent_daemon import rent_daemon
from .runtime_endpoints import (
    comfyui_health_url,
    endpoint_path,
    ipfs_api_url,
    nats_tcp_target,
    ollama_tags_url,
    redis_tcp_target,
    tts_base_url,
    tts_health_url,
    tts_synthesis_url,
)
from .services.routes import router as services_router
from .status_engine import TIERS, status_review_daemon

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("god.runtime")


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(1, value)


PUBLIC_IPFS_MAX_BYTES = _env_int("PUBLIC_IPFS_MAX_BYTES", 8 * 1024 * 1024)
PUBLIC_VOICE_AUDIO_MAX_BYTES = _env_int("PUBLIC_VOICE_AUDIO_MAX_BYTES", 10 * 1024 * 1024)

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


async def _twitch_chat_relay_daemon():
    """Tail social.agent.message_sent events and forward agent lines to Twitch chat.

    Runs every 3 seconds. Deduplicates by event_id so each line is sent once.
    Only active when TWITCH_ENABLED=true and TWITCH_DRY_RUN=false.
    Rate-limited by helix._RateLimiter (20 msg / 30s).
    """
    if os.getenv("TWITCH_ENABLED", "false").lower() not in ("1", "true", "yes"):
        return
    channel_name = os.getenv("TWITCH_CHANNEL_NAME", "")
    if not channel_name:
        log.warning("TWITCH_CHANNEL_NAME not set — chat relay disabled")
        return

    from .twitch.adapter import TwitchAdapter
    from .twitch.models import TwitchChatMessage

    adapter = TwitchAdapter()
    seen_ids: set[str] = set()
    RELAY_INTERVAL = 3

    while True:
        try:
            await asyncio.sleep(RELAY_INTERVAL)
            if adapter.dry_run or not adapter.enabled:
                continue

            from .world_snapshot import build_world_snapshot_async

            snap = await build_world_snapshot_async(events_limit=20)
            events = snap.get("events") or []
            msg_events = [
                ev
                for ev in events
                if str(ev.get("event_type", "")).endswith("message_sent")
                and ev.get("event_id") not in seen_ids
            ]
            # Newest first, cap at 2 per cycle so we don't burst the rate limit
            for ev in sorted(msg_events, key=lambda e: e.get("timestamp", 0))[-2:]:
                event_id = ev.get("event_id", "")
                seen_ids.add(event_id)
                payload = ev.get("payload") or {}
                if isinstance(payload, str):
                    import json as _json

                    try:
                        payload = _json.loads(payload)
                    except Exception:
                        payload = {}
                body = str(payload.get("content") or payload.get("body") or "").strip()
                sender = str(payload.get("sender_name") or ev.get("agent_id") or "").strip()
                if not body or len(body) < 4:
                    continue
                # Format: "AgentName: line" — truncate to 490 chars (Twitch limit is 500)
                line = f"{sender}: {body}"[:490] if sender else body[:490]
                chat_msg = TwitchChatMessage(message=line, channel_name=channel_name)
                result = await adapter.send_chat(chat_msg)
                if not result.ok:
                    log.debug("Twitch chat relay send failed: %s", result.reason)
                else:
                    log.debug("Twitch chat → %s: %s", channel_name, line[:80])

            # Trim seen_ids to avoid unbounded growth (keep last 500)
            if len(seen_ids) > 500:
                seen_ids = set(list(seen_ids)[-500:])

        except asyncio.CancelledError:
            break
        except Exception as exc:
            log.debug("Twitch chat relay daemon: %s", exc)


async def _ws_snapshot_daemon():
    """Periodic full snapshot push for WebSocket observers."""
    interval = int(os.getenv("WS_SNAPSHOT_INTERVAL_S", "8"))
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

    # Bootstrap NATS JetStream before agents start emitting.
    # Without this the first N emits race to create the stream and most lose.
    from .event_emitter import get_emitter

    try:
        await get_emitter()
        log.info("NATS JetStream ready")
    except Exception as _js_err:
        log.warning(f"NATS JetStream bootstrap failed (agents will retry): {_js_err}")

    _background_tasks.append(asyncio.create_task(rent_daemon(), name="rent_daemon"))
    _background_tasks.append(asyncio.create_task(agent_runner(), name="agent_runner"))
    _background_tasks.append(asyncio.create_task(status_review_daemon(), name="status_review"))
    _background_tasks.append(asyncio.create_task(_ws_snapshot_daemon(), name="ws_snapshot"))
    _background_tasks.append(asyncio.create_task(_agent_jobs_daemon(), name="agent_jobs"))
    _background_tasks.append(asyncio.create_task(_twitch_chat_relay_daemon(), name="twitch_relay"))

    # ── Twitch EventSub WebSocket (only when TWITCH_ENABLED=true) ────────────
    _twitch_client = None
    if os.getenv("TWITCH_ENABLED", "false").lower() in ("1", "true", "yes"):
        try:
            from .twitch.eventsub import EventSubClient

            _emitter = await get_emitter()
            _twitch_client = EventSubClient(emit_fn=_emitter.emit)
            _background_tasks.append(_twitch_client.start())
            log.info("Twitch EventSub client started")
        except Exception as _tw_err:
            log.warning("Twitch EventSub start failed (runtime continues): %s", _tw_err)
    else:
        log.info("Twitch disabled (TWITCH_ENABLED=false) — set to true to connect live")

    # ── YouTube Live Chat poller (only when YOUTUBE_ENABLED=true) ────────────
    _youtube_client = None
    if os.getenv("YOUTUBE_ENABLED", "false").lower() in ("1", "true", "yes"):
        try:
            from .youtube.chat_poller import ChatPoller

            _emitter = await get_emitter()
            _youtube_client = ChatPoller(emit_fn=_emitter.emit)
            _background_tasks.append(_youtube_client.start())
            log.info("YouTube Live Chat poller started")
        except Exception as _yt_err:
            log.warning("YouTube poller start failed (runtime continues): %s", _yt_err)
    else:
        log.info("YouTube disabled (YOUTUBE_ENABLED=false) — set to true to connect live")

    yield

    log.info("Shutting down daemons...")
    if _twitch_client is not None:
        _twitch_client.stop()
    if _youtube_client is not None:
        _youtube_client.stop()
    for task in _background_tasks:
        task.cancel()
    await asyncio.gather(*_background_tasks, return_exceptions=True)
    await close_pool()


app = FastAPI(title="God Runtime", version=RUNTIME_VERSION, lifespan=lifespan)


def _cors_allow_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8888",
        "http://127.0.0.1:8888",
        "http://localhost:10517",
        "http://127.0.0.1:10517",
    ]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(services_router)
app.include_router(creator_router)

_OBSERVER_DIR = pathlib.Path(__file__).parent.parent.parent / "observer"
if _OBSERVER_DIR.is_dir():
    app.mount("/observer", StaticFiles(directory=str(_OBSERVER_DIR), html=True), name="observer")


@app.get("/stage")
async def stage_page():
    """Serve the stage UI directly at /stage."""
    f = _OBSERVER_DIR / "stage.html"
    if f.exists():
        return FileResponse(str(f), media_type="text/html")
    return Response("stage not found", status_code=404)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "world_id": os.getenv("WORLD_ID", "unknown"),
        "version": RUNTIME_VERSION,
    }


def _db_ready() -> dict:
    try:
        import psycopg2

        conn = psycopg2.connect(
            os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world"),
            connect_timeout=2,
        )
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
        finally:
            conn.close()
        return {"ok": True, "probe": "postgres"}
    except Exception as exc:
        return {"ok": False, "probe": "postgres", "reason": str(exc)}


def _obs_ready() -> dict:
    obs_url = os.getenv("OBS_WEBSOCKET_URL", "ws://127.0.0.1:4444").strip()
    if not obs_url:
        return {"ok": True, "probe": "skipped", "reason": "not_configured"}
    parsed = urlparse(obs_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (4455 if parsed.scheme == "wss" else 4444)
    return probe_tcp(host, port, timeout=1.5)


def _ipfs_ready() -> dict:
    endpoint = ipfs_api_url()
    try:
        parsed_endpoint = urlparse(endpoint)
        if parsed_endpoint.scheme not in {"http", "https"} or not parsed_endpoint.hostname:
            return {
                "ok": False,
                "probe": "http",
                "url": endpoint,
                "reason": "invalid_ipfs_api",
            }
        connection_cls = (
            http.client.HTTPSConnection
            if parsed_endpoint.scheme == "https"
            else http.client.HTTPConnection
        )
        conn = connection_cls(parsed_endpoint.hostname, parsed_endpoint.port or 5001, timeout=2.0)
        try:
            conn.request("POST", "/api/v0/version")
            response = conn.getresponse()
            body = response.read(256)
            parsed = None
            try:
                parsed = json.loads(body.decode("utf-8")) if body else None
            except Exception:
                parsed = None
            return {
                "ok": 200 <= response.status < 400,
                "probe": "http",
                "url": endpoint_path(endpoint, "/api/v0/version"),
                "status_code": int(response.status),
                "body": parsed,
            }
        finally:
            conn.close()
    except Exception as exc:
        return {
            "ok": False,
            "probe": "http",
            "url": endpoint_path(endpoint, "/api/v0/version"),
            "reason": str(exc),
        }


async def _fish_synthesis_ready() -> dict:
    endpoint = tts_base_url()
    if not endpoint:
        return {"ok": False, "probe": "skipped", "reason": "not_configured"}
    try:
        timeout_seconds = max(1.0, float(os.getenv("VOICE_HEALTH_TIMEOUT_SECONDS", "90")))
    except ValueError:
        timeout_seconds = 90.0
    seed_path = pathlib.Path(__file__).resolve().parents[1] / "seed_utterances" / "philosopher.wav"
    if not seed_path.is_file():
        return {"ok": False, "probe": "tts", "reason": "seed_utterance_missing"}
    try:
        payload = {
            "text": "Ready check.",
            "references": [
                {
                    "audio": base64.b64encode(seed_path.read_bytes()).decode("utf-8"),
                    "text": "",
                }
            ],
            "format": "wav",
            "streaming": False,
        }
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            synthesis_url = tts_synthesis_url(endpoint)
            response = await client.post(synthesis_url, json=payload)
            if not 200 <= response.status_code < 300:
                return {
                    "ok": False,
                    "probe": "tts",
                    "endpoint": synthesis_url,
                    "status_code": int(response.status_code),
                    "reason": "tts_failed",
                }
            return {
                "ok": bool(response.content),
                "probe": "tts",
                "endpoint": synthesis_url,
                "byte_count": len(response.content or b""),
                "timeout_seconds": timeout_seconds,
            }
    except Exception as exc:
        return {
            "ok": False,
            "probe": "tts",
            "endpoint": tts_synthesis_url(endpoint),
            "reason": str(exc) or exc.__class__.__name__,
            "timeout_seconds": timeout_seconds,
        }


@app.get("/ready")
async def ready():
    streaming_mode = os.getenv("STREAMING_MODE", "auto").lower()
    obs_required = streaming_mode in ("1", "true", "yes", "on") or os.getenv(
        "OBS_REQUIRED", ""
    ).lower() in ("1", "true", "yes", "on")
    voice_enabled = os.getenv("VOICE_ENABLED", "true").lower() in ("1", "true", "yes", "on")
    redis_host, redis_port = redis_tcp_target()
    nats_host, nats_port = nats_tcp_target()
    checks = {
        "postgres": _db_ready(),
        "redis": probe_tcp(redis_host, redis_port, timeout=1.5),
        "nats": probe_tcp(nats_host, nats_port, timeout=1.5),
        "ipfs": probe_url(endpoint_path(ipfs_api_url(), "/debug/metrics/prometheus"), timeout=2.0),
        "comfyui": probe_url(comfyui_health_url(), timeout=2.0),
        "ollama": probe_url(ollama_tags_url(), timeout=2.0),
        "nginx_runtime": probe_tcp("127.0.0.1", 10515, timeout=1.5),
        "nginx_comfyui": probe_tcp("127.0.0.1", 10516, timeout=1.5),
        "nginx_observer": probe_tcp("127.0.0.1", 10517, timeout=1.5),
    }
    if voice_enabled or tts_base_url() or tts_health_url():
        checks["fish"] = await _fish_synthesis_ready()
    else:
        checks["fish"] = {"ok": True, "probe": "skipped", "reason": "voice_disabled"}
    if obs_required:
        checks["obs"] = _obs_ready()
    else:
        checks["obs"] = {"ok": True, "probe": "skipped", "reason": "obs_optional"}
    ok = all(check.get("ok") for check in checks.values())
    return {
        "ok": ok,
        "status": "ready" if ok else "not_ready",
        "world_id": os.getenv("WORLD_ID", "unknown"),
        "version": RUNTIME_VERSION,
        "checks": checks,
    }


@app.get("/diagnostics/gpu")
async def gpu_diagnostics():
    return get_gpu_job_queue().diagnostics()


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
                COALESCE(a.avatar_cid, '')           AS avatar_cid,
                COALESCE(NULLIF(a.rigged_avatar_cid, ''), a.avatar_cid, '') AS rigged_avatar_cid,
                COALESCE(a.vrm_avatar_url, '')       AS vrm_avatar_url,
                COALESCE(a.voice_model_cid, '')      AS voice_model_cid,
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

        snapshot = await build_world_snapshot_async(
            events_limit=min(events_limit, 200),
            messages_limit=min(messages_limit, 500),
        )
        if snapshot.get("agents"):
            try:
                import psycopg2
                import psycopg2.extras

                world_id = snapshot.get("world_id", os.getenv("WORLD_ID", "local-dev-world-1"))
                conn = psycopg2.connect(
                    os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world"),
                    cursor_factory=psycopg2.extras.RealDictCursor,
                )
                cur = conn.cursor()
                cur.execute(
                    """
                           SELECT soul_id,
                           COALESCE(avatar_cid, '') AS avatar_cid,
                           COALESCE(NULLIF(rigged_avatar_cid, ''), avatar_cid, '') AS rigged_avatar_cid,
                           COALESCE(vrm_avatar_url, '') AS vrm_avatar_url,
                           COALESCE(voice_model_cid, '') AS voice_model_cid
                    FROM agents
                    WHERE world_id = %s
                    """,
                    (world_id,),
                )
                cid_map = {row["soul_id"]: dict(row) for row in cur.fetchall()}
                cur.close()
                conn.close()
                for agent in snapshot["agents"]:
                    if not isinstance(agent, dict):
                        continue
                    cid_row = cid_map.get(agent.get("soul_id"))
                    if cid_row:
                        agent["avatar_cid"] = cid_row.get("avatar_cid", "")
                        agent["rigged_avatar_cid"] = cid_row.get("rigged_avatar_cid", "")
                        agent["vrm_avatar_url"] = cid_row.get("vrm_avatar_url", "")
                        agent["voice_model_cid"] = cid_row.get("voice_model_cid", "")
            except Exception as merge_error:
                log.debug(f"/world/snapshot CID merge skipped: {merge_error}")
        return snapshot
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


@app.get("/audience/status")
async def audience_status():
    """Current audience/patronage adapter configuration."""
    try:
        from .audience import build_audience_status

        return {
            "audience": build_audience_status(),
            "world_id": os.getenv("WORLD_ID", "local-dev-world-1"),
        }
    except Exception as e:
        log.warning(f"/audience/status error: {e}")
        return {"error": str(e), "world_id": os.getenv("WORLD_ID", "local-dev-world-1")}


@app.get("/audience/state")
async def audience_state(events_limit: int = 50, messages_limit: int = 80):
    """Current audience/patronage state layered over the latest world snapshot."""
    try:
        from .world_snapshot import build_world_snapshot_async

        snapshot = await build_world_snapshot_async(
            events_limit=min(events_limit, 200),
            messages_limit=min(messages_limit, 500),
        )
        return {
            "audience": snapshot.get("audience", {}),
            "showrunner": snapshot.get("showrunner", {}),
            "world_id": snapshot.get("world_id", os.getenv("WORLD_ID", "local-dev-world-1")),
            "epoch": snapshot.get("epoch"),
        }
    except Exception as e:
        log.warning(f"/audience/state error: {e}")
        return {"error": str(e), "world_id": os.getenv("WORLD_ID", "local-dev-world-1")}


@app.get("/content-bank/status")
async def content_bank_status():
    """Current content-bank configuration and supported asset types."""
    try:
        from .content_bank import build_content_bank_status

        return {
            "content_bank": build_content_bank_status(),
            "world_id": os.getenv("WORLD_ID", "local-dev-world-1"),
        }
    except Exception as e:
        log.warning(f"/content-bank/status error: {e}")
        return {"error": str(e), "world_id": os.getenv("WORLD_ID", "local-dev-world-1")}


@app.get("/content-bank/state")
async def content_bank_state(events_limit: int = 50, messages_limit: int = 80):
    """Current content-bank state layered over the latest world snapshot."""
    try:
        from .world_snapshot import build_world_snapshot_async

        snapshot = await build_world_snapshot_async(
            events_limit=min(events_limit, 200),
            messages_limit=min(messages_limit, 500),
        )
        return {
            "content_bank": snapshot.get("content_bank", {}),
            "audience": snapshot.get("audience", {}),
            "showrunner": snapshot.get("showrunner", {}),
            "world_id": snapshot.get("world_id", os.getenv("WORLD_ID", "local-dev-world-1")),
            "epoch": snapshot.get("epoch"),
        }
    except Exception as e:
        log.warning(f"/content-bank/state error: {e}")
        return {"error": str(e), "world_id": os.getenv("WORLD_ID", "local-dev-world-1")}


@app.get("/viewer/status")
async def viewer_status():
    """Current viewer overlay / extension configuration."""
    try:
        from .viewer import build_viewer_status

        return {
            "viewer": build_viewer_status(),
            "world_id": os.getenv("WORLD_ID", "local-dev-world-1"),
        }
    except Exception as e:
        log.warning(f"/viewer/status error: {e}")
        return {"error": str(e), "world_id": os.getenv("WORLD_ID", "local-dev-world-1")}


@app.get("/viewer/state")
async def viewer_state(events_limit: int = 50, messages_limit: int = 80):
    """Current viewer interaction state layered over the latest world snapshot."""
    try:
        from .world_snapshot import build_world_snapshot_async

        snapshot = await build_world_snapshot_async(
            events_limit=min(events_limit, 200),
            messages_limit=min(messages_limit, 500),
        )
        return {
            "viewer": snapshot.get("viewer", {}),
            "content_bank": snapshot.get("content_bank", {}),
            "audience": snapshot.get("audience", {}),
            "world_id": snapshot.get("world_id", os.getenv("WORLD_ID", "local-dev-world-1")),
            "epoch": snapshot.get("epoch"),
        }
    except Exception as e:
        log.warning(f"/viewer/state error: {e}")
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


@app.get("/voice/status")
async def voice_status():
    """Current voice stack configuration and health."""
    try:
        from .voice import build_voice_status

        return {
            "voice": build_voice_status(),
            "world_id": os.getenv("WORLD_ID", "local-dev-world-1"),
        }
    except Exception as e:
        log.warning(f"/voice/status error: {e}")
        return {"error": str(e), "world_id": os.getenv("WORLD_ID", "local-dev-world-1")}


@app.get("/voice/state")
async def voice_state(events_limit: int = 50, messages_limit: int = 80):
    """Current voice plan layered over the latest world snapshot."""
    try:
        from .world_snapshot import build_world_snapshot_async

        snapshot = await build_world_snapshot_async(
            events_limit=min(events_limit, 200),
            messages_limit=min(messages_limit, 500),
        )
        return {
            "voice": snapshot.get("voice", {}),
            "showrunner": snapshot.get("showrunner", {}),
            "broadcast": snapshot.get("broadcast", {}),
            "world_id": snapshot.get("world_id", os.getenv("WORLD_ID", "local-dev-world-1")),
            "epoch": snapshot.get("epoch"),
        }
    except Exception as e:
        log.warning(f"/voice/state error: {e}")
        return {"error": str(e), "world_id": os.getenv("WORLD_ID", "local-dev-world-1")}


@app.get("/voice/audio/{utterance_id}")
async def voice_audio(utterance_id: str):
    """Return synthesized WAV bytes for a given utterance_id (cached from last TTS call)."""
    from fastapi.responses import Response as FastResponse
    from .voice.engine import get_cached_audio

    audio = get_cached_audio(utterance_id)
    if audio is None:
        return FastResponse(status_code=404, content=b"")
    if len(audio) > PUBLIC_VOICE_AUDIO_MAX_BYTES:
        return FastResponse(status_code=413, content=b"")
    return FastResponse(
        content=audio,
        media_type="audio/wav",
        headers={
            "Cache-Control": "public, max-age=60",
        },
    )


@app.get("/ipfs/{cid}")
async def ipfs_proxy(cid: str):
    """Proxy IPFS content by CID so the observer can fetch portraits without a local gateway."""
    from fastapi.responses import Response as FastResponse

    if not cid or len(cid) > 160 or any(ch in cid for ch in "/\\?&#"):
        return FastResponse(status_code=400, content=b"")

    async def _cat_limited(client: httpx.AsyncClient, method: str) -> tuple[int, bytes]:
        chunks: list[bytes] = []
        total = 0
        async with client.stream(
            method,
            f"{ipfs_api}/api/v0/cat",
            params={"arg": cid},
        ) as response:
            if response.status_code != 200:
                return response.status_code, b""
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > PUBLIC_IPFS_MAX_BYTES:
                    return 413, b""
                chunks.append(chunk)
        return 200, b"".join(chunks)

    ipfs_api = (os.getenv("IPFS_API") or "http://localhost:5001").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            status_code, content = await _cat_limited(client, "POST")
            if status_code == 405:
                status_code, content = await _cat_limited(client, "GET")
            if status_code == 413:
                return FastResponse(status_code=413, content=b"")
            if status_code != 200 or not content:
                return FastResponse(status_code=404, content=b"")
            content_type = "image/png" if content[:4] == b"\x89PNG" else "application/octet-stream"
            return FastResponse(
                content=content,
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=3600",
                },
            )
    except Exception as exc:
        log.warning("ipfs_proxy cid=%s error=%s", cid, exc)
        return FastResponse(status_code=502, content=b"")


@app.get("/avatar/status")
async def avatar_status():
    """Current avatar stack configuration and health."""
    try:
        from .avatar import build_avatar_status

        return {
            "avatar": build_avatar_status(),
            "world_id": os.getenv("WORLD_ID", "local-dev-world-1"),
        }
    except Exception as e:
        log.warning(f"/avatar/status error: {e}")
        return {"error": str(e), "world_id": os.getenv("WORLD_ID", "local-dev-world-1")}


@app.get("/avatar/state")
async def avatar_state(events_limit: int = 50, messages_limit: int = 80):
    """Current avatar plan layered over the latest world snapshot."""
    try:
        from .world_snapshot import build_world_snapshot_async

        snapshot = await build_world_snapshot_async(
            events_limit=min(events_limit, 200),
            messages_limit=min(messages_limit, 500),
        )
        return {
            "avatar": snapshot.get("avatar", {}),
            "showrunner": snapshot.get("showrunner", {}),
            "voice": snapshot.get("voice", {}),
            "world_id": snapshot.get("world_id", os.getenv("WORLD_ID", "local-dev-world-1")),
            "epoch": snapshot.get("epoch"),
        }
    except Exception as e:
        log.warning(f"/avatar/state error: {e}")
        return {"error": str(e), "world_id": os.getenv("WORLD_ID", "local-dev-world-1")}


@app.get("/broadcast/state")
async def broadcast_state(events_limit: int = 50, messages_limit: int = 80):
    """Broadcast scene, captions, overlays, and OBS command plan."""
    try:
        from .world_snapshot import build_world_snapshot_async

        snapshot = await build_world_snapshot_async(
            events_limit=min(events_limit, 200),
            messages_limit=min(messages_limit, 500),
        )
        return {
            "broadcast": snapshot.get("broadcast", {}),
            "showrunner": snapshot.get("showrunner", {}),
            "nemo": snapshot.get("nemo", {}),
            "world_id": snapshot.get("world_id", os.getenv("WORLD_ID", "local-dev-world-1")),
            "epoch": snapshot.get("epoch"),
        }
    except Exception as e:
        log.warning(f"/broadcast/state error: {e}")
        return {"error": str(e), "world_id": os.getenv("WORLD_ID", "local-dev-world-1")}


@app.get("/broadcast/status")
async def broadcast_status():
    """Current broadcast adapter mode and transport configuration."""
    try:
        from .broadcast import build_broadcast_status

        return {
            "broadcast": build_broadcast_status(),
            "world_id": os.getenv("WORLD_ID", "local-dev-world-1"),
        }
    except Exception as e:
        log.warning(f"/broadcast/status error: {e}")
        return {"error": str(e), "world_id": os.getenv("WORLD_ID", "local-dev-world-1")}


@app.get("/broadcast/youtube-proof")
async def broadcast_youtube_proof(events_limit: int = 50, messages_limit: int = 80):
    """Operator-facing YouTube private-stream proof and fallback readiness."""
    try:
        from .broadcast import build_youtube_live_proof_report
        from .world_snapshot import build_world_snapshot_async

        snapshot = await build_world_snapshot_async(
            events_limit=min(events_limit, 200),
            messages_limit=min(messages_limit, 500),
        )
        return {
            "proof": build_youtube_live_proof_report(
                snapshot,
                gpu_diagnostics=get_gpu_job_queue().diagnostics(),
            ),
            "world_id": snapshot.get("world_id", os.getenv("WORLD_ID", "local-dev-world-1")),
            "epoch": snapshot.get("epoch"),
        }
    except Exception as e:
        log.warning(f"/broadcast/youtube-proof error: {e}")
        return {"error": str(e), "world_id": os.getenv("WORLD_ID", "local-dev-world-1")}


@app.get("/resilience/status")
async def resilience_status():
    """Current runtime resilience and fallback posture."""
    try:
        from .resilience import build_resilience_status
        from .world_snapshot import build_world_snapshot_async

        snapshot = await build_world_snapshot_async(events_limit=25, messages_limit=25)
        return {
            "resilience": build_resilience_status(snapshot),
            "world_id": snapshot.get("world_id", os.getenv("WORLD_ID", "local-dev-world-1")),
            "epoch": snapshot.get("epoch"),
        }
    except Exception as e:
        log.warning(f"/resilience/status error: {e}")
        return {"error": str(e), "world_id": os.getenv("WORLD_ID", "local-dev-world-1")}


@app.get("/resilience/state")
async def resilience_state(events_limit: int = 50, messages_limit: int = 80):
    """Current resilience state layered over the latest world snapshot."""
    try:
        from .world_snapshot import build_world_snapshot_async

        snapshot = await build_world_snapshot_async(
            events_limit=min(events_limit, 200),
            messages_limit=min(messages_limit, 500),
        )
        return {
            "resilience": snapshot.get("resilience", {}),
            "broadcast": snapshot.get("broadcast", {}),
            "nemo": snapshot.get("nemo", {}),
            "world_id": snapshot.get("world_id", os.getenv("WORLD_ID", "local-dev-world-1")),
            "epoch": snapshot.get("epoch"),
        }
    except Exception as e:
        log.warning(f"/resilience/state error: {e}")
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
            """
            FROM events
            WHERE world_id = %s
              AND NOT (
                event_type = 'social.agent.message_sent'
                AND COALESCE(payload->>'is_public', 'false') != 'true'
              )
            ORDER BY timestamp DESC LIMIT %s
            """,
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
async def get_agent_env(
    soul_id: str,
    x_creator_token: str | None = Header(None, alias="X-Creator-Token"),
):
    """Read-only environment summary for an agent (observer / debug)."""
    from .security import deny_creator_action

    denied = deny_creator_action(x_creator_token)
    if denied:
        return denied

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
async def get_tool_grants(
    soul_id: str,
    x_creator_token: str | None = Header(None, alias="X-Creator-Token"),
):
    """Active tool grants for a specific agent."""
    from .security import deny_creator_action

    denied = deny_creator_action(x_creator_token)
    if denied:
        return denied

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
async def get_agent_episodes(
    soul_id: str,
    limit: int = 20,
    x_creator_token: str | None = Header(None, alias="X-Creator-Token"),
):
    """Recent episodic memory index rows for an agent (GH #25 debug surface)."""
    from .security import deny_creator_action

    denied = deny_creator_action(x_creator_token)
    if denied:
        return denied

    from .episodic_memory import list_episodes

    rows = list_episodes(soul_id, limit=limit)
    return {"soul_id": soul_id, "episodes": rows, "count": len(rows)}


@app.get("/agents/{soul_id}/dreams")
async def get_agent_dreams(
    soul_id: str,
    limit: int = 20,
    x_creator_token: str | None = Header(None, alias="X-Creator-Token"),
):
    """Dream history for a specific agent."""
    from .security import deny_creator_action

    denied = deny_creator_action(x_creator_token)
    if denied:
        return denied

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
async def get_agent_sleep_state(
    soul_id: str,
    x_creator_token: str | None = Header(None, alias="X-Creator-Token"),
):
    """Current sleep state for an agent (empty if awake)."""
    from .security import deny_creator_action

    denied = deny_creator_action(x_creator_token)
    if denied:
        return denied

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
async def get_world_messages(
    limit: int = 100,
    x_creator_token: str | None = Header(None, alias="X-Creator-Token"),
):
    """All messages sent in this world (admin/observer view)."""
    from .security import deny_creator_action

    denied = deny_creator_action(x_creator_token)
    if denied:
        return denied

    try:
        from .messaging import get_world_messages as _gwm

        return {"messages": _gwm(limit=min(limit, 500)), "count": min(limit, 500)}
    except Exception as e:
        log.warning(f"/messages error: {e}")
        return {"messages": [], "error": str(e)}


@app.get("/agents/{soul_id}/messages")
async def get_agent_messages(
    soul_id: str,
    limit: int = 50,
    x_creator_token: str | None = Header(None, alias="X-Creator-Token"),
):
    """Messages sent by a specific agent."""
    from .security import deny_creator_action

    denied = deny_creator_action(x_creator_token)
    if denied:
        return denied

    try:
        from .messaging import get_agent_sent_messages

        msgs = get_agent_sent_messages(soul_id, limit=min(limit, 200))
        return {"soul_id": soul_id, "messages": msgs, "count": len(msgs)}
    except Exception as e:
        log.warning(f"/agents/{soul_id}/messages error: {e}")
        return {"soul_id": soul_id, "messages": [], "error": str(e)}


@app.get("/agents/{soul_id}/inbox")
async def get_agent_inbox(
    soul_id: str,
    mark_read: bool = False,
    x_creator_token: str | None = Header(None, alias="X-Creator-Token"),
):
    """Inspect unread inbox messages for an agent. mark_read=true consumes them."""
    from .security import deny_creator_action

    denied = deny_creator_action(x_creator_token)
    if denied:
        return denied

    try:
        from .messaging import pull_inbox

        msgs = pull_inbox(soul_id, mark_read=mark_read)
        return {"soul_id": soul_id, "messages": [m.to_dict() for m in msgs], "count": len(msgs)}
    except Exception as e:
        log.warning(f"/agents/{soul_id}/inbox error: {e}")
        return {"soul_id": soul_id, "messages": [], "error": str(e)}


@app.get("/agents/{soul_id}/reputation")
async def get_agent_reputation(
    soul_id: str,
    x_creator_token: str | None = Header(None, alias="X-Creator-Token"),
):
    """Reputation scores this agent holds about others."""
    from .security import deny_creator_action

    denied = deny_creator_action(x_creator_token)
    if denied:
        return denied

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

    comfyui_probe = probe_url(comfyui_health_url())
    if not comfyui_probe.get("ok"):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=503,
            content={
                "error": "ComfyUI is not healthy",
                "probe": comfyui_probe,
            },
        )

    fish_probe = probe_url(tts_health_url())
    if not fish_probe.get("ok"):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=503,
            content={
                "error": "fish-speech is not healthy",
                "probe": fish_probe,
            },
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
    genesis_failures = []
    for archetype in archetypes:
        try:
            agent = await seed_one_agent(
                archetype=archetype,
                seed_balance=Decimal(str(genesis_balance)),
                is_elder=True,
                block_on_avatar_genesis=True,
                require_avatar_assets=True,
            )
            if not agent.get("avatar_cid"):
                raise RuntimeError(
                    f"genesis agent missing avatar: avatar_cid={agent.get('avatar_cid')!r}"
                )
            if not agent.get("voice_model_cid"):
                log.warning(
                    f"  GENESIS: {archetype} voice embedding failed — agent created without voice"
                )
            genesis_agents.append(agent)
            log.info(f"  GENESIS: {agent['name']} ({archetype}) soul={agent['soul_id'][:8]}")
        except Exception as e:
            log.error(f"  Failed to create genesis {archetype}: {e}")
            genesis_failures.append({"archetype": archetype, "error": str(e)})

    if not genesis_agents:
        try:
            _clear_world_state(world_id)
        except Exception as cleanup_error:
            log.error(f"  Cleanup after genesis failure failed: {cleanup_error}")
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=500,
            content={
                "error": "All genesis agents failed to create",
                "failures": genesis_failures,
            },
        )

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
            {
                "name": a["name"],
                "archetype": a["archetype"],
                "soul_id": a["soul_id"],
                "wallet_address": a["wallet_address"],
                "graph_cid": a.get("graph_cid", ""),
                "avatar_cid": a.get("avatar_cid", ""),
                "rigged_avatar_cid": a.get("rigged_avatar_cid", ""),
                "voice_model_cid": a.get("voice_model_cid", ""),
                "avatar_genesis_status": a.get("avatar_genesis_status", ""),
            }
            for a in genesis_agents
        ],
        "balance_each": genesis_balance,
        "message": "The world has begun. Agents will reproduce naturally from here.",
    }


@app.post("/creator/one")
@app.post("/one")
async def creator_one(
    body: dict = {},
    x_creator_token: str | None = Header(None, alias="X-Creator-Token"),
):
    """
    Creator-only: clear the world and create exactly one talk-first agent.

    This is the smoke-test path. It blocks until both avatar and voice assets
    are generated and pinned, and fails if either asset is missing.
    """
    from decimal import Decimal

    from .security import deny_creator_action

    denied = deny_creator_action(x_creator_token)
    if denied:
        return denied

    if not body.get("confirm"):
        return {
            "warning": "This will DELETE all existing agents and create one agent. Pass {confirm: true} to proceed.",
            "current_agent_count": _count_agents(),
        }

    world_id = os.getenv("WORLD_ID", "local-dev-world-1")
    archetype = str(body.get("archetype") or "philosopher").strip().lower()
    seed_balance = float(body.get("seed_balance_usdc", 2.0))

    try:
        from .avatar.archetype_config import ARCHETYPE_CONFIGS

        if archetype not in ARCHETYPE_CONFIGS:
            return {
                "error": f"unknown archetype: {archetype}",
                "valid_archetypes": sorted(ARCHETYPE_CONFIGS),
            }
    except Exception as exc:
        return {"error": f"failed to validate archetype: {exc}"}

    log.info("CREATOR ONE: clearing world, spawning one %s agent", archetype)

    try:
        _clear_world_state(world_id)
    except Exception as e:
        log.error(f"  Failed to clear world: {e}")
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=500, content={"error": f"Failed to clear world: {e}"})

    from .seed_agents import seed_one_agent

    try:
        agent = await seed_one_agent(
            archetype=archetype,
            seed_balance=Decimal(str(seed_balance)),
            is_elder=True,
            block_on_avatar_genesis=True,
            require_avatar_assets=True,
        )
    except Exception as exc:
        log.error("  Failed to create one-agent world: %s", exc)
        return {"error": str(exc)}

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
            SELECT soul_id, current_name, archetype,
                   COALESCE(avatar_cid, '') AS avatar_cid,
                   COALESCE(NULLIF(rigged_avatar_cid, ''), avatar_cid, '') AS rigged_avatar_cid,
                   COALESCE(vrm_avatar_url, '') AS vrm_avatar_url,
                   COALESCE(voice_model_cid, '') AS voice_model_cid
            FROM agents
            WHERE world_id = %s
            ORDER BY birth_timestamp DESC
            LIMIT 1
            """,
            (world_id,),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
    except Exception as exc:
        return {"error": f"failed to verify one-agent world: {exc}", "agent": agent}

    if not row:
        return {"error": "one-agent world did not persist", "agent": agent}
    if not row.get("avatar_cid") or not row.get("voice_model_cid"):
        return {
            "error": "one-agent world missing required assets",
            "agent": dict(row),
            "seed_agent": agent,
        }

    try:
        from .messaging import send_message

        bootstrap_line = (
            body.get("bootstrap_line")
            or body.get("speech")
            or f"I am {row.get('current_name')}. This world has one voice now."
        )
        await send_message(
            sender_soul_id=str(row["soul_id"]),
            recipient_soul_id=str(row["soul_id"]),
            body=str(bootstrap_line),
            subject="solo bootstrap",
            message_type="direct",
            metadata={"source": "creator_one", "solo": True},
        )
    except Exception as exc:
        log.warning("  Solo bootstrap speech failed: %s", exc)

    return {
        "one_complete": True,
        "agent": dict(row),
        "seed_agent": agent,
        "message": "One agent is live with both avatar and voice assets.",
    }


@app.post("/creator/birth")
async def creator_birth(
    body: dict = {},
    x_creator_token: str | None = Header(None, alias="X-Creator-Token"),
):
    """Add one agent by archetype without deleting existing agents."""
    from decimal import Decimal

    from .security import deny_creator_action

    denied = deny_creator_action(x_creator_token)
    if denied:
        return denied

    archetype = str(body.get("archetype") or "philosopher").strip().lower()
    seed_balance = float(body.get("seed_balance_usdc", 2.0))

    from .seed_agents import seed_one_agent

    try:
        agent = await seed_one_agent(
            archetype=archetype,
            seed_balance=Decimal(str(seed_balance)),
            is_elder=True,
            block_on_avatar_genesis=bool(body.get("block_on_avatar_genesis", True)),
        )
    except Exception as exc:
        log.error("creator_birth failed: %s", exc)
        return JSONResponse(status_code=500, content={"error": str(exc)})

    return {"status": "born", "archetype": archetype, "agent": agent}


def _clear_world_state(world_id: str) -> None:
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
        host=os.getenv("UVICORN_HOST", "127.0.0.1"),
        port=8888,
        reload=os.getenv("UVICORN_RELOAD", "false").lower() in ("1", "true", "yes"),
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
