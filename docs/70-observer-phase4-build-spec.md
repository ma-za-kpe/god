# Observer Phase 4 — Build Specification

> Implementation spec for converting the Phase 1 single-file observer (`observer/index.html`) into the Phase 4 React + Vite + Three.js app described in doc 43. Covers project setup, component architecture, data hooks, and the Phase 4.0 milestone build steps.

---

## Project Setup

### Directory Structure After Migration

```
observer/
  index.html          ← Phase 1 (kept, served at /classic)
  package.json        ← NEW
  vite.config.js      ← NEW
  tailwind.config.js  ← NEW
  src/
    main.jsx          ← NEW — React entry point
    App.jsx           ← NEW — root component, router
    store.js          ← NEW — Zustand global state
    hooks/
      useWorld.js     ← NEW — polling /agents, /stats, /events
      useTimeline.js  ← NEW — polling /timeline/firsts, /milestones
      useAgent.js     ← NEW — single-agent detail + /status/{id}
    components/
      Header.jsx      ← converted from #hdr in index.html
      DramaFeed.jsx   ← converted from #events in index.html
      WorldMap.jsx     ← NEW — Three.js terrain + agent sprites
      AgentAvatar.jsx  ← NEW — per-agent 3D or billboard sprite
      AgentInspector.jsx ← NEW — click-through detail panel
      Leaderboard.jsx  ← NEW — /leaderboard endpoint
      MilestoneBar.jsx ← NEW — world firsts strip at bottom
      StatsPanel.jsx   ← converted from stats pills in index.html
  Dockerfile          ← update to build React app
```

### `package.json`

```json
{
  "name": "god-observer",
  "private": true,
  "version": "0.4.0",
  "scripts": {
    "dev":   "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@react-three/drei":    "^9.x",
    "@react-three/fiber":   "^8.x",
    "react":                "^18.x",
    "react-dom":            "^18.x",
    "three":                "^0.163.x",
    "zustand":              "^4.x",
    "react-router-dom":     "^6.x"
  },
  "devDependencies": {
    "@vitejs/plugin-react":  "^4.x",
    "autoprefixer":          "^10.x",
    "postcss":               "^8.x",
    "tailwindcss":           "^3.x",
    "vite":                  "^5.x"
  }
}
```

### `vite.config.js`

```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8888',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
```

### `tailwind.config.js`

```js
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: { mono: ['"Courier New"', 'monospace'] },
      colors: {
        god: {
          bg:      '#050510',
          surface: 'rgba(10,10,30,0.92)',
          border:  'rgba(80,80,200,0.18)',
          green:   '#70ffaa',
          muted:   '#9090cc',
          text:    '#c8c8e0',
        },
      },
    },
  },
}
```

---

## Zustand Store (`store.js`)

```js
import { create } from 'zustand'

export const useGodStore = create((set) => ({
  // World state
  agents:     [],
  stats:      {},
  events:     [],
  firsts:     [],
  milestones: [],
  leaderboard: [],

  // UI state
  selectedSoulId:  null,
  followMode:      false,
  dramaFilter:     'all',   // 'all' | event_type

  // Actions
  setAgents:      (agents)     => set({ agents }),
  setStats:       (stats)      => set({ stats }),
  setEvents:      (events)     => set({ events }),
  setFirsts:      (firsts)     => set({ firsts }),
  setMilestones:  (milestones) => set({ milestones }),
  setLeaderboard: (lb)         => set({ leaderboard: lb }),
  selectAgent:    (id)         => set({ selectedSoulId: id }),
  setFollowMode:  (v)          => set({ followMode: v }),
}))
```

---

## Data Hooks

### `hooks/useWorld.js`

