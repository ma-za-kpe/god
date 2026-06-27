import { Canvas } from '@react-three/fiber';
import { Billboard, OrbitControls, Text } from '@react-three/drei';
import { useMemo } from 'react';
import { AgentAvatar } from './AgentAvatar';
import { useObserverStore } from '../store';
import { API_BASE } from '../hooks/useWorld';

const COLORS = ['#4effb5', '#54c8ff', '#f4c95d', '#cc86ff', '#ff6b88', '#87a7ff', '#7df2e3', '#ffc66b'];

function indexToHex(i) {
  if (i === 0) return { q: 0, r: 0 };
  let ring = 1;
  let count = 1;
  while (count + 6 * ring <= i) {
    count += 6 * ring;
    ring += 1;
  }
  const posInRing = i - count;
  const dirs = [[1, -1], [1, 0], [0, 1], [-1, 1], [-1, 0], [0, -1]];
  const dir = Math.floor(posInRing / ring);
  const step = posInRing % ring;
  const startQ = -ring * dirs[(dir + 4) % 6][0];
  const startR = -ring * dirs[(dir + 4) % 6][1];
  return { q: startQ + dirs[dir][0] * step, r: startR + dirs[dir][1] * step };
}

function hexToWorld({ q, r }) {
  const size = 3.2;
  return {
    x: size * (1.5 * q),
    z: size * (Math.sqrt(3) / 2 * q + Math.sqrt(3) * r),
  };
}

function activeIndexFor(agents, selectedSoulId) {
  if (!agents.length) return 0;
  const selected = agents.findIndex((agent) => agent.soul_id === selectedSoulId);
  return selected >= 0 ? selected : 0;
}

export function WorldMap({ mode, minimal = false }) {
  const agents = useObserverStore((s) => s.agents).filter((a) => a && a.is_alive !== false);
  const snapshot = useObserverStore((s) => s.snapshot) || {};
  const selectedSoulId = useObserverStore((s) => s.selectedSoulId);
  const voicePlayback = useObserverStore((s) => s.voicePlayback);
  const activeIndex = activeIndexFor(agents, selectedSoulId || snapshot?.showrunner?.speaker);
  const activeAgent = agents[activeIndex] || agents[0] || null;
  const avatarState = snapshot.avatar || {};
  const speakingId = snapshot.last_dialogue_turn?.sender_soul_id || snapshot.last_dialogue_turn?.sender_id || null;

  const layout = useMemo(() => {
    if (mode === 'one' || agents.length <= 1) {
      return [{ agent: activeAgent || agents[0], pos: [0, 0, 0] }];
    }
    return agents.map((agent, i) => {
      const { x, z } = hexToWorld(indexToHex(i));
      return { agent, pos: [x, 0, z] };
    });
  }, [agents, activeAgent, mode]);

  return (
    <div className="world-shell">
      <Canvas
        camera={{ position: [0, 8.5, 18], fov: 42 }}
        shadows
        legacy
      >
        <color attach="background" args={['#050712']} />
        <ambientLight intensity={0.85} />
        <directionalLight position={[8, 12, 8]} intensity={2.2} castShadow />
        <directionalLight position={[-8, 4, -6]} intensity={0.8} color="#66ccff" />

        <group position={[0, -0.15, 0]}>
          {layout.map(({ agent, pos }, index) => {
            if (!agent) return null;
            const isSelected = agent.soul_id === (selectedSoulId || activeAgent?.soul_id);
            const isSpeaking = agent.soul_id === speakingId;
            const modelUrl = agent.vrm_avatar_url || snapshot.avatar?.vrm_avatar_url || import.meta.env.VITE_DEFAULT_VRM_URL || '';
            const color = COLORS[index % COLORS.length];
            return (
              <AgentAvatar
                key={agent.soul_id}
                agent={agent}
                avatarState={avatarState}
                selected={isSelected}
                speaking={isSpeaking}
                vrmUrl={modelUrl}
                position={pos}
                color={color}
                runtimeBaseUrl={API_BASE}
                voicePlayback={voicePlayback}
                minimal={minimal}
              />
            );
          })}
          {mode === 'one' || agents.length <= 1 || minimal ? null : (
            <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
              <planeGeometry args={[60, 60]} />
              <meshStandardMaterial color="#0d1020" />
            </mesh>
          )}
        </group>

        {minimal ? null : (
          <Billboard position={[0, 5.5, 0]}>
            <Text fontSize={0.55} color="#f4c95d" anchorX="center" anchorY="middle">
              {mode === 'one' ? 'solo voice' : 'ensemble'}
            </Text>
          </Billboard>
        )}

        {minimal ? null : <OrbitControls enablePan={false} enableRotate={mode !== 'one'} enableZoom={mode !== 'one'} />}
      </Canvas>
    </div>
  );
}
