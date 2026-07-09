import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import { ControlledAvatar } from './ControlledAvatar';
import { TalkingHeadAvatar } from './TalkingHeadAvatar';
import {
  avatarIntentToJson,
  intentFromText,
  normalizeAvatarIntent,
  TEST_AVATAR_LINE,
} from '../avatarIntent';
import {
  buildAvatarIntentMessages,
  buildOllamaAvatarRequest,
  parseAvatarIntentResponse,
} from '../avatarPrompt';
import { compileAvatarIntentNodes } from '../avatarNodeCompiler';

const LOCAL_AGENT = {
  soul_id: 'local-avatar-lab',
  current_name: 'Local Avatar',
  is_alive: true,
};

function nowMs() {
  return typeof performance !== 'undefined' ? performance.now() : Date.now();
}

function estimateDurationSeconds(line, tempo = 1) {
  const words = String(line || '').trim().split(/\s+/).filter(Boolean).length;
  return Math.max(2.4, Math.min(10, (words / 2.8 + 1.2) / Math.max(0.5, tempo)));
}

function queryParam(name, fallback) {
  try {
    return new URLSearchParams(window.location.search).get(name) || fallback;
  } catch {
    return fallback;
  }
}

function summarizeNodeTargets(nodes = []) {
  return nodes.reduce((summary, node) => {
    const target = node?.target || 'unknown';
    summary[target] = (summary[target] || 0) + 1;
    return summary;
  }, {});
}

function summarizeIntentForLog(intent) {
  const normalized = normalizeAvatarIntent(intent);
  const nodes = normalized.nodes || [];
  return {
    line: normalized.voice.line,
    mood: normalized.mood,
    gesture: normalized.gesture,
    gaze: normalized.gaze,
    camera: normalized.camera,
    pose: normalized.motion.pose,
    tempo: normalized.tempo,
    voiceEnergy: normalized.voice.energy,
    hands: normalized.hands,
    hair: normalized.hair,
    face: normalized.face,
    appearance: normalized.appearance,
    nodeCount: nodes.length,
    targetCounts: summarizeNodeTargets(nodes),
    boneSample: nodes.filter((node) => node.target === 'bone').slice(0, 10).map((node) => node.id),
    morphSample: nodes.filter((node) => node.target === 'morph').slice(0, 10).map((node) => node.id),
  };
}

function currentLipTag(rendererStatus) {
  const applied = rendererStatus?.diagnostics?.applied || [];
  return applied.find((item) => String(item).startsWith('lips:')) || '';
}

function avatarDiscrepancies({ auto, audioStatus, intent, nodeRegistry, rendererStatus, voicePlayback }) {
  const normalized = normalizeAvatarIntent(intent);
  const nodes = normalized.nodes || [];
  const rendererDiagnostics = rendererStatus?.diagnostics || {};
  const unsupported = rendererDiagnostics.unsupported || [];
  const boneRegistryCount = nodeRegistry.filter((node) => node.target === 'bone').length;
  const boneCount = nodes.filter((node) => node.target === 'bone').length;
  const bodyMotionControls = nodes.filter((node) => (
    node.target === 'morph'
    && ['bodyRotateX', 'bodyRotateY', 'bodyRotateZ', 'headRotateX', 'headRotateY', 'headRotateZ', 'chestInhale'].includes(node.id)
  )).length;
  const lipTag = currentLipTag(rendererStatus);
  const fullBodyIntent = boneCount >= 20 || normalized.motion.bodyMovement > 0.65 || normalized.gesture !== 'idle';
  const handIntent = normalized.hands.leftFingerCurl > 0.55
    || normalized.hands.rightFingerCurl > 0.55
    || normalized.hands.openPalm > 0.55;
  const discrepancies = [];

  if (!auto) discrepancies.push('auto_loop_disabled');
  if (unsupported.length) discrepancies.push(`unsupported_renderer_controls:${unsupported.slice(0, 6).join(',')}`);
  if (boneRegistryCount >= 30 && fullBodyIntent && bodyMotionControls < 4) discrepancies.push('full_body_intent_without_bounded_body_motion_nodes');
  if ((fullBodyIntent || handIntent) && ['upper', 'head'].includes(normalized.camera.view)) {
    discrepancies.push(`camera_${normalized.camera.view}_may_hide_body_or_hand_controls`);
  }
  if (voicePlayback?.status === 'playing' && !lipTag) discrepancies.push('audio_playing_without_lip_viseme_diagnostics');
  if (voicePlayback?.status === 'playing' && audioStatus.status !== 'speaking') {
    discrepancies.push(`voice_playback_audio_status_mismatch:${audioStatus.status}`);
  }
  if (audioStatus.lastError) discrepancies.push(`audio_error:${audioStatus.lastError}`);
  if (rendererStatus?.status && rendererStatus.status !== 'ready') discrepancies.push(`renderer_not_ready:${rendererStatus.status}`);

  return discrepancies;
}