```js
import { useEffect } from 'react'
import { useGodStore } from '../store'

const BASE = '/api'
const AGENT_POLL_MS  = 5_000
const EVENTS_POLL_MS = 2_000
const STATS_POLL_MS  = 10_000

export function useWorld() {
  const { setAgents, setStats, setEvents } = useGodStore()

  useEffect(() => {
    let alive = true

    const fetchAgents = async () => {
      try {
        const r = await fetch(`${BASE}/agents`)
        if (r.ok) setAgents((await r.json()).agents || [])
      } catch {}
      if (alive) setTimeout(fetchAgents, AGENT_POLL_MS)
    }

    const fetchStats = async () => {
      try {
        const r = await fetch(`${BASE}/stats`)
        if (r.ok) setStats(await r.json())
      } catch {}
      if (alive) setTimeout(fetchStats, STATS_POLL_MS)
    }

    const fetchEvents = async () => {
      try {
        const r = await fetch(`${BASE}/events?limit=30`)
        if (r.ok) setEvents((await r.json()).events || [])
      } catch {}
      if (alive) setTimeout(fetchEvents, EVENTS_POLL_MS)
    }

    fetchAgents(); fetchStats(); fetchEvents()
    return () => { alive = false }
  }, [])
}
```

### `hooks/useTimeline.js`

```js
import { useEffect } from 'react'
import { useGodStore } from '../store'

export function useTimeline() {
  const { setFirsts, setMilestones, setLeaderboard } = useGodStore()

  useEffect(() => {
    let alive = true

    const poll = async () => {
      try {
        const [fr, mr, lb] = await Promise.all([
          fetch('/api/timeline/firsts'),
          fetch('/api/timeline/milestones'),
          fetch('/api/leaderboard?by=prestige&limit=10'),
        ])
        if (fr.ok)  setFirsts((await fr.json()).firsts || [])
        if (mr.ok)  setMilestones((await mr.json()).milestones || [])
        if (lb.ok)  setLeaderboard((await lb.json()).leaderboard || [])
      } catch {}
      if (alive) setTimeout(poll, 30_000)
    }

    poll()
    return () => { alive = false }
  }, [])
}
```

---

## Components

### `WorldMap.jsx` — Three.js Scene (Phase 4.0)

Phase 4.0 uses a flat hex grid (same layout as Phase 1) rendered in Three.js, with sprites replacing canvas circles.

```jsx
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Billboard, Text } from '@react-three/drei'
import { AgentAvatar } from './AgentAvatar'
import { useGodStore } from '../store'

const ARCHETYPE_COLORS = {
  trader:     '#ffaa44',
  hoarder:    '#cc8800',
  explorer:   '#44ffcc',
  parasite:   '#ff4488',
  cooperator: '#44ff88',
  defender:   '#4488ff',
  philosopher:'#aa88ff',
  builder:    '#ff8844',
}

function HexGrid({ agents }) {
  // Map agent index to a hex position using axial coordinates
  // Simple spiral layout: center agent at (0,0), next 6 at ring 1, etc.
  return (
    <>
      {agents.map((agent, i) => {
        const pos = hexToWorld(indexToHex(i))
        return (
          <AgentAvatar
            key={agent.soul_id}
            agent={agent}
            position={[pos.x, 0, pos.z]}
            color={ARCHETYPE_COLORS[agent.archetype] || '#888888'}
          />
        )
      })}
    </>
  )
}

export function WorldMap() {
  const agents = useGodStore(s => s.agents)
  const living = agents.filter(a => a.is_alive)

  return (
    <Canvas
      className="flex-1"
      camera={{ position: [0, 30, 40], fov: 50 }}
      gl={{ antialias: true }}
    >
      <ambientLight intensity={0.4} />
      <pointLight position={[10, 30, 10]} intensity={1} />
      <HexGrid agents={living} />
      <OrbitControls enablePan enableZoom enableRotate />
    </Canvas>
  )
}

// Axial hex coordinate → world XZ position
function hexToWorld({ q, r }) {
  const size = 3.5
  return {
    x: size * (3/2 * q),
    z: size * (Math.sqrt(3)/2 * q + Math.sqrt(3) * r),
  }
}

function indexToHex(i) {
  // Spiral outward from center
  if (i === 0) return { q: 0, r: 0 }
  let ring = 1, count = 1
  while (count + 6 * ring <= i) { count += 6 * ring; ring++ }
  const posInRing = i - count
  const dirs = [[1,-1],[1,0],[0,1],[-1,1],[-1,0],[0,-1]]
  const dir = Math.floor(posInRing / ring)
  const step = posInRing % ring
  const startQ = -ring * dirs[(dir + 4) % 6][0]
  const startR = -ring * dirs[(dir + 4) % 6][1]
  return { q: startQ + dirs[dir][0] * step, r: startR + dirs[dir][1] * step }
}
```

### `AgentAvatar.jsx`

