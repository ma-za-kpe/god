import { useEffect } from 'react';
import { useObserverStore } from '../store';

function defaultRuntimeUrl() {
  const { hostname, origin } = window.location;
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return 'http://localhost:8888';
  }
  return origin;
}

export const API_BASE = window.RUNTIME_URL || import.meta.env.VITE_RUNTIME_URL || defaultRuntimeUrl();

export function useWorld() {
  const setAgents = useObserverStore((s) => s.setAgents);
  const setEvents = useObserverStore((s) => s.setEvents);
  const setStats = useObserverStore((s) => s.setStats);
  const setSnapshot = useObserverStore((s) => s.setSnapshot);
  const setObserverHealth = useObserverStore((s) => s.setObserverHealth);

  useEffect(() => {
    let alive = true;

    const poll = async () => {
      const startedAt = Date.now();
      let ok = true;
      let lastError = '';
      try {
        const [agentsRes, eventsRes, statsRes, snapshotRes] = await Promise.all([
          fetch(`${API_BASE}/agents?limit=10000`),
          fetch(`${API_BASE}/events?limit=80`),
          fetch(`${API_BASE}/stats`),
          fetch(`${API_BASE}/world/snapshot?events_limit=60&messages_limit=40`),
        ]);
        if (agentsRes.ok) {
          const json = await agentsRes.json();
          setAgents(json.agents || []);
        } else {
          ok = false;
          lastError = `agents:${agentsRes.status}`;
        }
        if (eventsRes.ok) {
          const json = await eventsRes.json();
          setEvents(json.events || []);
        } else {
          ok = false;
          lastError = lastError || `events:${eventsRes.status}`;
        }
        if (statsRes.ok) {
          setStats(await statsRes.json());
        } else {
          ok = false;
          lastError = lastError || `stats:${statsRes.status}`;
        }
        if (snapshotRes.ok) {
          setSnapshot(await snapshotRes.json());
        } else {
          ok = false;
          lastError = lastError || `snapshot:${snapshotRes.status}`;
        }
      } catch (err) {
        ok = false;
        lastError = err instanceof Error ? err.message : String(err);
      }
      setObserverHealth({
        ok,
        lastPollAt: startedAt,
        lastError,
      });
      if (alive) setTimeout(poll, 3000);
    };

    poll();
    return () => {
      alive = false;
    };
  }, [setAgents, setEvents, setSnapshot, setStats]);
}
