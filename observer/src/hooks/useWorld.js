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
// Singleton AudioContext that stays unlocked after first user gesture
let _audioCtx = null;

function _getAudioCtx() {
  if (!_audioCtx || _audioCtx.state === 'closed') {
    _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  }
  return _audioCtx;
}

// Unlock AudioContext on first user interaction (required by Firefox autoplay policy)
function _unlockAudio() {
  const ctx = _getAudioCtx();
  if (ctx.state === 'suspended') {
    ctx.resume().catch(() => {});
  }
  document.removeEventListener('click', _unlockAudio);
  document.removeEventListener('keydown', _unlockAudio);
  document.removeEventListener('touchstart', _unlockAudio);
}
document.addEventListener('click', _unlockAudio, { once: true });
document.addEventListener('keydown', _unlockAudio, { once: true });
document.addEventListener('touchstart', _unlockAudio, { once: true });

function _playAudioBuffer(buf) {
  if (!buf) return;
  const ctx = _getAudioCtx();
  const resume = ctx.state === 'suspended' ? ctx.resume() : Promise.resolve();
  resume.then(() => {
    ctx.decodeAudioData(buf.slice(0), (decoded) => {
      const src = ctx.createBufferSource();
      src.buffer = decoded;
      src.connect(ctx.destination);
      src.start(0);
    }, (err) => {
      // WAV decode failed — ignore silently
    });
  }).catch(() => {});
}

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
          setSnapshot(snap);
          // Play synthesized voice audio when a new utterance arrives
          const uid = snap?.voice?.plan?.utterance_id;
          const synthOk = snap?.voice?.synthesis?.ok;
          if (uid && synthOk && uid !== _lastPlayedUtteranceId) {
            _lastPlayedUtteranceId = uid;
            fetch(`${API_BASE}/voice/audio/${uid}`)
              .then((r) => r.ok ? r.arrayBuffer() : null)
              .then((buf) => _playAudioBuffer(buf))
              .catch(() => {});
          }
        } else {
          ok = false;
          lastError = lastError || `snapshot:${snapshotRes.status === 'fulfilled' ? snapshotRes.value.status : 'fetch'}`;
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