function ProceduralAvatarScene({ intent, voicePlayback, vrmUrl }) {
  const avatarState = useMemo(() => ({
    speaking: voicePlayback?.status === 'playing',
    speaker_soul_id: LOCAL_AGENT.soul_id,
    avatar_intent: intent,
    life: {
      breathing_phase: 0.5,
      mouth_amplitude: intent.voice.energy,
    },
  }), [intent, voicePlayback?.status]);

  return (
    <Canvas
      camera={{ position: [0, 3.0, 12], fov: 36 }}
      gl={{ preserveDrawingBuffer: true }}
      shadows
      legacy
    >
      <color attach="background" args={['#071014']} />
      <ambientLight intensity={0.86} />
      <directionalLight position={[7, 10, 8]} intensity={2.2} castShadow />
      <directionalLight position={[-7, 4, -6]} intensity={0.72} color="#b7ef7b" />
      <group position={[0, -0.05, 0]}>
        <Suspense fallback={null}>
          <ControlledAvatar
            agent={LOCAL_AGENT}
            avatarState={avatarState}
            selected
            speaking={voicePlayback?.status === 'playing'}
            vrmUrl={vrmUrl}
            position={[0, 0, 0]}
            color="#57d89b"
            voicePlayback={voicePlayback}
            avatarIntent={intent}
          />
        </Suspense>
      </group>
      <OrbitControls enablePan={false} enableZoom={false} minPolarAngle={Math.PI / 2.8} maxPolarAngle={Math.PI / 2.05} />
    </Canvas>
  );
}

