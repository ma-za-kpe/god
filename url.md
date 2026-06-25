# Access URLs

Current setup:

- Observer UI: http://localhost:3000
- Stage view: http://localhost:3000/stage
- Local runtime tunnel: http://localhost:18888
- Agents API: http://localhost:18888/agents
- World snapshot: http://localhost:18888/world/snapshot
- Recent events: http://localhost:18888/events
- API docs: http://localhost:18888/docs

Cloud status:

- The cloud runtime has 8 live genesis agents.
- All 8 ComfyUI portraits were generated and pinned to IPFS.
- The observer pages now read the runtime URL from `window.RUNTIME_URL` and fall back to `http://localhost:18888`.