```jsx
import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { Billboard, Text } from '@react-three/drei'
import { useGodStore } from '../store'

export function AgentAvatar({ agent, position, color }) {
  const meshRef = useRef()
  const selectAgent = useGodStore(s => s.selectAgent)
  const selected = useGodStore(s => s.selectedSoulId) === agent.soul_id

  // Pulse sleeping agents
  useFrame((state) => {
    if (!meshRef.current) return
    if (agent.is_sleeping) {
      meshRef.current.scale.setScalar(
        0.9 + 0.1 * Math.sin(state.clock.elapsedTime * 0.6 * Math.PI)
      )
    } else {
      meshRef.current.scale.setScalar(1)
    }
  })

  const opacity = agent.is_sleeping ? 0.5 : 1.0
  const emissive = selected ? '#ffffff' : color

  return (
    <group position={position} onClick={() => selectAgent(agent.soul_id)}>
      <mesh ref={meshRef}>
        <sphereGeometry args={[0.6, 16, 16]} />
        <meshStandardMaterial
          color={color}
          emissive={emissive}
          emissiveIntensity={selected ? 0.5 : 0.1}
          transparent
          opacity={opacity}
        />
      </mesh>

      <Billboard follow={true} lockX={false} lockY={false} lockZ={false}>
        <Text
          position={[0, 1.2, 0]}
          fontSize={0.4}
          color="#c8c8e0"
          anchorX="center"
          anchorY="bottom"
        >
          {agent.is_sleeping ? '💤 ' : ''}{(agent.current_name || agent.soul_id.slice(0,8))}
        </Text>
      </Billboard>
    </group>
  )
}
```

### `AgentInspector.jsx`

```jsx
import { useGodStore } from '../store'
import { useState, useEffect } from 'react'

export function AgentInspector() {
  const soulId = useGodStore(s => s.selectedSoulId)
  const agents = useGodStore(s => s.agents)
  const selectAgent = useGodStore(s => s.selectAgent)

  const [status, setStatus] = useState(null)
  const [dreams, setDreams] = useState([])

  const agent = agents.find(a => a.soul_id === soulId)

  useEffect(() => {
    if (!soulId) return
    fetch(`/api/status/${soulId}`).then(r => r.json()).then(setStatus).catch(() => {})
    fetch(`/api/agents/${soulId}/dreams?limit=5`).then(r => r.json()).then(d => setDreams(d.dreams || [])).catch(() => {})
  }, [soulId])

  if (!agent) return null

  return (
    <div className="absolute right-4 top-12 w-72 bg-god-surface border border-god-border rounded-lg p-4 font-mono text-sm">
      <div className="flex justify-between items-center mb-3">
        <span className="text-god-green font-bold">{agent.current_name || agent.soul_id.slice(0,8)}</span>
        <button onClick={() => selectAgent(null)} className="text-god-muted hover:text-white">✕</button>
      </div>

      <div className="space-y-1 text-god-text text-xs">
        <div><span className="text-god-muted">archetype:</span> {agent.archetype}</div>
        <div><span className="text-god-muted">balance:</span> ${parseFloat(agent.balance_usdc || 0).toFixed(4)}</div>
        <div><span className="text-god-muted">rent paid:</span> {agent.rent_paid_count} / missed: {agent.rent_miss_count}</div>
        {status && (
          <>
            <div><span className="text-god-muted">tier:</span> {status.tier_name} ({status.tier})</div>
            <div><span className="text-god-muted">prestige:</span> {status.prestige_score}</div>
          </>
        )}
        {agent.is_sleeping && (
          <div className="text-blue-400">💤 dreaming…</div>
        )}
      </div>

      {dreams.length > 0 && (
        <div className="mt-3 border-t border-god-border pt-2">
          <div className="text-god-muted text-xs mb-1">last dream:</div>
          <div className="text-god-text text-xs italic">
            "{dreams[0].mutation_proposed?.slice(0, 80)}…"
            <span className={dreams[0].mutation_accepted ? 'text-green-400' : 'text-red-400'}>
              {dreams[0].mutation_accepted ? ' [kept]' : ' [discarded]'}
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
```

### `MilestoneBar.jsx`

