import { useEffect } from 'react';
import { useObserverStore } from '../store';

function defaultRuntimeUrl() {
  const { hostname, origin } = window.location;
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return 'http://localhost:8888';
  }
  return origin;
}

export const API_BASE =
  new URLSearchParams(window.location.search).get('runtime') ||
  window.RUNTIME_URL ||
  import.meta.env.VITE_RUNTIME_URL ||
  defaultRuntimeUrl();

let _lastPlayedUtteranceId = '';
let _pendingUrl = null;
let _pendingPlayback = null;
let _alphabetAttempt = 0;
let _alphabetPassed = false;
let _alphabetSpeaking = false;
let _alphabetNextAt = 0;
let _alphabetVisualTimer = null;

const ONE_ALPHABET_LINE = 'A B C D E F G H I J K L M N O P Q R S T U V W X Y Z.';
const ONE_ALPHABET_NORMALIZED = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
const ONE_ALPHABET_VISUAL_MS = 8200;
const ONE_ALPHABET_LOOP_GAP_MS = 2000;

function streamUrl() {
  return API_BASE.replace(/^http/i, 'ws') + '/world/stream';
}

function nowMs() {
  return typeof performance !== 'undefined' ? performance.now() : Date.now();
}

function currentMode() {
  const pathname = window.location.pathname.replace(/\/+$/, '');
  const params = new URLSearchParams(window.location.search);
  if (pathname === '/one' || params.get('solo') === '1') return 'one';
  return 'stage';
}

function oneAlphabetEnabled() {
  const params = new URLSearchParams(window.location.search);
  return currentMode() === 'one' && params.get('alphabet') !== '0';
}

function normalizeAlphabet(raw) {
  return String(raw || '').toUpperCase().replace(/[^A-Z]/g, '');
}

function isCorrectAlphabet(raw) {
  return normalizeAlphabet(raw) === ONE_ALPHABET_NORMALIZED;
}

function cleanLine(raw) {
  return String(raw || '').replace(/\s+/g, ' ').trim();
}

function resolveVoiceAudioUrl(audioUrl, utteranceId) {
  if (audioUrl) {
    try {
      return new URL(audioUrl, API_BASE).toString();
    } catch {
      return String(audioUrl);
    }
  }
  return `${API_BASE}/voice/audio/${utteranceId}`;
}

function speakerSoulIdFromSnapshot(snap) {
  const direct = snap?.last_dialogue_turn?.sender_soul_id || snap?.last_dialogue_turn?.sender_id || snap?.avatar?.speaker_soul_id;
  if (direct) return String(direct);
  const speaker = String(snap?.voice?.plan?.speaker || '').toLowerCase();
  const agent = (snap?.agents || []).find((item) => {
    const name = String(item?.current_name || '').toLowerCase();
    const soulId = String(item?.soul_id || '').toLowerCase();
    return speaker && (name === speaker || soulId === speaker);
  });
  return agent?.soul_id || '';
}

function playbackContextFromSnapshot(snap) {
  const voice = snap?.voice || {};
  const plan = voice.plan || {};
  const synthesis = voice.synthesis || {};
  return {
    utteranceId: plan.utterance_id || '',
    speakerSoulId: speakerSoulIdFromSnapshot(snap),
    speakerName: plan.speaker || '',
    line: cleanLine(plan.line || snap?.last_dialogue_turn?.content || ''),
    audioRms: Number(synthesis.audio_rms || plan.audio_rms || 0),
    mouthAmplitude: Number(synthesis.mouth_amplitude || plan.mouth_amplitude || 0),
    durationSeconds: Number(synthesis.duration_seconds || 0),
    latencyTargetMs: Number(synthesis.latency_target_ms || synthesis.lip_sync?.latency_target_ms || 300),
    lipSyncSource: synthesis.lip_sync?.source || plan.lip_sync_source || 'audio_rms',
    synthesisOk: Boolean(synthesis.ok),
  };
}

function markVoicePlayback(status, playback, extra = {}) {
  if (playback?.line) {
    useObserverStore.getState().setCurrentSpokenLine(playback.line);
    if (oneAlphabetEnabled() && isCorrectAlphabet(playback.line)) {
      const nextStatus =
        status === 'ended'
          ? 'passed'
          : (status === 'blocked' || status === 'timeout' || status === 'error')
          ? 'retry'
          : 'reciting';
      useObserverStore.getState().setOneAlphabetStatus(nextStatus);
      if (status === 'ended') _alphabetPassed = true;
    }
  }
  useObserverStore.getState().setVoicePlayback({
    ...(playback || {}),
    status,
    updatedAtMs: nowMs(),
    ...extra,
  });
}

