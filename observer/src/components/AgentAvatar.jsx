import { useEffect, useMemo, useRef, useState } from 'react';
import { Billboard, Html, Text } from '@react-three/drei';
import { useFrame } from '@react-three/fiber';
import { selectAvatarSource, sourceStatusText } from '../avatarSource';

function clamp(value, lower, upper) {
  return Math.max(lower, Math.min(upper, value));
}

function lifeNumber(life, key) {
  const parsed = Number(life?.[key]);
  return Number.isFinite(parsed) ? parsed : Number.NaN;
}

function stablePhase(value) {
  const text = String(value || '');
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) {
    hash = ((hash << 5) - hash + text.charCodeAt(i)) | 0;
  }
  return (Math.abs(hash) % 6283) / 1000;
}

function nowMs() {
  return typeof performance !== 'undefined' ? performance.now() : Date.now();
}

export function AgentAvatar({
  agent,
  avatarState,
  selected,
  speaking,
  runtimeBaseUrl,
  position,
  color,
  voicePlayback,
  minimal = false,
}) {
  const groupRef = useRef();
  const avatarRootRef = useRef();
  const haloRef = useRef();
  const blinkRef = useRef();
  const mouthRef = useRef();
  const sourceSwitchStartedAt = useRef(nowMs());
  const mouthLatencyRef = useRef(null);
  const [videoReady, setVideoReady] = useState(false);
  const [videoFailed, setVideoFailed] = useState(false);
  const [switchMs, setSwitchMs] = useState(0);
  const [mouthLatencyMs, setMouthLatencyMs] = useState(null);
  const phase = useMemo(() => stablePhase(agent?.soul_id || agent?.current_name), [agent?.current_name, agent?.soul_id]);

  const playbackMatchesAgent = Boolean(
    voicePlayback?.status === 'playing' &&
    (
      (voicePlayback?.speakerSoulId && agent?.soul_id === voicePlayback.speakerSoulId) ||
      (!voicePlayback?.speakerSoulId && voicePlayback?.speakerName &&
        String(agent?.current_name || '').toLowerCase() === String(voicePlayback.speakerName).toLowerCase())
    )
  );
  const isActiveSpeaker = Boolean(
    speaking ||
    playbackMatchesAgent ||
    (avatarState?.speaker_soul_id && agent?.soul_id === avatarState.speaker_soul_id && avatarState?.speaking)
  );
  const avatarSource = useMemo(
    () => selectAvatarSource({ agent, avatarState, runtimeBaseUrl, speaking: isActiveSpeaker }),
    [agent, avatarState, runtimeBaseUrl, isActiveSpeaker]
  );
  const portraitUrl = avatarSource.fallback?.url || '';
  const videoUrl = avatarSource.video?.url || '';
  const fallbackInitial = avatarSource.fallback?.initial || (agent?.current_name || agent?.soul_id || '?').slice(0, 1).toUpperCase();
  const sourceLabel = sourceStatusText(avatarSource);
  const sourceStatus = videoFailed
    ? 'video-error-fallback'
    : (videoUrl ? `${sourceLabel}-${videoReady ? 'ready' : 'preloading'}` : avatarSource.status);
  const showVideo = Boolean(videoUrl && videoReady && !videoFailed);
  const usesSnapshotLife = Boolean(!avatarState?.speaker_soul_id || agent?.soul_id === avatarState.speaker_soul_id || selected);
  const life = avatarState?.life || {};
  const basePosition = position || [0, 0, 0];

  useEffect(() => {
    sourceSwitchStartedAt.current = nowMs();
    setVideoReady(false);
    setVideoFailed(false);
    setSwitchMs(0);
  }, [videoUrl]);

  useEffect(() => {
    mouthLatencyRef.current = null;
    setMouthLatencyMs(null);
  }, [voicePlayback?.utteranceId]);

  const markVideoReady = (event) => {
    setVideoFailed(false);
    setVideoReady(true);
    setSwitchMs(Math.max(0, Math.round(nowMs() - sourceSwitchStartedAt.current)));
    const play = event?.currentTarget?.play?.();
    if (play?.catch) play.catch(() => {});
  };

  const markVideoFailed = () => {
    setVideoReady(false);
    setVideoFailed(true);
    setSwitchMs(Math.max(0, Math.round(nowMs() - sourceSwitchStartedAt.current)));
  };

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    const localBreath = 0.5 + 0.5 * Math.sin(t * 2.1 + phase);
    const snapshotBreath = usesSnapshotLife ? lifeNumber(life, 'breathing_phase') : Number.NaN;
    const breath = Number.isFinite(snapshotBreath)
      ? clamp(snapshotBreath * 0.7 + localBreath * 0.3, 0, 1)
      : localBreath;
    const snapshotHeadX = usesSnapshotLife ? lifeNumber(life, 'head_sway_x') : Number.NaN;
    const snapshotHeadY = usesSnapshotLife ? lifeNumber(life, 'head_sway_y') : Number.NaN;
    const headSwayX = Number.isFinite(snapshotHeadX)
      ? snapshotHeadX + Math.sin(t * 1.3 + phase) * 0.018
      : Math.sin(t * 1.3 + phase) * 0.075;
    const headSwayY = Number.isFinite(snapshotHeadY)
      ? snapshotHeadY
      : Math.cos(t * 0.9 + phase) * 0.04;

    if (groupRef.current) {
      groupRef.current.position.set(basePosition[0], basePosition[1] + (breath - 0.5) * 0.22, basePosition[2]);
      groupRef.current.rotation.z = headSwayX * 0.7;
      groupRef.current.rotation.x = headSwayY * 0.45;
    }

    if (haloRef.current) {
      const pulse = isActiveSpeaker ? 1.0 + Math.sin(t * 5) * 0.1 : (selected ? 1.04 : 1.0);
      haloRef.current.scale.setScalar(pulse);
      haloRef.current.material.opacity = isActiveSpeaker ? 0.95 : (selected ? 0.5 : 0.18);
    }

    if (blinkRef.current) {
      const localBlink = clamp(Math.pow(Math.max(0, Math.sin(t * 0.8 + phase) - 0.92) * 14, 2), 0, 1);
      const blink = usesSnapshotLife && life?.blink_state === true ? 1 : localBlink;
      blinkRef.current.style.opacity = String(blink);
      blinkRef.current.style.transform = `scaleY(${clamp(1 - blink * 0.82, 0.12, 1)})`;
    }

    if (mouthRef.current) {
      const snapshotMouth = usesSnapshotLife ? lifeNumber(life, 'mouth_amplitude') : Number.NaN;
      const playbackMouth = playbackMatchesAgent ? Number(voicePlayback?.mouthAmplitude || 0) : Number.NaN;
      const mouth = isActiveSpeaker
        ? (Number.isFinite(playbackMouth) && playbackMouth > 0
          ? playbackMouth * (0.76 + Math.abs(Math.sin(t * 14 + phase)) * 0.24)
          : Number.isFinite(snapshotMouth)
          ? snapshotMouth * (0.88 + Math.abs(Math.sin(t * 12)) * 0.12)
          : 0.35 + Math.abs(Math.sin(t * 10)) * 0.25)
        : 0;
      mouthRef.current.style.opacity = String(isActiveSpeaker ? 0.86 : 0.22);
      mouthRef.current.style.transform = `translateX(-50%) scaleY(${clamp(0.55 + mouth * 2.8, 0.45, 3.4)})`;
      if (
        playbackMatchesAgent &&
        voicePlayback?.startedAtMs &&
        mouth > 0.04 &&
        mouthLatencyRef.current === null
      ) {
        const latency = Math.max(0, Math.round(nowMs() - voicePlayback.startedAtMs));
        mouthLatencyRef.current = latency;
        setMouthLatencyMs(latency);
      }
    }
  });

  return (
    <group ref={groupRef} position={position}>
      {/* Halo ring — pulses when speaking */}
      <Billboard>
        <mesh ref={haloRef} position={[0, 1.1, -0.08]}>
          <ringGeometry args={[1.08, 1.28, 48]} />
          <meshBasicMaterial color={isActiveSpeaker ? '#f4c95d' : color} transparent opacity={0.18} />
        </mesh>
      </Billboard>

      {/* Portrait card via real HTML img — no WebGL texture issues */}
      <Html
        center
        position={[0, 1.1, 0]}
        style={{ width: '170px', height: '210px', pointerEvents: 'none', userSelect: 'none' }}
        occlude={false}
      >
        <div
          ref={avatarRootRef}
          className={isActiveSpeaker ? 'speaking-avatar' : ''}
          data-avatar-source-kind={avatarSource.activeKind}
          data-avatar-source-status={sourceStatus}
          data-avatar-fallback-kind={avatarSource.fallbackKind}
          data-avatar-source-switch-ms={switchMs}
          data-avatar-black-frame-ms="0"
          data-voice-playback-status={playbackMatchesAgent ? voicePlayback?.status || '' : ''}
          data-voice-mouth-amplitude={playbackMatchesAgent ? Number(voicePlayback?.mouthAmplitude || 0).toFixed(4) : '0.0000'}
          data-voice-mouth-latency-ms={mouthLatencyMs ?? ''}
          data-voice-latency-target-ms={playbackMatchesAgent ? voicePlayback?.latencyTargetMs || 300 : ''}
          data-voice-lip-sync-source={playbackMatchesAgent ? voicePlayback?.lipSyncSource || 'audio_rms' : ''}
          style={{
            width: '170px',
            height: '210px',
            position: 'relative',
            '--glow-color': color,
          }}
        >
          {/* Portrait image */}
          <div style={{
            width: '170px',
            height: '210px',
            border: `2.5px solid ${isActiveSpeaker ? '#f4c95d' : (selected ? '#fff' : color)}`,
            boxShadow: isActiveSpeaker
              ? `0 0 24px ${color}, 0 0 10px #f4c95d`
              : (selected ? `0 0 14px ${color}` : `0 0 6px ${color}55`),
            borderRadius: '7px',
            overflow: 'hidden',
            background: '#0d1020',
            animation: isActiveSpeaker ? 'portrait-glow 0.8s ease-in-out infinite' : 'none',
          }}>
            {portraitUrl ? (
              <img
                src={portraitUrl}
                alt={agent.current_name || 'agent'}
                style={{
                  position: 'absolute',
                  inset: 0,
                  zIndex: 1,
                  width: '100%',
                  height: '100%',
                  objectFit: 'cover',
                  display: 'block',
                }}
                crossOrigin="anonymous"
              />
            ) : (
              <div style={{
                position: 'absolute',
                inset: 0,
                zIndex: 1,
                width: '100%', height: '100%',
                background: `radial-gradient(circle at 50% 40%, ${color}44, #0d1020)`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '48px', color,
              }}>
                {fallbackInitial}
              </div>
            )}
            {videoUrl && !videoFailed && (
              <video
                src={videoUrl}
                muted
                autoPlay
                loop={avatarSource.video?.kind !== 'cinematic'}
                playsInline
                preload="auto"
                crossOrigin="anonymous"
                onLoadedData={markVideoReady}
                onCanPlay={markVideoReady}
                onPlaying={markVideoReady}
                onError={markVideoFailed}
                onEnded={() => {
                  if (avatarSource.video?.kind === 'cinematic') setVideoReady(false);
                }}
                style={{
                  position: 'absolute',
                  inset: 0,
                  zIndex: 2,
                  width: '100%',
                  height: '100%',
                  objectFit: 'cover',
                  opacity: showVideo ? 1 : 0,
                  transition: 'opacity 220ms ease',
                  background: 'transparent',
                }}
              />
            )}
            <div
              ref={blinkRef}
              style={{
                position: 'absolute',
                zIndex: 3,
                left: '24%',
                right: '24%',
                top: '32%',
                height: '12px',
                display: 'flex',
                justifyContent: 'space-between',
                transformOrigin: 'center',
                opacity: 0,
                pointerEvents: 'none',
              }}
            >
              <span style={{ width: '42%', height: '100%', borderRadius: '999px', background: 'rgba(5,7,18,0.86)' }} />
              <span style={{ width: '42%', height: '100%', borderRadius: '999px', background: 'rgba(5,7,18,0.86)' }} />
            </div>
            <div
              ref={mouthRef}
              style={{
                position: 'absolute',
                zIndex: 3,
                left: '50%',
                bottom: '22%',
                width: '46px',
                height: '7px',
                borderRadius: '999px',
                background: isActiveSpeaker ? '#2b1015' : 'rgba(244,247,255,0.2)',
                boxShadow: `0 0 10px ${color}55`,
                transform: 'translateX(-50%)',
                transformOrigin: 'center',
                opacity: 0.2,
                pointerEvents: 'none',
              }}
            />
          </div>

          {/* Speaking equalizer bars */}
          {isActiveSpeaker && (
            <div style={{
              position: 'absolute',
              bottom: '-18px',
              left: '50%',
              transform: 'translateX(-50%)',
              display: 'flex',
              alignItems: 'flex-end',
              gap: '3px',
              height: '22px',
            }}>
              {[1, 2, 3, 4, 5].map((i) => (
                <span
                  key={i}
                  className="speaking-bar"
                  style={{ animationDelay: `${(i - 1) * 0.1}s` }}
                />
              ))}
            </div>
          )}
        </div>
      </Html>

      {/* Name label */}
      {!minimal && (
        <Billboard position={[0, 2.65, 0]}>
          <Text
            fontSize={0.28}
            color={isActiveSpeaker ? '#f4c95d' : (selected ? '#ffffff' : '#d6dcff')}
            anchorX="center"
            anchorY="middle"
            outlineWidth={0.018}
            outlineColor="#050712"
          >
            {isActiveSpeaker ? '▶ ' : ''}{agent.current_name || agent.soul_id?.slice(0, 8)}
          </Text>
        </Billboard>
      )}
    </group>
  );
}