```jsx
import { useGodStore } from '../store'

const FIRST_ICONS = {
  'first.birth':         '▶',
  'first.death':         '★',
  'first.rent_paid':     '◈',
  'first.reproduction':  '⬡',
  'first.coalition':     '◎',
  'first.token_deployed':'⊕',
  'first.consciousness_signal': '◉',
}

export function MilestoneBar() {
  const firsts = useGodStore(s => s.firsts)

  return (
    <div className="h-8 bg-god-surface border-t border-god-border flex items-center px-4 gap-4 overflow-x-auto flex-shrink-0">
      {firsts.map(f => (
        <span key={f.first_id} className="text-xs text-god-muted whitespace-nowrap" title={f.first_type}>
          {FIRST_ICONS[f.first_type] || '◦'} {f.first_type.replace('first.', '')}
        </span>
      ))}
      {firsts.length === 0 && (
        <span className="text-xs text-god-muted italic">no world firsts yet</span>
      )}
    </div>
  )
}
```

---

## `App.jsx` — Root Layout

```jsx
import { useWorld } from './hooks/useWorld'
import { useTimeline } from './hooks/useTimeline'
import { WorldMap } from './components/WorldMap'
import { DramaFeed } from './components/DramaFeed'
import { AgentInspector } from './components/AgentInspector'
import { MilestoneBar } from './components/MilestoneBar'
import { Header } from './components/Header'

export default function App() {
  useWorld()
  useTimeline()

  return (
    <div className="flex flex-col h-screen bg-god-bg text-god-text font-mono overflow-hidden">
      <Header />
      <div className="flex flex-1 overflow-hidden relative">
        <WorldMap />
        <DramaFeed />
        <AgentInspector />
      </div>
      <MilestoneBar />
    </div>
  )
}
```

---

## Docker Update

Update `observer/Dockerfile` to build the React app:

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
# Serve Phase 4 app at /
COPY --from=build /app/dist /usr/share/nginx/html
# Serve Phase 1 fallback at /classic
COPY index.html /usr/share/nginx/html/classic/index.html
EXPOSE 3000
```

`nginx.conf` (add to observer directory):
```nginx
server {
  listen 3000;
  root /usr/share/nginx/html;
  index index.html;

  location /classic {
    try_files $uri $uri/ /classic/index.html;
  }

  location / {
    try_files $uri $uri/ /index.html;
  }
}
```

---

## Phase 4.0 Build Checklist

- [ ] `cd observer && npm install`
- [ ] Verify `npm run dev` starts and proxy to `localhost:8888` works
- [ ] WorldMap renders agents as spheres at hex positions
- [ ] AgentAvatar shows archetype color + name label
- [ ] Sleeping agents pulse at 0.6Hz and show 💤
- [ ] Clicking an agent opens AgentInspector with status + last dream
- [ ] DramaFeed polls `/events` and renders narrative text
- [ ] MilestoneBar shows all `first.*` events achieved
- [ ] StatsPanel updates every 10 seconds with living count, events total
- [ ] `npm run build` produces `dist/` with no errors
- [ ] Docker build succeeds and Phase 1 accessible at `/classic`

---

## Phase 4.1+ Roadmap (Implementation Order)

| Phase | What to Build | Key Dependency |
|-------|--------------|----------------|
| 4.1 | Terrain elevation (Perlin noise on hex tiles) | `simplex-noise` package |
| 4.1 | Coalition color regions on terrain | `/coalitions` endpoint |
| 4.1 | Agent mood → avatar animation | emotional_state in agents query |
| 4.2 | x402 tipping button in AgentInspector | `/services/{soul_id}/tip` endpoint |
| 4.2 | Subscription modal | Creator backend + Stripe |
| 4.3 | Timeline scrubber | Full event log replay query |
| 4.3 | Milestone marker icons on timeline | `/timeline/firsts` |
| 4.4 | NFT avatar minting | Token Factory + wallet connect |

---

## See Also

- [doc 43 — Observer Phase 4 Upgrade Plan](./43-observer-phase4-upgrade.md) — design rationale, all components, human participation spec
- [doc 53 — Narrative Engine](./53-narrative-engine.md) — server-side event narration
- [doc 38 — Event Schema](./38-event-schema.md) — events the observer consumes
- [doc 67 — Dream Implementation](./67-dream-sleep-implementation.md) — dream data shown in inspector
