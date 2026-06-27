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

let _lastPlayedUtteranceId = '';
let _pendingUrl = null;

function streamUrl() {
  return API_BASE.replace(/^http/i, 'ws') + '/world/stream';
}

// Singleton AudioContext — pre-unlocked in OBS CEF, unlockable in Firefox
let _audioCtx = null;
function _getCtx() {
  if (!_audioCtx || _audioCtx.state === 'closed') {
    _audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 48000 });
  }
  return _audioCtx;
}

function _playAudioUrl(url) {
  // Strategy 1: HTMLAudioElement (works when user has interacted or in OBS CEF)
  const audio = new Audio(url);
  audio.volume = 1.0;
  const p = audio.play();
  if (p && p.catch) {
    p.catch(() => {
      // Strategy 2: AudioContext fetch+decode (OBS CEF has pre-unlocked AudioContext)
      const ctx = _getCtx();
      const resume = ctx.state === 'suspended' ? ctx.resume() : Promise.resolve();
      resume.then(() => {
        fetch(url)
          .then((r) => r.ok ? r.arrayBuffer() : null)
          .then((buf) => {
            if (!buf) return;
            ctx.decodeAudioData(buf, (decoded) => {
              const src = ctx.createBufferSource();
              src.buffer = decoded;
              src.connect(ctx.destination);
              src.start(0);
              useObserverStore.getState().setAudioBlocked(false);
            }, () => {});
          })
          .catch(() => {
            _pendingUrl = url;
            useObserverStore.getState().setAudioBlocked(true);
          });
      }).catch(() => {
        _pendingUrl = url;
        useObserverStore.getState().setAudioBlocked(true);
      });
    });
  }
}

function _unlockAndPlay() {
  useObserverStore.getState().setAudioBlocked(false);
  const ctx = _getCtx();
  if (ctx.state === 'suspended') ctx.resume().catch(() => {});
  if (_pendingUrl) {
    const url = _pendingUrl;
    _pendingUrl = null;
    _playAudioUrl(url);
  }
}

document.addEventListener('click', _unlockAndPlay, { once: true });
document.addEventListener('keydown', _unlockAndPlay, { once: true });