function alphabetSpeakerFromSnapshot(snap) {
  const speakerSoulId = speakerSoulIdFromSnapshot(snap);
  const agents = (snap?.agents || []).filter((agent) => agent && agent.is_alive !== false);
  return agents.find((agent) => agent.soul_id === speakerSoulId) || agents[0] || null;
}

function oneAlphabetPlayback(snap, speaker, transport) {
  const plan = snap?.voice?.plan || {};
  _alphabetAttempt += 1;
  return {
    utteranceId: `${plan.utterance_id || 'one-alphabet'}:${transport}:${_alphabetAttempt}`,
    speakerSoulId: speaker.soul_id,
    speakerName: speaker.current_name || speaker.soul_id,
    line: ONE_ALPHABET_LINE,
    mouthAmplitude: 0.68,
    durationSeconds: 8.08,
    latencyTargetMs: 300,
    lipSyncSource: transport,
    synthesisOk: true,
  };
}

function ensureOneAlphabetVisualLoop(snap) {
  if (!oneAlphabetEnabled()) return;
  const now = Date.now();
  if (_alphabetSpeaking || now < _alphabetNextAt) return;
  const speaker = alphabetSpeakerFromSnapshot(snap);
  if (!speaker) {
    useObserverStore.getState().setOneAlphabetStatus('waiting-for-agent');
    return;
  }
  const playback = oneAlphabetPlayback(snap, speaker, 'fish-audio-loop');
  _alphabetSpeaking = true;
  _alphabetPassed = true;
  _alphabetNextAt = now + ONE_ALPHABET_VISUAL_MS + ONE_ALPHABET_LOOP_GAP_MS;
  useObserverStore.getState().setCurrentSpokenLine(ONE_ALPHABET_LINE);
  useObserverStore.getState().setOneAlphabetStatus('reciting');
  markVoicePlayback('playing', playback, {
    startedAtMs: nowMs(),
    transport: 'fish-audio-loop',
  });

  if (_alphabetVisualTimer) window.clearTimeout(_alphabetVisualTimer);
  _alphabetVisualTimer = window.setTimeout(() => {
    _alphabetSpeaking = false;
    useObserverStore.getState().setOneAlphabetStatus('passed');
    markVoicePlayback('ended', playback, {
      transport: 'fish-audio-loop',
    });
    _alphabetVisualTimer = null;
  }, ONE_ALPHABET_VISUAL_MS);
}

function ensureOneAlphabetDrill(snap) {
  if (!oneAlphabetEnabled() || _alphabetPassed || _alphabetSpeaking) return;
  if (Date.now() < _alphabetNextAt) return;
  const speaker = alphabetSpeakerFromSnapshot(snap);
  if (!speaker) {
    useObserverStore.getState().setOneAlphabetStatus('waiting-for-agent');
    return;
  }
  _alphabetSpeaking = true;
  const playback = oneAlphabetPlayback(snap, speaker, 'alphabet_drill');
  useObserverStore.getState().setCurrentSpokenLine(ONE_ALPHABET_LINE);
  useObserverStore.getState().setOneAlphabetStatus('queued');
  markVoicePlayback('starting', playback);

  const finish = (ok) => {
    _alphabetSpeaking = false;
    const passed = ok && isCorrectAlphabet(ONE_ALPHABET_LINE);
    _alphabetPassed = passed;
    _alphabetNextAt = Date.now() + (passed ? 60000 : 1200);
    useObserverStore.getState().setOneAlphabetStatus(passed ? 'passed' : 'retry');
    markVoicePlayback(passed ? 'ended' : 'blocked', playback, {
      transport: 'speech-synthesis',
    });
  };

  if (!('speechSynthesis' in window) || !('SpeechSynthesisUtterance' in window)) {
    markVoicePlayback('playing', playback, {
      startedAtMs: nowMs(),
      transport: 'visual-drill',
    });
    window.setTimeout(() => finish(true), 5200);
    return;
  }

  try {
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(ONE_ALPHABET_LINE);
    utterance.lang = 'en-US';
    utterance.rate = 0.82;
    utterance.pitch = 0.92;
    utterance.volume = 1;
    utterance.onstart = () => {
      markVoicePlayback('playing', playback, {
        startedAtMs: nowMs(),
        transport: 'speech-synthesis',
      });
      useObserverStore.getState().setOneAlphabetStatus('reciting');
    };
    utterance.onend = () => finish(true);
    utterance.onerror = () => finish(false);
    window.speechSynthesis.speak(utterance);
  } catch {
    finish(false);
  }
}

