import { useMemo } from 'react';
import { useWorld } from './hooks/useWorld';
import { Header } from './components/Header';
import { WorldMap } from './components/WorldMap';
import { DramaFeed } from './components/DramaFeed';
import { AgentInspector } from './components/AgentInspector';
import { MilestoneBar } from './components/MilestoneBar';
import { useObserverStore } from './store';

function currentMode() {
  const pathname = window.location.pathname.replace(/\/+$/, '');
  const params = new URLSearchParams(window.location.search);
  if (pathname === '/one-red' || params.get('debug') === 'red') return 'red';
  if (pathname === '/one' || params.get('solo') === '1') return 'one';
  return 'stage';
}

export default function App() {
  useWorld();
  const mode = useMemo(() => currentMode(), []);
  const agents = useObserverStore((s) => s.agents);
  const selectedSoulId = useObserverStore((s) => s.selectedSoulId);
  const observerHealth = useObserverStore((s) => s.observerHealth);
  const ageMs = observerHealth.lastPollAt ? Date.now() - observerHealth.lastPollAt : Infinity;
  const live = observerHealth.ok && ageMs < 7000;
  const label = live ? 'observer live' : 'observer stale';

  if (mode === 'red') {
    return (
      <div className="debug-red-screen">
        <div className="debug-red-card">
          <div className="debug-red-title">observer debug</div>
          <div className="debug-red-copy">If you can see this, the browser source is rendering correctly.</div>
          <div className="debug-red-copy muted">Use /one to return to the live world.</div>
        </div>
      </div>
    );
  }

  if (mode === 'one') {
    return (
      <div className="observer-app one minimal">
        <div className={`stream-badge ${live ? 'live' : 'stale'}`}>
          <span>{label}</span>
          <span>{observerHealth.lastError || (live ? 'runtime healthy' : 'waiting for runtime')}</span>
        </div>
        <main className="observer-main minimal">
          <WorldMap mode={mode} minimal />
        </main>
      </div>
    );
  }

  return (
    <div className={`observer-app ${mode}`}>
      <Header mode={mode} />
      <div className={`stream-badge ${live ? 'live' : 'stale'}`}>
        <span>{label}</span>
        <span>{observerHealth.lastError || (live ? 'runtime healthy' : 'waiting for runtime')}</span>
      </div>
      <main className="observer-main">
        <WorldMap mode={mode} />
        {mode === 'one' ? null : <DramaFeed />}
        <AgentInspector />
      </main>
      <MilestoneBar />
      <div className="status-strip">
        <span>{agents.length ? `${agents.length} agents` : 'loading agents'}</span>
        <span>{selectedSoulId ? selectedSoulId.slice(0, 8) : 'no agent selected'}</span>
      </div>
    </div>
  );
}