export function useWorld() {
  const setAgents = useObserverStore((s) => s.setAgents);
  const setEvents = useObserverStore((s) => s.setEvents);
  const setStats = useObserverStore((s) => s.setStats);
  const setSnapshot = useObserverStore((s) => s.setSnapshot);
  const setObserverHealth = useObserverStore((s) => s.setObserverHealth);

  useEffect(() => {
    let alive = true;
    let pollTimer = null;
    let reconnectTimer = null;
    let pingTimer = null;
    let deltaRefreshTimer = null;
    let ws = null;
    let wsLive = false;
    let pollInFlight = false;

    const markHealth = (ok, lastError = '', transport = 'poll') => {
      setObserverHealth({
        ok,
        lastPollAt: Date.now(),
        lastError,
        transport,
      });
    };

    const applySnapshot = (snap, transport = 'poll') => {
      if (!alive || !snap || snap.error) return;
      setSnapshot(snap);
      if (Array.isArray(snap.agents)) setAgents(snap.agents);
      if (Array.isArray(snap.events)) setEvents(snap.events);
      // Play synthesized voice audio when a new utterance arrives
      const uid = snap?.voice?.plan?.utterance_id;
      const synthOk = snap?.voice?.synthesis?.ok;
      if (uid && synthOk && uid !== _lastPlayedUtteranceId) {
        _lastPlayedUtteranceId = uid;
        _playAudioUrl(`${API_BASE}/voice/audio/${uid}`);
      }
      markHealth(true, '', transport);
    };

    const mergeAgentPatches = (patches) => {
      if (!Array.isArray(patches) || !patches.length) return;
      const current = useObserverStore.getState().agents || [];
      const byId = new Map(current.filter(Boolean).map((agent) => [agent.soul_id, agent]));
      for (const patch of patches) {
        const soulId = patch?.soul_id;
        if (!soulId) continue;
        byId.set(soulId, { ...(byId.get(soulId) || {}), ...patch });
      }
      setAgents(Array.from(byId.values()));
    };

    const mergeEvents = (events) => {
      if (!Array.isArray(events) || !events.length) return;
      const current = useObserverStore.getState().events || [];
      const byId = new Map();
      for (const event of [...events, ...current]) {
        const id = event?.event_id || `${event?.event_type || 'event'}:${event?.timestamp || ''}:${byId.size}`;
        if (!byId.has(id)) byId.set(id, event);
      }
      setEvents(Array.from(byId.values()).slice(0, 120));
    };

    const schedulePoll = (delayMs) => {
      if (pollTimer) clearTimeout(pollTimer);
      if (alive) pollTimer = setTimeout(() => poll(), delayMs);
    };

    const scheduleDeltaRefresh = () => {
      if (deltaRefreshTimer) return;
      deltaRefreshTimer = setTimeout(() => {
        deltaRefreshTimer = null;
        poll('ws-delta');
      }, 150);
    };

    const poll = async (transport = 'poll') => {
      if (pollInFlight) return;
      pollInFlight = true;
      const startedAt = Date.now();
      let ok = true;
      let lastError = '';
      try {
        const agentsRes = await fetch(`${API_BASE}/agents?limit=10000`);
        if (agentsRes.ok) {
          const json = await agentsRes.json();
          setAgents(json.agents || []);
        } else {
          ok = false;
          lastError = `agents:${agentsRes.status}`;
        }

        const [eventsRes, statsRes, snapshotRes] = await Promise.allSettled([
          fetch(`${API_BASE}/events?limit=80`),
          fetch(`${API_BASE}/stats`),
          fetch(`${API_BASE}/world/snapshot?events_limit=60&messages_limit=40`),
        ]);

        if (eventsRes.status === 'fulfilled' && eventsRes.value.ok) {
          const json = await eventsRes.value.json();
          setEvents(json.events || []);
        } else {
          ok = false;
          lastError = lastError || `events:${eventsRes.status === 'fulfilled' ? eventsRes.value.status : 'fetch'}`;
        }

        if (statsRes.status === 'fulfilled' && statsRes.value.ok) {
          setStats(await statsRes.value.json());
        } else {
          ok = false;
          lastError = lastError || `stats:${statsRes.status === 'fulfilled' ? statsRes.value.status : 'fetch'}`;
        }

        if (snapshotRes.status === 'fulfilled' && snapshotRes.value.ok) {
          const snap = await snapshotRes.value.json();
          applySnapshot(snap, transport);
        } else {
          ok = false;
          lastError = lastError || `snapshot:${snapshotRes.status === 'fulfilled' ? snapshotRes.value.status : 'fetch'}`;
        }
      } catch (err) {
        ok = false;
        lastError = err instanceof Error ? err.message : String(err);
      }
      pollInFlight = false;
      if (!ok) {
        setObserverHealth({
          ok,
          lastPollAt: startedAt,
          lastError,
          transport,
        });
      }
      schedulePoll(wsLive ? 8000 : 3000);
    };

    const connectStream = () => {
      if (!alive || typeof WebSocket === 'undefined') return;
      try {
        ws = new WebSocket(streamUrl());
        ws.onopen = () => {
          wsLive = true;
          markHealth(true, '', 'ws');
          pingTimer = setInterval(() => {
            if (ws?.readyState === WebSocket.OPEN) ws.send('ping');
          }, 20000);
        };
        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'snapshot') {
              applySnapshot(msg, 'ws');
              return;
            }
            if (msg.type === 'delta') {
              mergeEvents(msg.events);
              mergeAgentPatches(msg.agents);
              markHealth(true, '', 'ws-delta');
              scheduleDeltaRefresh();
            }
          } catch (err) {
            markHealth(false, err instanceof Error ? err.message : String(err), 'ws');
          }
        };
        ws.onclose = () => {
          wsLive = false;
          if (pingTimer) clearInterval(pingTimer);
          pingTimer = null;
          if (alive) reconnectTimer = setTimeout(connectStream, 4000);
        };
        ws.onerror = () => {
          wsLive = false;
          markHealth(false, 'world-stream:error', 'ws');
        };
      } catch (err) {
        wsLive = false;
        markHealth(false, err instanceof Error ? err.message : String(err), 'ws');
        if (alive) reconnectTimer = setTimeout(connectStream, 4000);
      }
    };

    poll();
    connectStream();
    return () => {
      alive = false;
      if (pollTimer) clearTimeout(pollTimer);
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (pingTimer) clearInterval(pingTimer);
      if (deltaRefreshTimer) clearTimeout(deltaRefreshTimer);
      if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
        ws.close();
      }
    };
  }, [setAgents, setEvents, setObserverHealth, setSnapshot, setStats]);
}
