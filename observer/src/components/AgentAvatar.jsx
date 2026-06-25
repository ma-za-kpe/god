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
    if (!groupRef.current) return;
    const targetY = isActiveSpeaker ? Math.sin(Date.now() / 1000 * 4) * 0.18 : 0;
    groupRef.current.position.y += (targetY - groupRef.current.position.y) * 0.12;

    if (haloRef.current) {
      const pulse = isActiveSpeaker ? 1.0 + Math.sin(Date.now() / 1000 * 5) * 0.12 : (selected ? 1.05 : 1.0);
      haloRef.current.scale.setScalar(pulse);
      haloRef.current.material.opacity = isActiveSpeaker ? 0.9 : (selected ? 0.55 : 0.2);
    }
  });

  return (
    <group ref={groupRef} position={position}>
      {/* Halo ring behind portrait */}
      <Billboard>
        <mesh ref={haloRef} position={[0, 1.0, -0.05]}>
          <ringGeometry args={[1.05, 1.22, 48]} />
          <meshBasicMaterial color={color} transparent opacity={0.2} />
        </mesh>
      </Billboard>

      {/* Portrait card rendered as real HTML img — bypasses WebGL texture issues */}
      <Html
        center
        position={[0, 1.0, 0]}
        style={{
          width: '160px',
          height: '200px',
          pointerEvents: 'none',
          userSelect: 'none',
        }}
        occlude={false}
      >
        <div style={{
          width: '160px',
          height: '200px',
          border: `2.5px solid ${isActiveSpeaker ? '#f4c95d' : (selected ? '#ffffff' : color)}`,
          boxShadow: isActiveSpeaker
            ? `0 0 22px ${color}, 0 0 8px #f4c95d`
            : (selected ? `0 0 12px ${color}` : `0 0 6px ${color}55`),
          borderRadius: '6px',
          overflow: 'hidden',
          background: '#0d1020',
          transition: 'box-shadow 0.2s, border-color 0.2s',
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
              width: '100%',
              height: '100%',
              background: `radial-gradient(circle at 50% 40%, ${color}44, #0d1020)`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '40px',
              color,
            }}>
              ◈
            </div>
          )}
          {isActiveSpeaker && (
            <div style={{
              position: 'absolute',
              bottom: '6px',
              left: '50%',
              transform: 'translateX(-50%)',
              display: 'flex',
              gap: '3px',
            }}>
              {[0, 1, 2, 3].map(i => (
                <div key={i} style={{
                  width: '4px',
                  height: `${8 + Math.sin((Date.now() / 1000 * 6) + i * 1.2) * 6}px`,
                  background: '#f4c95d',
                  borderRadius: '2px',
                  transition: 'height 0.05s',
                }} />
              ))}
            </div>
          )}
        </div>
      </Html>

      {/* Name label */}
      {!minimal && (
        <Billboard position={[0, 2.5, 0]}>
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
