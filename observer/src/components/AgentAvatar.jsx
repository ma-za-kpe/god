import { useRef } from 'react';
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

export function AgentAvatar({ agent, avatarState, selected, speaking, runtimeBaseUrl, position, color, minimal = false }) {
  const groupRef = useRef();
  const haloRef = useRef();

  const portraitCid = resolveAvatarCid(agent, avatarState);
  const portraitUrl = portraitCid
    ? `${String(runtimeBaseUrl || '').replace(/\/+$/, '')}/ipfs/${portraitCid}`
    : '';

  const isActiveSpeaker = Boolean(
    speaking || (avatarState?.speaker_soul_id && agent?.soul_id === avatarState.speaker_soul_id && avatarState?.speaking)
  );

  useFrame(() => {
    if (haloRef.current) {
      const pulse = isActiveSpeaker ? 1.0 + Math.sin(Date.now() / 1000 * 5) * 0.1 : (selected ? 1.04 : 1.0);
      haloRef.current.scale.setScalar(pulse);
      haloRef.current.material.opacity = isActiveSpeaker ? 0.95 : (selected ? 0.5 : 0.18);
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
