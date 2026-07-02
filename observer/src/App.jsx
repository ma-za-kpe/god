import React, { Suspense, useMemo } from 'react';
import { useWorld } from './hooks/useWorld';
import { Header } from './components/Header';
import { WorldMap } from './components/WorldMap';
import { DramaFeed } from './components/DramaFeed';
import { AgentInspector } from './components/AgentInspector';
import { MilestoneBar } from './components/MilestoneBar';
import { useObserverStore } from './store';

class ObserverErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error('observer render error', error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="debug-red-screen">
          <div className="debug-red-card">
            <div className="debug-red-title">observer render error</div>
            <div className="debug-red-copy">{String(this.state.error?.message || this.state.error)}</div>
            <div className="debug-red-copy muted">Check the browser console and Vite log for the stack trace.</div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

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
  const audioBlocked = useObserverStore((s) => s.audioBlocked);
  const currentSpokenLine = useObserverStore((s) => s.currentSpokenLine);
  const oneAlphabetStatus = useObserverStore((s) => s.oneAlphabetStatus);
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
          <ObserverErrorBoundary>
            <Suspense
              fallback={
                <div className="debug-red-screen">
                  <div className="debug-red-card">
                    <div className="debug-red-title">loading observer</div>
                    <div className="debug-red-copy">Waiting for the scene graph and avatar assets to resolve.</div>
                  </div>
                </div>
              }
            >
              <WorldMap mode={mode} minimal />
            </Suspense>
          </ObserverErrorBoundary>
          <div
            className="one-caption"
            data-one-alphabet-status={oneAlphabetStatus || 'waiting'}
          >
            <span>{oneAlphabetStatus || 'waiting'}</span>
            <strong>{currentSpokenLine || 'A B C D E F G H I J K L M N O P Q R S T U V W X Y Z.'}</strong>
          </div>
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
      {audioBlocked && (
        <div className="audio-unlock-badge" onClick={() => useObserverStore.getState().setAudioBlocked(false)}>
          <span>AUDIO MUTED</span>
          <span>Click anywhere to enable voice</span>
        </div>
      )}
      <main className="observer-main">
        <ObserverErrorBoundary>
          <Suspense
            fallback={
              <div className="debug-red-screen">
                <div className="debug-red-card">
                  <div className="debug-red-title">loading observer</div>
                  <div className="debug-red-copy">Waiting for the scene graph and avatar assets to resolve.</div>
                </div>
              </div>
            }
          >
            <WorldMap mode={mode} />
          </Suspense>
        </ObserverErrorBoundary>
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
