import { useMemo, useRef } from 'react';
import { Billboard, Html, Text } from '@react-three/drei';
import { useFrame } from '@react-three/fiber';

function resolveAvatarCid(agent, avatarState) {
  return (
    agent?.rigged_avatar_cid ||
    agent?.avatar_cid ||
    avatarState?.avatar_asset ||
    avatarState?.rigged_avatar_cid ||
    ''
  );
}

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

export function AgentAvatar({ agent, avatarState, selected, speaking, runtimeBaseUrl, position, color, minimal = false }) {
  const groupRef = useRef();
  const haloRef = useRef();
  const blinkRef = useRef();
  const mouthRef = useRef();
  const phase = useMemo(() => stablePhase(agent?.soul_id || agent?.current_name), [agent?.current_name, agent?.soul_id]);

  const portraitCid = resolveAvatarCid(agent, avatarState);
  const portraitUrl = portraitCid
    ? `${String(runtimeBaseUrl || '').replace(/\/+$/, '')}/ipfs/${portraitCid}`
    : '';

  const isActiveSpeaker = Boolean(
    speaking || (avatarState?.speaker_soul_id && agent?.soul_id === avatarState.speaker_soul_id && avatarState?.speaking)
  );
  const usesSnapshotLife = Boolean(!avatarState?.speaker_soul_id || agent?.soul_id === avatarState.speaker_soul_id || selected);
  const life = avatarState?.life || {};
  const basePosition = position || [0, 0, 0];

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
      const mouth = isActiveSpeaker
        ? (Number.isFinite(snapshotMouth)
          ? snapshotMouth * (0.88 + Math.abs(Math.sin(t * 12)) * 0.12)
          : 0.35 + Math.abs(Math.sin(t * 10)) * 0.25)
        : 0;
      mouthRef.current.style.opacity = String(isActiveSpeaker ? 0.86 : 0.22);
      mouthRef.current.style.transform = `translateX(-50%) scaleY(${clamp(0.55 + mouth * 2.8, 0.45, 3.4)})`;
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
          className={isActiveSpeaker ? 'speaking-avatar' : ''}
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
                style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                crossOrigin="anonymous"
              />
            ) : (
              <div style={{
                width: '100%', height: '100%',
                background: `radial-gradient(circle at 50% 40%, ${color}44, #0d1020)`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '48px', color,
              }}>
                ◈
              </div>
            )}
            <div
              ref={blinkRef}
              style={{
                position: 'absolute',
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