export function LocalAvatarLab() {
  const [line, setLine] = useState(() => queryParam('line', ''));
  const [intent, setIntent] = useState(() => normalizeAvatarIntent({ voice: { line: queryParam('line', '') } }));
  const [voicePlayback, setVoicePlayback] = useState(null);
  const [auto, setAuto] = useState(() => queryParam('auto', '1') !== '0');
  const [status, setStatus] = useState('local-ready');
  const [ollamaModel, setOllamaModel] = useState(() => queryParam('model', import.meta.env.VITE_OLLAMA_MODEL || 'llama3.1:8b'));
  const [ollamaUrl, setOllamaUrl] = useState(() => queryParam('ollama', import.meta.env.VITE_OLLAMA_URL || '/ollama'));
  const [renderer, setRenderer] = useState(() => queryParam('renderer', import.meta.env.VITE_AVATAR_LAB_RENDERER || 'talkinghead'));
  const [avatarUrl, setAvatarUrl] = useState(() => queryParam('avatar', import.meta.env.VITE_TALKINGHEAD_AVATAR_URL || ''));
  const [nodeRegistry, setNodeRegistry] = useState([]);
  const [intentSource, setIntentSource] = useState('initial');
  const [lastIntentError, setLastIntentError] = useState('');
  const [rendererStatus, setRendererStatus] = useState({});
  const [clientLogs, setClientLogs] = useState([]);
  const [actionLogs, setActionLogs] = useState([]);
  const [audioStatus, setAudioStatus] = useState({
    provider: 'browser-speech',
    status: 'idle',
    supported: typeof window !== 'undefined' && Boolean(window.speechSynthesis && window.SpeechSynthesisUtterance),
    voices: 0,
    selectedVoice: '',
    lastError: '',
    unlocked: false,
  });
  const speechRef = useRef(null);
  const audioContextRef = useRef(null);
  const voicesRef = useRef([]);
  const fallbackTimerRef = useRef(null);
  const rendererLogSignatureRef = useRef('');
  const audioLogSignatureRef = useRef('');
  const discrepancyLogSignatureRef = useRef('');

  const vrmUrl = queryParam('vrm', import.meta.env.VITE_DEFAULT_VRM_URL || '');
  const intentJson = useMemo(() => avatarIntentToJson(intent), [intent]);
  const currentDiscrepancies = useMemo(() => avatarDiscrepancies({
    auto,
    audioStatus,
    intent,
    nodeRegistry,
    rendererStatus,
    voicePlayback,
  }), [audioStatus, auto, intent, nodeRegistry, rendererStatus, voicePlayback]);
  const recordAction = useCallback((type, detail = {}) => {
    setActionLogs((current) => [
      ...current.slice(-119),
      {
        at: new Date().toISOString(),
        type,
        ...detail,
      },
    ]);
  }, []);
  const pushClientLog = useCallback((entry) => {
    setClientLogs((current) => [
      ...current.slice(-11),
      {
        at: new Date().toISOString(),
        ...entry,
      },
    ]);
  }, []);

  const refreshVoices = useCallback(() => {
    if (typeof window === 'undefined' || !window.speechSynthesis) return [];
    const voices = window.speechSynthesis.getVoices?.() || [];
    voicesRef.current = voices;
    const selected = voices.find((voice) => /^en[-_]/i.test(voice.lang)) || voices[0] || null;
    setAudioStatus((current) => ({
      ...current,
      supported: Boolean(window.speechSynthesis && window.SpeechSynthesisUtterance),
      voices: voices.length,
      selectedVoice: selected ? `${selected.name} (${selected.lang})` : '',
    }));
    return voices;
  }, []);

  const primeAudio = useCallback(() => {
    if (typeof window === 'undefined') return;
    refreshVoices();
    try {
      const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
      if (AudioContextCtor) {
        const ctx = audioContextRef.current || new AudioContextCtor();
        audioContextRef.current = ctx;
        ctx.resume?.();
        const oscillator = ctx.createOscillator();
        const gain = ctx.createGain();
        gain.gain.value = 0.0001;
        oscillator.connect(gain);
        gain.connect(ctx.destination);
        oscillator.start();
        oscillator.stop(ctx.currentTime + 0.035);
      }
      window.speechSynthesis?.resume?.();
      setAudioStatus((current) => ({
        ...current,
        status: 'primed',
        unlocked: true,
        lastError: '',
      }));
      recordAction('audio:prime', {
        supported: true,
        voices: voicesRef.current.length,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setAudioStatus((current) => ({
        ...current,
        status: 'prime-error',
        lastError: message,
      }));
      pushClientLog({ level: 'error', message: `audio-prime:${message}` });
      recordAction('audio:prime-error', { message });
    }
  }, [pushClientLog, recordAction, refreshVoices]);

  const runWithAudio = useCallback((action) => {
    primeAudio();
    return action();
  }, [primeAudio]);

  const stopSpeech = useCallback(() => {
    if (fallbackTimerRef.current) {
      clearTimeout(fallbackTimerRef.current);
      fallbackTimerRef.current = null;
    }
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
      window.speechSynthesis.resume?.();
    }
    speechRef.current = null;
    setVoicePlayback((current) => current ? { ...current, status: 'ended', updatedAtMs: nowMs() } : current);
    setAudioStatus((current) => ({
      ...current,
      status: current.status === 'speaking' ? 'stopped' : current.status,
    }));
    recordAction('audio:stop', {});
  }, [recordAction]);

  const speakIntent = useCallback((nextIntent, { source = 'unknown' } = {}) => {
    const normalized = normalizeAvatarIntent(nextIntent);
    const durationSeconds = estimateDurationSeconds(normalized.voice.line, normalized.tempo);
    const startedAtMs = nowMs();
    const nextPlayback = {
      utteranceId: `local-${Date.now()}`,
      speakerSoulId: LOCAL_AGENT.soul_id,
      speakerName: LOCAL_AGENT.current_name,
      line: normalized.voice.line,
      status: 'playing',
      mouthAmplitude: normalized.voice.energy,
      durationSeconds,
      startedAtMs,
      updatedAtMs: startedAtMs,
      lipSyncSource: 'browser_speech+intent_viseme_track',
      transport: 'browser-speech',
      intentSource: source,
    };

    stopSpeech();
    setIntent(normalized);
    setIntentSource(source);
    setLine(normalized.voice.line);
    setVoicePlayback(nextPlayback);
    setStatus('speaking');
    recordAction('intent:speak', {
      source,
      durationSeconds,
      lipSyncSource: nextPlayback.lipSyncSource,
      intent: summarizeIntentForLog(normalized),
    });

    if (typeof window !== 'undefined' && window.speechSynthesis && window.SpeechSynthesisUtterance) {
      refreshVoices();
      const utterance = new SpeechSynthesisUtterance(normalized.voice.line);
      const selectedVoice = voicesRef.current.find((voice) => /^en[-_]/i.test(voice.lang)) || voicesRef.current[0] || null;
      if (selectedVoice) utterance.voice = selectedVoice;
      utterance.rate = Math.max(0.65, Math.min(1.35, normalized.tempo));
      utterance.pitch = normalized.mood === 'happy' ? 1.08 : normalized.mood === 'concerned' ? 0.92 : 1;
      utterance.volume = 1;
      utterance.onstart = () => {
        setAudioStatus((current) => ({
          ...current,
          status: 'speaking',
          lastError: '',
          selectedVoice: selectedVoice ? `${selectedVoice.name} (${selectedVoice.lang})` : current.selectedVoice,
        }));
        recordAction('audio:speech-start', {
          utteranceId: nextPlayback.utteranceId,
          durationSeconds,
          selectedVoice: selectedVoice ? `${selectedVoice.name} (${selectedVoice.lang})` : '',
          line: normalized.voice.line,
        });
      };
      utterance.onend = () => {
        setStatus('ended');
        setAudioStatus((current) => ({ ...current, status: 'ended', lastError: '' }));
        setVoicePlayback((current) => current?.utteranceId === nextPlayback.utteranceId
          ? { ...current, status: 'ended', updatedAtMs: nowMs() }
          : current);
        recordAction('audio:speech-end', {
          utteranceId: nextPlayback.utteranceId,
          line: normalized.voice.line,
        });
      };
      utterance.onerror = (event) => {
        const error = event?.error || 'speech-error';
        setStatus('speech-fallback');
        setAudioStatus((current) => ({ ...current, status: 'speech-error', lastError: error }));
        pushClientLog({ level: 'error', message: `speech:${error}` });
        recordAction('audio:speech-error', {
          utteranceId: nextPlayback.utteranceId,
          error,
          line: normalized.voice.line,
        });
        fallbackTimerRef.current = setTimeout(() => {
          setVoicePlayback((current) => current?.utteranceId === nextPlayback.utteranceId
            ? { ...current, status: 'ended', updatedAtMs: nowMs() }
            : current);
        }, durationSeconds * 1000);
      };
      speechRef.current = utterance;
      setAudioStatus((current) => ({
        ...current,
        status: 'speech-queued',
        lastError: '',
        selectedVoice: selectedVoice ? `${selectedVoice.name} (${selectedVoice.lang})` : current.selectedVoice,
      }));
      recordAction('audio:speech-queued', {
        utteranceId: nextPlayback.utteranceId,
        selectedVoice: selectedVoice ? `${selectedVoice.name} (${selectedVoice.lang})` : '',
        line: normalized.voice.line,
      });
      window.speechSynthesis.speak(utterance);
      window.speechSynthesis.resume?.();
      window.setTimeout(() => {
        if (speechRef.current === utterance && window.speechSynthesis?.pending) {
          window.speechSynthesis.resume?.();
          setAudioStatus((current) => current.status === 'speech-queued'
            ? { ...current, status: 'speech-pending' }
            : current);
        }
      }, 900);
    } else {
      setAudioStatus((current) => ({
        ...current,
        status: 'unsupported',
        supported: false,
        lastError: 'SpeechSynthesis unavailable in this browser',
      }));
      recordAction('audio:unsupported', {
        provider: 'browser-speech',
        line: normalized.voice.line,
      });
      fallbackTimerRef.current = setTimeout(() => {
        setStatus('ended');
        setVoicePlayback((current) => current?.utteranceId === nextPlayback.utteranceId
          ? { ...current, status: 'ended', updatedAtMs: nowMs() }
          : current);
      }, durationSeconds * 1000);
    }
  }, [pushClientLog, recordAction, refreshVoices, stopSpeech]);

  const runTestFallback = useCallback(() => {
    setStatus('test-fallback');
    recordAction('fallback:test-intent', {
      line: line || TEST_AVATAR_LINE,
      registryCount: nodeRegistry.length,
    });
    speakIntent(
      compileAvatarIntentNodes(intentFromText(line || TEST_AVATAR_LINE), nodeRegistry),
      { source: 'explicit-test-fallback' },
    );
  }, [line, nodeRegistry, recordAction, speakIntent]);

  const askOllama = useCallback(async ({ autonomous = false } = {}) => {
    setStatus('ollama');
    setLastIntentError('');
    try {
      let repairError = '';
      for (let attempt = 0; attempt < 3; attempt += 1) {
        recordAction('llm:request', {
          attempt: attempt + 1,
          autonomous,
          model: ollamaModel,
          line,
          registryCount: nodeRegistry.length,
          registryTargets: summarizeNodeTargets(nodeRegistry),
          repairError,
        });
        const messages = buildAvatarIntentMessages({
          line,
          previousIntent: intent,
          nodeRegistry,
          autonomous,
          repairError,
        });
        const response = await fetch(`${ollamaUrl.replace(/\/+$/, '')}/api/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(buildOllamaAvatarRequest({ model: ollamaModel, messages })),
        });
        if (!response.ok) throw new Error(`ollama:${response.status}`);
        const payload = await response.json();
        const responseText = payload?.message?.content || payload?.response || '';
        recordAction('llm:response', {
          attempt: attempt + 1,
          status: response.status,
          responseLength: String(responseText).length,
        });
        try {
          const parsedIntent = parseAvatarIntentResponse(payload, { requestedLine: line, nodeRegistry });
          const nextIntent = compileAvatarIntentNodes(parsedIntent, nodeRegistry);
          recordAction('llm:intent-accepted', {
            attempt: attempt + 1,
            source: `ollama:${ollamaModel}`,
            intent: summarizeIntentForLog(nextIntent),
          });
          speakIntent(nextIntent, { source: `ollama:${ollamaModel}` });
          setStatus('ollama-intent');
          setLastIntentError('');
          return;
        } catch (parseError) {
          repairError = parseError instanceof Error ? parseError.message : String(parseError);
          setLastIntentError(repairError);
          recordAction('llm:intent-repair', {
            attempt: attempt + 1,
            error: repairError,
          });
        }
      }
      throw new Error(`ollama:intent-repair-failed:${repairError || 'unknown'}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      console.error('Avatar intent request failed', message);
      setLastIntentError(message);
      setStatus('ollama-error');
      setAuto(false);
      recordAction('llm:error', { message });
    }
  }, [intent, line, nodeRegistry, ollamaModel, ollamaUrl, recordAction, speakIntent]);

  const updateIntentField = useCallback((path, value) => {
    recordAction('manual:intent-field', {
      path,
      value: Number(value),
    });
    setIntent((current) => {
      const next = normalizeAvatarIntent(current);
      if (path === 'hair.bend') next.hair.bend = Number(value);
      if (path === 'hair.sway') next.hair.sway = Number(value);
      if (path === 'hands.leftFingerCurl') next.hands.leftFingerCurl = Number(value);
      if (path === 'hands.rightFingerCurl') next.hands.rightFingerCurl = Number(value);
      if (path === 'face.smile') next.face.smile = Number(value);
      if (path === 'voice.energy') next.voice.energy = Number(value);
      return normalizeAvatarIntent(next);
    });
  }, [recordAction]);

  useEffect(() => () => stopSpeech(), [stopSpeech]);

  useEffect(() => {
    if (typeof window === 'undefined' || !window.speechSynthesis) return undefined;
    refreshVoices();
    window.speechSynthesis.onvoiceschanged = refreshVoices;
    return () => {
      if (window.speechSynthesis.onvoiceschanged === refreshVoices) {
        window.speechSynthesis.onvoiceschanged = null;
      }
    };
  }, [refreshVoices]);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const originalError = console.error;
    const originalWarn = console.warn;
    const stringify = (value) => {
      if (value instanceof Error) return value.message;
      if (typeof value === 'string') return value;
      try {
        return JSON.stringify(value);
      } catch {
        return String(value);
      }
    };
    const onError = (event) => {
      pushClientLog({ level: 'error', message: event.message || 'window.error' });
    };
    const onUnhandled = (event) => {
      pushClientLog({ level: 'error', message: stringify(event.reason || 'unhandledrejection') });
    };
    console.error = (...args) => {
      pushClientLog({ level: 'error', message: args.map(stringify).join(' ') });
      originalError(...args);
    };
    console.warn = (...args) => {
      pushClientLog({ level: 'warn', message: args.map(stringify).join(' ') });
      originalWarn(...args);
    };
    window.addEventListener('error', onError);
    window.addEventListener('unhandledrejection', onUnhandled);
    return () => {
      console.error = originalError;
      console.warn = originalWarn;
      window.removeEventListener('error', onError);
      window.removeEventListener('unhandledrejection', onUnhandled);
    };
  }, [pushClientLog]);

  useEffect(() => {
    const signature = JSON.stringify({
      status: audioStatus.status,
      selectedVoice: audioStatus.selectedVoice,
      lastError: audioStatus.lastError,
      playback: voicePlayback?.status || '',
      line: voicePlayback?.line || '',
    });
    if (audioLogSignatureRef.current === signature) return;
    audioLogSignatureRef.current = signature;
    recordAction('audio:status', {
      status: audioStatus.status,
      selectedVoice: audioStatus.selectedVoice,
      lastError: audioStatus.lastError,
      voicePlaybackStatus: voicePlayback?.status || '',
      line: voicePlayback?.line || '',
    });
  }, [audioStatus, recordAction, voicePlayback]);

  useEffect(() => {
    const diagnostics = rendererStatus?.diagnostics || {};
    const signature = JSON.stringify({
      renderer: rendererStatus.renderer,
      status: rendererStatus.status,
      nodeCount: rendererStatus.nodeCount,
      cameraView: rendererStatus.cameraView,
      applied: diagnostics.applied || [],
      degraded: diagnostics.degraded || [],
      unsupported: diagnostics.unsupported || [],
    });
    if (rendererLogSignatureRef.current === signature) return;
    rendererLogSignatureRef.current = signature;
    recordAction('renderer:diagnostics', {
      renderer: rendererStatus.renderer,
      status: rendererStatus.status,
      nodeCount: rendererStatus.nodeCount,
      cameraView: rendererStatus.cameraView,
      applied: diagnostics.applied || [],
      degraded: diagnostics.degraded || [],
      unsupported: diagnostics.unsupported || [],
      lipTag: currentLipTag(rendererStatus),
    });
  }, [recordAction, rendererStatus]);

  useEffect(() => {
    const signature = JSON.stringify(currentDiscrepancies);
    if (discrepancyLogSignatureRef.current === signature) return;
    discrepancyLogSignatureRef.current = signature;
    recordAction(currentDiscrepancies.length ? 'quality:discrepancy' : 'quality:clear', {
      discrepancies: currentDiscrepancies,
    });
  }, [currentDiscrepancies, recordAction]);

  const handleRendererEvent = useCallback((event) => {
    const { type = 'renderer:event', ...detail } = event || {};
    recordAction(type, detail);
  }, [recordAction]);

  useEffect(() => {
    if (!auto) return undefined;
    if (!voicePlayback || voicePlayback.status === 'ended') {
      const timer = setTimeout(() => askOllama({ autonomous: true }), voicePlayback ? 900 : 300);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [askOllama, auto, voicePlayback]);

  return (
    <div className="avatar-lab-shell">
      <main className="avatar-lab-stage" data-avatar-lab-status={status}>
        {renderer === 'procedural' ? (
          <ProceduralAvatarScene intent={intent} voicePlayback={voicePlayback} vrmUrl={vrmUrl} />
        ) : (
          <TalkingHeadAvatar
            avatarIntent={intent}
            voicePlayback={voicePlayback}
            avatarUrl={avatarUrl}
            onNodeRegistry={setNodeRegistry}
            onRendererEvent={handleRendererEvent}
            onRendererStatus={setRendererStatus}
          />
        )}
      </main>
      <aside className="avatar-lab-controls">
        <div className="avatar-lab-head">
          <div>
            <div className="avatar-lab-title">Avatar Lab</div>
            <div className="avatar-lab-status">{status}</div>
            <div className="avatar-lab-status secondary">intent {intentSource}</div>
            <div className="avatar-lab-status secondary">audio {audioStatus.status}</div>
          </div>
          <div className="avatar-lab-actions">
            <button type="button" onClick={() => runWithAudio(() => askOllama())}>Run</button>
            <button type="button" className={auto ? 'active' : ''} onClick={() => runWithAudio(() => setAuto((value) => !value))}>Auto</button>
            <button type="button" onClick={() => runWithAudio(() => askOllama({ autonomous: true }))}>Next</button>
          </div>
        </div>

        <label className="avatar-lab-field">
          <span>Line</span>
          <textarea value={line} onChange={(event) => setLine(event.target.value)} rows={4} />
        </label>

        <div className="avatar-lab-actions wide">
          <button type="button" onClick={() => runWithAudio(() => askOllama())}>Ollama</button>
          <button type="button" onClick={() => runWithAudio(runTestFallback)}>Test</button>
          <button type="button" onClick={primeAudio}>Audio</button>
          <button type="button" onClick={stopSpeech}>Stop</button>
        </div>

        <div className="avatar-lab-grid">
          <label>
            <span>Ollama Endpoint</span>
            <input value={ollamaUrl} onChange={(event) => setOllamaUrl(event.target.value)} />
          </label>
          <label>
            <span>Model</span>
            <input value={ollamaModel} onChange={(event) => setOllamaModel(event.target.value)} />
          </label>
          <label>
            <span>Renderer</span>
            <input value={renderer} onChange={(event) => setRenderer(event.target.value)} />
          </label>
          <label>
            <span>Avatar GLB URL</span>
            <input value={avatarUrl} placeholder="Default local MPFB avatar" onChange={(event) => setAvatarUrl(event.target.value)} />
          </label>
        </div>

        <div className="avatar-lab-sliders">
          <label><span>Hair Bend</span><input type="range" min="-1" max="1" step="0.01" value={intent.hair.bend} onChange={(event) => updateIntentField('hair.bend', event.target.value)} /></label>
          <label><span>Hair Sway</span><input type="range" min="0" max="1" step="0.01" value={intent.hair.sway} onChange={(event) => updateIntentField('hair.sway', event.target.value)} /></label>
          <label><span>Left Curl</span><input type="range" min="0" max="1" step="0.01" value={intent.hands.leftFingerCurl} onChange={(event) => updateIntentField('hands.leftFingerCurl', event.target.value)} /></label>
          <label><span>Right Curl</span><input type="range" min="0" max="1" step="0.01" value={intent.hands.rightFingerCurl} onChange={(event) => updateIntentField('hands.rightFingerCurl', event.target.value)} /></label>
          <label><span>Smile</span><input type="range" min="0" max="1" step="0.01" value={intent.face.smile} onChange={(event) => updateIntentField('face.smile', event.target.value)} /></label>
          <label><span>Energy</span><input type="range" min="0" max="1" step="0.01" value={intent.voice.energy} onChange={(event) => updateIntentField('voice.energy', event.target.value)} /></label>
        </div>

        <pre className="avatar-lab-json">{intentJson}</pre>
        <pre className="avatar-lab-json">{JSON.stringify({ rendererNodes: nodeRegistry.slice(0, 256) }, null, 2)}</pre>
        <pre className="avatar-lab-json">{JSON.stringify({ intentSource, lastIntentError, rendererStatus, audioStatus, currentDiscrepancies, clientLogs }, null, 2)}</pre>
        <pre className="avatar-lab-json">{JSON.stringify({ actionLogs: actionLogs.slice(-48) }, null, 2)}</pre>
      </aside>
    </div>
  );
}
