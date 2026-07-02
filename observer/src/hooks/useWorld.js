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
let _pendingLiveVideoUtteranceId = '';
let _pendingUrl = null;
let _pendingPlayback = null;
let _activeAudio = null;
let _activeAudioSource = null;
let _activeAudioEnded = null;
let _activeAudioTimer = null;
let _alphabetPassed = false;
let _alphabetSpeaking = false;
let _alphabetNextAt = 0;

const ONE_ALPHABET_NORMALIZED = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
const ONE_WAITING_VIDEO_STATUSES = new Set(['waiting-for-video', 'waiting-for-live-video']);
const ONE_RETRY_STATUSES = new Set(['blocked', 'timeout', 'error', 'video-timeout']);

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

function resolveAbsoluteUrl(rawUrl) {
  if (!rawUrl) return '';
  try {
    return new URL(rawUrl, API_BASE).toString();
  } catch {
    return String(rawUrl);
  }
}

function firstMediaUrl(value) {
  if (!value) return '';
  if (typeof value === 'string') return value.trim();
  if (Array.isArray(value)) {
    for (const entry of value) {
      const url = firstMediaUrl(entry);
      if (url) return url;
    }
    return '';
  }
  if (typeof value === 'object') {
    for (const field of ['url', 'src', 'href', 'uri', 'path']) {
      if (typeof value[field] === 'string' && value[field].trim()) return value[field].trim();
    }
    return firstMediaUrl(value.sources);
  }
  return '';
}

function liveVideoUrlFromSnapshot(snap) {
  const avatar = snap?.avatar || {};
  const candidates = [
    avatar?.video_manifest?.live_video,
    avatar?.video_manifest?.live,
    avatar?.plan?.video_manifest?.live_video,
    avatar?.plan?.video_manifest?.live,
  ];
  for (const candidate of candidates) {
    const url = firstMediaUrl(candidate);
    if (url) return resolveAbsoluteUrl(url);
  }
  return '';
}

async function waitForLiveVideo(url, timeoutMs = Number(import.meta.env.VITE_ONE_LIVE_VIDEO_WAIT_TIMEOUT_MS || 120000)) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), Math.max(1000, timeoutMs));
  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: { Range: 'bytes=0-0' },
      cache: 'no-store',
      signal: controller.signal,
    });
    return response.ok || response.status === 206;
  } finally {
    clearTimeout(timer);
  }
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
        ONE_WAITING_VIDEO_STATUSES.has(status)
          ? 'waiting-for-live-video'
          : status === 'ended'
          ? 'passed'
          : ONE_RETRY_STATUSES.has(status)
          ? 'retry'
          : 'reciting';
      useObserverStore.getState().setOneAlphabetStatus(nextStatus);
      if (status === 'ended') _alphabetPassed = true;
      if (status === 'ended' || ONE_WAITING_VIDEO_STATUSES.has(status) || ONE_RETRY_STATUSES.has(status)) {
        _alphabetSpeaking = false;
      } else {
        _alphabetSpeaking = true;
      }
    }
  }
  useObserverStore.getState().setVoicePlayback({
    ...(playback || {}),
    status,
    updatedAtMs: nowMs(),
    ...extra,
  });
}

function clearActiveAudioTimer() {
  if (_activeAudioTimer) {
    clearTimeout(_activeAudioTimer);
    _activeAudioTimer = null;
  }
}

function armPlaybackEndedWatchdog(playback, extra = {}) {
  clearActiveAudioTimer();
  const durationMs = Number(playback?.durationSeconds || 0) * 1000;
  if (!Number.isFinite(durationMs) || durationMs <= 0) return;
  _activeAudioTimer = setTimeout(() => {
    if (_activeAudioEnded) _activeAudioEnded();
  }, Math.max(1500, durationMs + 1500));
}

function startVoicePlayback(playback, audioUrl, extra = {}) {
  const nextPlayback = { ...(playback || {}), ...extra };
  markVoicePlayback('starting', nextPlayback, {
    audioUrl,
    transport: extra.transport || 'fish-audio',
    ...extra,
  });
  _playAudioUrl(audioUrl, nextPlayback);
}