// Singleton AudioContext — pre-unlocked in OBS CEF, unlockable in Firefox
let _audioCtx = null;
function _getCtx() {
  if (!_audioCtx || _audioCtx.state === 'closed') {
    _audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 48000 });
  }
  return _audioCtx;
}

function _playAudioUrl(url, playback = {}) {
  // Strategy 1: HTMLAudioElement (works when user has interacted or in OBS CEF)
  const audio = new Audio(url);
  let markedPlaying = false;
  audio.volume = 1.0;
  audio.addEventListener('playing', () => {
    markedPlaying = true;
    useObserverStore.getState().setAudioBlocked(false);
    markVoicePlayback('playing', playback, {
      audioUrl: url,
      transport: 'html-audio',
      startedAtMs: nowMs(),
    });
  }, { once: true });
  audio.addEventListener('ended', () => {
    markVoicePlayback('ended', playback, { audioUrl: url, transport: 'html-audio' });
  }, { once: true });
  audio.addEventListener('error', () => {
    if (!markedPlaying) {
      markVoicePlayback('blocked', playback, { audioUrl: url, transport: 'html-audio' });
    }
  }, { once: true });
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
            if (!buf) {
              _pendingUrl = url;
              _pendingPlayback = playback;
              useObserverStore.getState().setAudioBlocked(true);
              markVoicePlayback('blocked', playback, { audioUrl: url, transport: 'audio-context' });
              return;
            }
            ctx.decodeAudioData(buf, (decoded) => {
              const src = ctx.createBufferSource();
              src.buffer = decoded;
              src.connect(ctx.destination);
              src.onended = () => {
                markVoicePlayback('ended', playback, { audioUrl: url, transport: 'audio-context' });
              };
              src.start(0);
              useObserverStore.getState().setAudioBlocked(false);
              markVoicePlayback('playing', playback, {
                audioUrl: url,
                durationSeconds: decoded.duration || playback.durationSeconds || 0,
                transport: 'audio-context',
                startedAtMs: nowMs(),
              });
            }, () => {
              _pendingUrl = url;
              _pendingPlayback = playback;
              useObserverStore.getState().setAudioBlocked(true);
              markVoicePlayback('blocked', playback, { audioUrl: url, transport: 'audio-context' });
            });
          })
          .catch(() => {
            _pendingUrl = url;
            _pendingPlayback = playback;
            useObserverStore.getState().setAudioBlocked(true);
            markVoicePlayback('blocked', playback, { audioUrl: url, transport: 'audio-context' });
          });
      }).catch(() => {
        _pendingUrl = url;
        _pendingPlayback = playback;
        useObserverStore.getState().setAudioBlocked(true);
        markVoicePlayback('blocked', playback, { audioUrl: url, transport: 'audio-context' });
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
    const playback = _pendingPlayback;
    _pendingUrl = null;
    _pendingPlayback = null;
    _playAudioUrl(url, playback);
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
      if (oneAlphabetEnabled()) {
        const line = cleanLine(snap?.voice?.plan?.line || snap?.last_dialogue_turn?.content || '');
        if (isCorrectAlphabet(line)) {
          useObserverStore.getState().setCurrentSpokenLine(line);
          if (!_alphabetSpeaking) {
            useObserverStore.getState().setOneAlphabetStatus('line-ready');
          }
          if (uid && synthOk && uid !== _lastPlayedUtteranceId) {
            _lastPlayedUtteranceId = uid;
            const playback = playbackContextFromSnapshot(snap);
            const audioUrl = resolveVoiceAudioUrl(snap?.voice?.synthesis?.audio_url, uid);
            _playAudioUrl(audioUrl, playback);
          } else if (!uid || !synthOk) {
            ensureOneAlphabetDrill(snap);
          }
          ensureOneAlphabetVisualLoop(snap);
        } else {
          ensureOneAlphabetDrill(snap);
        }
      } else if (uid && synthOk && uid !== _lastPlayedUtteranceId) {
        _lastPlayedUtteranceId = uid;
        const playback = playbackContextFromSnapshot(snap);
        const audioUrl = resolveVoiceAudioUrl(snap?.voice?.synthesis?.audio_url, uid);
        _playAudioUrl(audioUrl, playback);
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
