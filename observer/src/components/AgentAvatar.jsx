import { useEffect, useMemo, useRef } from 'react';
import { Text } from '@react-three/drei';
import { useFrame, useLoader } from '@react-three/fiber';
import { TextureLoader } from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';

const DEFAULT_VRM = import.meta.env.VITE_DEFAULT_VRM_URL || '';
const TRANSPARENT_PIXEL =
  'data:image/gif;base64,R0lGODlhAQABAAAAACwAAAAAAQABAAA='; // 1x1 transparent pixel

function emotionToExpression(state) {
  const value = String(state || 'neutral').toLowerCase();
  if (value === 'vulnerable' || value === 'flinch') return 'sad';
  if (value === 'angry' || value === 'intense') return 'angry';
  if (value === 'playful' || value === 'animated') return 'happy';
  if (value === 'calm') return 'relaxed';
  return 'neutral';
}

function resolveAvatarCid(agent, avatarState) {
  return (
    agent?.vrm_avatar_url ||
    avatarState?.vrm_avatar_url ||
    agent?.rigged_avatar_cid ||
    agent?.avatar_cid ||
    ''
  );
}

function applyVRMState(vrm, avatarState, delta) {
  if (!vrm) return;
  if (typeof vrm.update === 'function') vrm.update(delta);

  const expression = emotionToExpression(
    avatarState?.expression_override || avatarState?.current_expression || avatarState?.expression
  );
  const speaking = Boolean(avatarState?.speaking);
  const mouthOpen = Number(avatarState?.mouth_open || (speaking ? 0.7 : 0.05));
  const pose = String(avatarState?.presentation_mode || avatarState?.pose || 'standard');

  try {
    const manager = vrm.expressionManager;
    if (manager?.setValue) {
      manager.setValue('happy', expression === 'happy' ? 1 : 0);
      manager.setValue('angry', expression === 'angry' ? 1 : 0);
      manager.setValue('sad', expression === 'sad' ? 1 : 0);
      manager.setValue('relaxed', expression === 'relaxed' ? 1 : 0.8);
      manager.setValue('aa', mouthOpen);
    }
  } catch {
    // fall back to bone motion below
  }

  try {
    const humanoid = vrm.humanoid;
    const jaw = humanoid?.getNormalizedBoneNode?.('jaw');
    if (jaw) jaw.rotation.x = -0.04 - mouthOpen * 0.35;
    const head = humanoid?.getNormalizedBoneNode?.('head');
    if (head) {
      head.rotation.y = Math.sin(Date.now() / 1000 * 0.8) * 0.03;
      head.rotation.x = expression === 'angry' ? -0.08 : expression === 'sad' ? 0.05 : 0;
    }
    const spine = humanoid?.getNormalizedBoneNode?.('spine');
    if (spine) {
      spine.rotation.z = pose === 'speaking' ? 0.04 : pose === 'presenting' ? 0.03 : pose === 'debate' ? -0.04 : 0;
    }
  } catch {
    // no-op; the fallback rig handles visible motion
  }

  if (vrm.scene) {
    const speed = speaking ? 1.08 : 1.0;
    vrm.scene.rotation.y = Math.sin(Date.now() / 1000 * speed * 0.6) * 0.08;
  }
}

