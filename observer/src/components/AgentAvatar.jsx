import { useEffect, useRef, useState } from 'react';
import { Billboard, Text } from '@react-three/drei';
import { useFrame } from '@react-three/fiber';
import { TextureLoader, MeshBasicMaterial } from 'three';
import { Suspense } from 'react';

const TRANSPARENT_PIXEL =
  'data:image/gif;base64,R0lGODlhAQABAAAAACwAAAAAAQABAAA=';

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
  const cardRef = useRef();
  const ringRef = useRef();
  const [portraitTexture, setPortraitTexture] = useState(null);

  const portraitCid = resolveAvatarCid(agent, avatarState);
  const portraitUrl = portraitCid
    ? `${String(runtimeBaseUrl || '').replace(/\/+$/, '')}/ipfs/${portraitCid}`
    : TRANSPARENT_PIXEL;

  const isActiveSpeaker = Boolean(
    speaking || (avatarState?.speaker_soul_id && agent?.soul_id === avatarState.speaker_soul_id && avatarState?.speaking)
  );

  useEffect(() => {
    let disposed = false;
    const loader = new TextureLoader();
    loader.crossOrigin = 'anonymous';
    loader.load(
      portraitUrl,
      (texture) => {
        if (disposed) return;
        texture.colorSpace = 'srgb';
        texture.needsUpdate = true;
        setPortraitTexture(texture);
      },
      undefined,
      () => {
        if (disposed) return;
        setPortraitTexture(null);
      }
    );
    return () => {
      disposed = true;
    };
  }, [portraitUrl]);

  useFrame((_, delta) => {
    if (!groupRef.current) return;
    // Bob up when speaking
    const targetY = isActiveSpeaker ? Math.sin(Date.now() / 1000 * 4) * 0.12 : 0;
    groupRef.current.position.y += (targetY - groupRef.current.position.y) * 0.15;

    // Pulse ring when speaking
    if (ringRef.current) {
      const pulse = isActiveSpeaker ? 1.0 + Math.sin(Date.now() / 1000 * 6) * 0.08 : 1.0;
      ringRef.current.scale.setScalar(pulse);
      ringRef.current.material.opacity = isActiveSpeaker ? 0.85 : (selected ? 0.5 : 0.2);
    }

    // Card subtle sway
    if (cardRef.current) {
      cardRef.current.rotation.y = Math.sin(Date.now() / 1000 * 0.4) * (isActiveSpeaker ? 0.04 : 0.02);
    }
  });

  // Portrait card dimensions
  const cardW = 1.6;
  const cardH = 2.0;

  return (
    <group ref={groupRef} position={position}>
      <group ref={cardRef}>
        {/* Background panel */}
        <mesh position={[0, cardH / 2, -0.01]}>
          <planeGeometry args={[cardW + 0.08, cardH + 0.08]} />
          <meshBasicMaterial color={selected ? '#ffffff' : color} transparent opacity={isActiveSpeaker ? 0.18 : 0.08} />
        </mesh>

        {/* Portrait image */}
        <mesh position={[0, cardH / 2, 0]}>
          <planeGeometry args={[cardW, cardH]} />
          <meshBasicMaterial
            map={portraitTexture || undefined}
            transparent
            toneMapped={false}
            color={portraitTexture ? '#ffffff' : color}
            opacity={portraitTexture ? 1.0 : 0.35}
          />
        </mesh>

        {/* Glow border ring */}
        <mesh ref={ringRef} position={[0, cardH / 2, -0.02]}>
          <ringGeometry args={[0.92, 1.0, 32]} />
          <meshBasicMaterial color={color} transparent opacity={0.2} />
        </mesh>

        {/* Speaking mouth indicator */}
        {isActiveSpeaker && (
          <mesh position={[0, 0.05, 0.01]}>
            <planeGeometry args={[0.4, 0.08 + Math.sin(Date.now() / 1000 * 8) * 0.04]} />
            <meshBasicMaterial color={color} transparent opacity={0.9} />
          </mesh>
        )}
      </group>

      {/* Name label — always billboard so it faces camera */}
      {!minimal && (
        <Billboard position={[0, cardH + 0.35, 0]}>
          <Text
            fontSize={0.26}
            color={isActiveSpeaker ? '#f4c95d' : (selected ? '#ffffff' : '#d6dcff')}
            anchorX="center"
            anchorY="middle"
            outlineWidth={0.015}
            outlineColor="#050712"
          >
            {isActiveSpeaker ? '▶ ' : ''}{agent.current_name || agent.soul_id?.slice(0, 8)}
          </Text>
        </Billboard>
      )}
    </group>
  );
}
