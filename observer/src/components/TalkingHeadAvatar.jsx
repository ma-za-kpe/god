import { useEffect, useMemo, useRef, useState } from 'react';
import { TalkingHead } from '@met4citizen/talkinghead/modules/talkinghead.mjs';
import { normalizeAvatarIntent } from '../avatarIntent';
import {
  applyTalkingHeadBeat,
  applyTalkingHeadFrame,
  buildTalkingHeadNodeRegistry,
  stageStyleForIntent,
} from '../talkingHeadAdapter';
import { sampleTextViseme } from '../avatarVisemes';

const TALKING_HEAD_DEFAULT_AVATAR =
  '/assets/avatars/brunette.glb';

export function TalkingHeadAvatar({
  avatarIntent,
  voicePlayback,
  avatarUrl,
  onNodeRegistry,
  onRendererEvent,
  onRendererStatus,
}) {
  const containerRef = useRef(null);
  const headRef = useRef(null);
  const loadedRef = useRef(false);
  const adapterStateRef = useRef({});
  const initialCameraViewRef = useRef(null);
  const lastFrameDiagnosticsAtRef = useRef(0);
  const lastRendererEventAtRef = useRef(0);
  const lastVisemeKeyRef = useRef('');
  const frameRef = useRef(0);
  const [status, setStatus] = useState('loading');
  const [errorDetail, setErrorDetail] = useState('');
  const [nodeCount, setNodeCount] = useState(0);
  const [adapterDiagnostics, setAdapterDiagnostics] = useState({ applied: [], degraded: [], unsupported: [] });
  const intent = useMemo(() => normalizeAvatarIntent(avatarIntent), [avatarIntent]);
  if (!initialCameraViewRef.current) initialCameraViewRef.current = intent.camera.view;
  const stageStyle = useMemo(() => stageStyleForIntent(intent), [intent]);
  const sourceUrl = avatarUrl || import.meta.env.VITE_TALKINGHEAD_AVATAR_URL || TALKING_HEAD_DEFAULT_AVATAR;

  useEffect(() => {
    onRendererStatus?.({
      renderer: 'talkinghead',
      status,
      sourceUrl,
      errorDetail,
      nodeCount,
      cameraView: intent.camera.view,
      stage: intent.stage,
      diagnostics: adapterDiagnostics,
    });
  }, [adapterDiagnostics, errorDetail, intent.camera.view, intent.stage, nodeCount, onRendererStatus, sourceUrl, status]);

  useEffect(() => {
    let cancelled = false;
    let head = null;

    async function start() {
      if (!containerRef.current) return;
      setStatus('loading');
      loadedRef.current = false;
      adapterStateRef.current = {};
      containerRef.current.replaceChildren();
      head = new TalkingHead(containerRef.current, {
        lipsyncModules: ['en'],
        cameraView: initialCameraViewRef.current,
        avatarMood: 'neutral',
      });
      headRef.current = head;

      try {
        setErrorDetail('');
        await head.showAvatar(
          {
            url: sourceUrl,
            body: 'F',
            avatarMood: 'neutral',
            lipsyncLang: 'en',
          },
          (event) => {
            if (cancelled) return;
            if (event?.lengthComputable && event.total > 0) {
              const percent = Math.min(100, Math.round((event.loaded / event.total) * 100));
              setStatus(`loading ${percent}%`);
            } else if (event?.loaded) {
              setStatus(`loading ${Math.round(event.loaded / 1024)}kb`);
            }
          },
        );
        if (cancelled) return;
        loadedRef.current = true;
        setStatus('ready');
        try {
          const registry = buildTalkingHeadNodeRegistry(head);
          setNodeCount(registry.length);
          onNodeRegistry?.(registry);
          onRendererEvent?.({
            type: 'renderer:registry',
            nodeCount: registry.length,
            targetCounts: registry.reduce((summary, node) => {
              const target = node.target || 'unknown';
              summary[target] = (summary[target] || 0) + 1;
              return summary;
            }, {}),
          });
        } catch {
          setNodeCount(0);
          onNodeRegistry?.([]);
          onRendererEvent?.({
            type: 'renderer:registry-error',
          });
        }
        try {
          const diagnostics = applyTalkingHeadBeat({
            head,
            intent,
            container: containerRef.current,
            state: adapterStateRef.current,
          });
          setAdapterDiagnostics(diagnostics);
          onRendererEvent?.({
            type: 'renderer:beat',
            cameraView: intent.camera.view,
            applied: diagnostics.applied,
            degraded: diagnostics.degraded,
            unsupported: diagnostics.unsupported,
          });
        } catch {}
        head.start?.();
      } catch (error) {
        if (!cancelled) {
          console.error('TalkingHead avatar load failed', { sourceUrl, error });
          setStatus('load-error');
          setErrorDetail(error instanceof Error ? error.message : String(error));
          onRendererEvent?.({
            type: 'renderer:load-error',
            sourceUrl,
            message: error instanceof Error ? error.message : String(error),
          });
        }
      }
    }

    start();

    return () => {
      cancelled = true;
      loadedRef.current = false;
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
      frameRef.current = 0;
      try {
        head?.stop?.();
      } catch {}
      containerRef.current?.replaceChildren();
      headRef.current = null;
    };
  }, [onNodeRegistry, onRendererEvent, sourceUrl]);

  useEffect(() => {
    const head = headRef.current;
    if (!head || !loadedRef.current) return;

    try {
      const diagnostics = applyTalkingHeadBeat({
        head,
        intent,
        container: containerRef.current,
        state: adapterStateRef.current,
      });
      setAdapterDiagnostics(diagnostics);
    } catch (error) {
      setAdapterDiagnostics((current) => ({
        ...current,
        unsupported: [...(current.unsupported || []), error instanceof Error ? error.message : String(error)],
      }));
      onRendererEvent?.({
        type: 'renderer:beat-error',
        message: error instanceof Error ? error.message : String(error),
      });
    }
  }, [intent, onRendererEvent]);

  useEffect(() => {
    const tick = () => {
      const head = headRef.current;
      if (head && loadedRef.current) {
        const speaking = voicePlayback?.status === 'playing';
        const elapsed = voicePlayback?.startedAtMs
          ? Math.max(0, (performance.now() - voicePlayback.startedAtMs) / 1000)
          : performance.now() / 1000;
        const mouthPulse = speaking ? Math.abs(Math.sin(elapsed * 12 * intent.tempo)) * 0.32 : 0;
        const visemeFrame = speaking
          ? sampleTextViseme({
            text: voicePlayback?.line || intent.voice.line,
            elapsedSeconds: elapsed,
            durationSeconds: voicePlayback?.durationSeconds || 1,
            tempo: intent.tempo,
          })
          : { current: 'sil', next: 'sil', intensity: 0 };
        try {
          const diagnostics = applyTalkingHeadFrame({
            head,
            intent,
            mouthPulse,
            speaking,
            visemeFrame,
            elapsedSeconds: elapsed,
          });
          const visemeKey = `${speaking}:${visemeFrame.current}:${visemeFrame.next}:${visemeFrame.index}`;
          if (speaking && visemeKey !== lastVisemeKeyRef.current) {
            lastVisemeKeyRef.current = visemeKey;
            onRendererEvent?.({
              type: 'viseme:sample',
              current: visemeFrame.current,
              next: visemeFrame.next,
              index: visemeFrame.index,
              count: visemeFrame.count,
              intensity: visemeFrame.intensity,
              line: voicePlayback?.line || intent.voice.line,
            });
          }
          if (performance.now() - lastFrameDiagnosticsAtRef.current > 650) {
            lastFrameDiagnosticsAtRef.current = performance.now();
            if (performance.now() - lastRendererEventAtRef.current > 1100) {
              lastRendererEventAtRef.current = performance.now();
              onRendererEvent?.({
                type: 'renderer:frame',
                speaking,
                lipTag: diagnostics.applied.find((item) => String(item).startsWith('lips:')) || '',
                appliedSummary: diagnostics.applied.filter((item) => (
                  String(item).startsWith('lips:')
                  || String(item).startsWith('body_motion:')
                  || String(item).startsWith('semantic:')
                  || String(item).startsWith('morph:handFist')
                  || String(item).startsWith('morph:bodyRotate')
                  || String(item).startsWith('morph:headRotate')
                )).slice(0, 18),
                degraded: diagnostics.degraded,
                unsupported: diagnostics.unsupported,
              });
            }
            setAdapterDiagnostics((current) => ({
              applied: [
                ...(current.applied || []).filter((item) => !String(item).startsWith('morph:') && !String(item).startsWith('lips:')),
                ...diagnostics.applied.slice(0, 18),
              ].slice(-36),
              degraded: [...new Set([...(current.degraded || []), ...diagnostics.degraded])].slice(-18),
              unsupported: [...new Set([...(current.unsupported || []), ...diagnostics.unsupported])].slice(-30),
            }));
          }
        } catch {}
      }
      frameRef.current = requestAnimationFrame(tick);
    };
    frameRef.current = requestAnimationFrame(tick);
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
      frameRef.current = 0;
    };
  }, [intent, onRendererEvent, voicePlayback?.line, voicePlayback?.startedAtMs, voicePlayback?.status]);

  return (
    <div
      className="talkinghead-stage"
      data-avatar-renderer="talkinghead"
      data-avatar-source-status={status}
      data-avatar-source-url={sourceUrl}
      data-avatar-intent-mood={intent.mood}
      data-avatar-intent-gesture={intent.gesture}
      data-avatar-intent-gaze={intent.gaze}
      data-avatar-intent-camera={intent.camera.view}
      style={stageStyle}
    >
      <div ref={containerRef} className="talkinghead-canvas" />
      {status !== 'ready' && (
        <div className="talkinghead-status">
          <div>{status}</div>
          {errorDetail && <small>{errorDetail}</small>}
        </div>
      )}
    </div>
  );
}
