"""
God Project — Agent Runtime
Entry point. Starts the FastAPI health/API server and the agent execution loop.
"""
import asyncio
import logging
import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("god.runtime")

app = FastAPI(title="God Runtime", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "world_id": os.getenv("WORLD_ID", "unknown"),
        "version": "0.1.0",
    }


@app.get("/agents")
async def list_agents():
    """List all living agents. Placeholder until DB layer is wired."""
    return {"agents": [], "count": 0}


@app.get("/events")
async def list_events(limit: int = 50):
    """Recent world events. Placeholder until event store is wired."""
    return {"events": [], "limit": limit}


if __name__ == "__main__":
    log.info("Starting God Runtime...")
    log.info(f"World ID: {os.getenv('WORLD_ID', 'local-dev-world-1')}")
    log.info(f"IPFS API: {os.getenv('IPFS_API', 'not configured')}")
    log.info(f"Chain RPC: {os.getenv('ANVIL_RPC', 'not configured')}")

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8888,
        reload=True,  # Hot reload in dev
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