function startOneAlphabetPlaybackWhenVideoReady({
  uid,
  playback,
  audioUrl,
  liveVideoUrl,
  isAlive,
}) {
  if (_pendingLiveVideoUtteranceId === uid || _lastPlayedUtteranceId === uid) return;
  _pendingLiveVideoUtteranceId = uid;
  const livePlayback = { ...playback, liveVideoUrl };
  markVoicePlayback('waiting-for-video', livePlayback, {
    audioUrl,
    liveVideoUrl,
    transport: 'fish-audio+live-video',
  });
  waitForLiveVideo(liveVideoUrl)
    .then((ready) => {
      if (!isAlive() || _lastPlayedUtteranceId === uid) return;
      _pendingLiveVideoUtteranceId = '';
      if (!ready) {
        _alphabetNextAt = Date.now() + 1200;
        markVoicePlayback('video-timeout', livePlayback, {
          audioUrl,
          liveVideoUrl,
          transport: 'fish-audio+live-video',
        });
        return;
      }
      _lastPlayedUtteranceId = uid;
      startVoicePlayback(livePlayback, audioUrl, {
        liveVideoUrl,
        transport: 'fish-audio+live-video',
      });
    })
    .catch(() => {
      if (!isAlive()) return;
      _pendingLiveVideoUtteranceId = '';
      _alphabetNextAt = Date.now() + 1200;
      markVoicePlayback('video-timeout', livePlayback, {
        audioUrl,
        liveVideoUrl,
        transport: 'fish-audio+live-video',
      });
    });
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
  let markedDone = false;
  _activeAudio = audio;
  _activeAudioSource = null;
  clearActiveAudioTimer();
  const markDone = (status, extra = {}) => {
    if (markedDone) return;
    markedDone = true;
    clearActiveAudioTimer();
    if (_activeAudio === audio) _activeAudio = null;
    if (_activeAudioEnded === markDone) _activeAudioEnded = null;
    markVoicePlayback(status, playback, { audioUrl: url, transport: 'html-audio', ...extra });
  };
  _activeAudioEnded = () => markDone('ended');
  audio.volume = 1.0;
  audio.addEventListener('playing', () => {
    markedPlaying = true;
    useObserverStore.getState().setAudioBlocked(false);
    markVoicePlayback('playing', playback, {
      audioUrl: url,
      transport: 'html-audio',
      startedAtMs: nowMs(),
    });
    armPlaybackEndedWatchdog(playback);
  }, { once: true });
  audio.addEventListener('ended', () => {
    markDone('ended');
  }, { once: true });
  audio.addEventListener('error', () => {
    if (!markedPlaying) {
      markDone('blocked');
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
              _activeAudio = null;
              _activeAudioSource = src;
              let sourceDone = false;
              const markSourceDone = () => {
                if (sourceDone) return;
                sourceDone = true;
                clearActiveAudioTimer();
                if (_activeAudioSource === src) _activeAudioSource = null;
                if (_activeAudioEnded === markSourceDone) _activeAudioEnded = null;
                markVoicePlayback('ended', playback, { audioUrl: url, transport: 'audio-context' });
              };
              _activeAudioEnded = markSourceDone;
              src.onended = () => {
                markSourceDone();
              };
              src.start(0);
              useObserverStore.getState().setAudioBlocked(false);
              const playbackWithDuration = {
                ...playback,
                durationSeconds: decoded.duration || playback.durationSeconds || 0,
              };
              markVoicePlayback('playing', playback, {
                audioUrl: url,
                durationSeconds: playbackWithDuration.durationSeconds,
                transport: 'audio-context',
                startedAtMs: nowMs(),
              });
              armPlaybackEndedWatchdog(playbackWithDuration);
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
          if (!_alphabetSpeaking && !_alphabetPassed) {
            useObserverStore.getState().setOneAlphabetStatus('line-ready');
          }
          if (uid && synthOk && uid !== _lastPlayedUtteranceId) {
            const playback = playbackContextFromSnapshot(snap);
            const audioUrl = resolveVoiceAudioUrl(snap?.voice?.synthesis?.audio_url, uid);
            const liveVideoUrl = liveVideoUrlFromSnapshot(snap);
            if (liveVideoUrl) {
              startOneAlphabetPlaybackWhenVideoReady({
                uid,
                playback,
                audioUrl,
                liveVideoUrl,
                isAlive: () => alive,
              });
            } else {
              _alphabetSpeaking = false;
              _alphabetNextAt = Date.now() + 1200;
              markVoicePlayback('waiting-for-live-video', playback, {
                audioUrl,
                transport: 'fish-audio+live-video',
              });
            }
          } else if (!uid || !synthOk) {
            _alphabetSpeaking = false;
            _alphabetNextAt = Date.now() + 1200;
            useObserverStore.getState().setOneAlphabetStatus('waiting-for-fish-audio');
          }
        } else {
          _alphabetSpeaking = false;
          if (Date.now() >= _alphabetNextAt) {
            useObserverStore.getState().setOneAlphabetStatus('waiting-for-alphabet-line');
            _alphabetNextAt = Date.now() + 1200;
          }
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