export function AgentAvatar({ agent, avatarState, selected, speaking, vrmUrl, runtimeBaseUrl, position, color, minimal = false }) {
  const fallbackRef = useRef();
  const groupRef = useRef();
  const modelUrl = vrmUrl || agent.vrm_avatar_url || DEFAULT_VRM || '';
  const vrmStateRef = useRef(null);
  const portraitCid = resolveAvatarCid(agent, avatarState);
  const portraitUrl = portraitCid
    ? `${String(runtimeBaseUrl || '').replace(/\/+$/, '')}/ipfs/${portraitCid}`
    : TRANSPARENT_PIXEL;
  const portraitTexture = useLoader(TextureLoader, portraitUrl || TRANSPARENT_PIXEL);
  const isActiveSpeaker = Boolean(
    speaking || (avatarState?.speaker_soul_id && agent?.soul_id === avatarState.speaker_soul_id && avatarState?.speaking)
  );
  const mouthOpen = Number(
    isActiveSpeaker ? avatarState?.mouth_open ?? (speaking ? 0.58 : 0.08) : 0.03
  );
  const speakerState = isActiveSpeaker
    ? avatarState
    : { ...(avatarState || {}), speaking: false, mouth_open: 0.03, presentation_mode: 'listening' };

  useFrame((_, delta) => {
    if (vrmStateRef.current) applyVRMState(vrmStateRef.current, speakerState, delta);
    if (fallbackRef.current) {
      const target = isActiveSpeaker ? 1.08 + mouthOpen * 0.05 : 1.0;
      fallbackRef.current.scale.setScalar(target);
      fallbackRef.current.rotation.y = Math.sin(Date.now() / 1000 * 0.5) * (isActiveSpeaker ? 0.08 : 0.05);
    }
    if (groupRef.current) {
      groupRef.current.position.y = isActiveSpeaker ? Math.sin(Date.now() / 1000 * 4) * 0.08 : 0;
    }
  });

  return (
    <group ref={groupRef} position={position}>
      {modelUrl ? (
        <VRMAvatarModel
          modelUrl={modelUrl}
          vrmStateRef={vrmStateRef}
        />
      ) : (
        <group ref={fallbackRef}>
          <mesh castShadow position={[0, 1.0, 0]}>
            <sphereGeometry args={[0.58, 32, 32]} />
            <meshStandardMaterial color={color} emissive={selected ? '#ffffff' : color} emissiveIntensity={selected ? 0.45 : 0.1} />
          </mesh>
          <mesh position={[0, 0.76, 0]}>
            <capsuleGeometry args={[0.20, 0.56, 8, 16]} />
            <meshStandardMaterial color="#d8b19a" roughness={0.95} />
          </mesh>
          <mesh position={[-0.42, 0.66, 0]} rotation={[0, 0, 0.42]}>
            <capsuleGeometry args={[0.08, 0.48, 6, 12]} />
            <meshStandardMaterial color="#d8b19a" roughness={0.95} />
          </mesh>
          <mesh position={[0.42, 0.66, 0]} rotation={[0, 0, -0.42]}>
            <capsuleGeometry args={[0.08, 0.48, 6, 12]} />
            <meshStandardMaterial color="#d8b19a" roughness={0.95} />
          </mesh>
          <mesh position={[-0.18, -0.12, 0]} rotation={[0, 0, 0.04]}>
            <capsuleGeometry args={[0.09, 0.62, 6, 12]} />
            <meshStandardMaterial color="#5b667a" roughness={0.8} />
          </mesh>
          <mesh position={[0.18, -0.12, 0]} rotation={[0, 0, -0.04]}>
            <capsuleGeometry args={[0.09, 0.62, 6, 12]} />
            <meshStandardMaterial color="#5b667a" roughness={0.8} />
          </mesh>
          <mesh position={[0.12, 1.15, 0.46]}>
            <sphereGeometry args={[0.095, 16, 16]} />
            <meshStandardMaterial color="#faf7ff" />
          </mesh>
          <mesh position={[-0.12, 1.15, 0.46]}>
            <sphereGeometry args={[0.095, 16, 16]} />
            <meshStandardMaterial color="#faf7ff" />
          </mesh>
          <mesh position={[0, 0.97, 0.49]}>
            <boxGeometry args={[0.28, Math.max(0.06, mouthOpen * 0.14), 0.05]} />
            <meshStandardMaterial color="#3e1018" />
          </mesh>
          <mesh position={[0, 1.02, 0.59]}>
            <planeGeometry args={[0.9, 1.2]} />
            <meshBasicMaterial map={portraitTexture} transparent toneMapped={false} />
          </mesh>
        </group>
      )}

      {minimal ? null : (
        <Text
          position={[0, 1.45, 0]}
          fontSize={0.32}
          color={selected ? '#f4c95d' : '#d6dcff'}
          anchorX="center"
          anchorY="middle"
        >
          {isActiveSpeaker ? '* ' : ''}{agent.current_name || agent.soul_id.slice(0, 8)}
        </Text>
      )}
    </group>
  );
}

function VRMAvatarModel({ modelUrl, vrmStateRef }) {
  const gltf = useLoader(GLTFLoader, modelUrl, (assetLoader) => {
    assetLoader.register((parser) => new VRMLoaderPlugin(parser));
  });

  const vrm = useMemo(() => gltf?.userData?.vrm || null, [gltf]);

  useEffect(() => {
    if (!vrm) return;
    vrmStateRef.current = vrm;
    try {
      VRMUtils.rotateVRM0(vrm);
      VRMUtils.removeUnnecessaryJoints(vrm.scene);
    } catch {
      // keep going even if some helper methods are unavailable
    }
    return () => {
      if (vrmStateRef.current === vrm) {
        vrmStateRef.current = null;
      }
    };
  }, [vrm, vrmStateRef]);

  if (!vrm) {
    return null;
  }
  return <primitive object={vrm.scene || gltf.scene} scale={1.6} />;
}
