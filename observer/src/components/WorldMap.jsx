import { Canvas, useThree } from '@react-three/fiber';
import { Billboard, OrbitControls, Text } from '@react-three/drei';
import { useEffect, useMemo } from 'react';
import { AgentAvatar } from './AgentAvatar';
import { useObserverStore } from '../store';
import { API_BASE } from '../hooks/useWorld';

const COLORS = ['#4effb5', '#54c8ff', '#f4c95d', '#cc86ff', '#ff6b88', '#87a7ff', '#7df2e3', '#ffc66b'];
const ROOM_FLOOR_Y = -2.32;
const TILE_SIZE = 0.42;

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

function speakerSoulIdFromSnapshot(snapshot, voicePlayback) {
  const direct =
    voicePlayback?.speakerSoulId ||
    snapshot?.avatar?.controller_soul_id ||
    snapshot?.avatar?.controllerSoulId ||
    snapshot?.avatar?.agent_id ||
    snapshot?.avatar?.agentId ||
    snapshot?.last_dialogue_turn?.sender_soul_id ||
    snapshot?.last_dialogue_turn?.sender_id ||
    snapshot?.avatar?.speaker_soul_id;
  if (direct) return String(direct);
  const speaker = String(snapshot?.voice?.plan?.speaker || '').toLowerCase();
  const agent = (snapshot?.agents || []).find((item) => {
    const name = String(item?.current_name || '').toLowerCase();
    const soulId = String(item?.soul_id || '').toLowerCase();
    return speaker && (name === speaker || soulId === speaker);
  });
  return agent?.soul_id || '';
}

function activeAgentFor(agents, snapshot, selectedSoulId, voicePlayback, mode) {
  if (!agents.length) return null;
  if (mode === 'one') {
    const speakerSoulId = speakerSoulIdFromSnapshot(snapshot, voicePlayback);
    return agents.find((agent) => agent.soul_id === speakerSoulId) || agents[0] || null;
  }
  return agents[activeIndexFor(agents, selectedSoulId || snapshot?.showrunner?.speaker)] || agents[0] || null;
}

function number(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function bodyMotionPlan(avatarState) {
  return (
    avatarState?.body_motion ||
    avatarState?.motion_plan ||
    avatarState?.control_plan ||
    avatarState?.plan?.body_motion ||
    {}
  );
}

function normalizeRoom(rawRoom = {}) {
  const bounds = rawRoom?.bounds || {};
  const xBounds = Array.isArray(bounds.x) ? bounds.x : [-4.2, 4.2];
  const zBounds = Array.isArray(bounds.z) ? bounds.z : [-2.8, 2.8];
  const minX = number(xBounds[0], -4.2);
  const maxX = number(xBounds[1], 4.2);
  const minZ = number(zBounds[0], -2.8);
  const maxZ = number(zBounds[1], 2.8);
  const waypoints = Array.isArray(rawRoom?.waypoints)
    ? rawRoom.waypoints
      .map((item) => ({
        id: String(item?.id || '').slice(0, 18),
        x: number(item?.x, 0),
        z: number(item?.z, 0),
      }))
      .filter((item) => item.id)
    : [];
  return {
    minX,
    maxX,
    minZ,
    maxZ,
    width: Math.max(1, maxX - minX),
    depth: Math.max(1, maxZ - minZ),
    centerX: (minX + maxX) / 2,
    centerZ: (minZ + maxZ) / 2,
    waypoints,
  };
}

function trajectoryFromPlan(plan) {
  const raw = Array.isArray(plan?.trajectory) ? plan.trajectory : [];
  const points = raw
    .map((item) => ({
      x: number(item?.x, Number.NaN),
      z: number(item?.z, Number.NaN),
      label: String(item?.label || '').slice(0, 20),
    }))
    .filter((item) => Number.isFinite(item.x) && Number.isFinite(item.z));
  if (points.length) return points;
  const rootStart = Array.isArray(plan?.root_start || plan?.rootStart) ? (plan.root_start || plan.rootStart) : null;
  if (rootStart && rootStart.length >= 2) {
    return [{ x: number(rootStart[0], 0), z: number(rootStart[1], 0), label: 'start' }];
  }
  return [];
}

function RoomTiles({ room }) {
  const tiles = useMemo(() => {
    const items = [];
    let key = 0;
    for (let x = room.minX + TILE_SIZE / 2; x < room.maxX; x += TILE_SIZE) {
      for (let z = room.minZ + TILE_SIZE / 2; z < room.maxZ; z += TILE_SIZE) {
        const xi = Math.round((x - room.minX) / TILE_SIZE);
        const zi = Math.round((z - room.minZ) / TILE_SIZE);
        items.push({
          key: key += 1,
          x,
          z,
          color: (xi + zi) % 2 === 0 ? '#182036' : '#202a45',
        });
      }
    }
    return items;
  }, [room.maxX, room.maxZ, room.minX, room.minZ]);

  return tiles.map((tile) => (
    <mesh key={tile.key} position={[tile.x, ROOM_FLOOR_Y + 0.003, tile.z]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
      <planeGeometry args={[TILE_SIZE * 0.96, TILE_SIZE * 0.96]} />
      <meshStandardMaterial color={tile.color} roughness={0.84} metalness={0.02} />
    </mesh>
  ));
}

function TrajectoryPath({ points }) {
  const segments = useMemo(() => points.slice(1).map((point, index) => {
    const previous = points[index];
    const dx = point.x - previous.x;
    const dz = point.z - previous.z;
    return {
      key: `${index}-${point.x}-${point.z}`,
      x: previous.x + dx / 2,
      z: previous.z + dz / 2,
      length: Math.max(0.04, Math.hypot(dx, dz)),
      rotationY: -Math.atan2(dz, dx),
    };
  }), [points]);

  return (
    <group>
      {segments.map((segment) => (
        <mesh
          key={segment.key}
          position={[segment.x, ROOM_FLOOR_Y + 0.055, segment.z]}
          rotation={[0, segment.rotationY, 0]}
        >
          <boxGeometry args={[segment.length, 0.035, 0.035]} />
          <meshStandardMaterial color="#f4c95d" emissive="#5c4212" emissiveIntensity={0.18} roughness={0.5} />
        </mesh>
      ))}
      {points.map((point, index) => (
        <mesh key={`${point.x}-${point.z}-${index}`} position={[point.x, ROOM_FLOOR_Y + 0.095, point.z]}>
          <sphereGeometry args={[index === 0 ? 0.07 : 0.09, 18, 10]} />
          <meshStandardMaterial
            color={index === 0 ? '#54c8ff' : '#f4c95d'}
            emissive={index === 0 ? '#164d66' : '#5c4212'}
            emissiveIntensity={0.2}
          />
        </mesh>
      ))}
    </group>
  );
}

function RoomEnvironment({ avatarState, minimal }) {
  const motion = bodyMotionPlan(avatarState);
  const room = useMemo(() => normalizeRoom(motion?.room), [motion?.room]);
  const trajectory = useMemo(() => trajectoryFromPlan(motion), [motion]);
  const wallHeight = minimal ? 5.2 : 5.6;

  return (
    <group>
      <mesh position={[room.centerX, ROOM_FLOOR_Y - 0.02, room.centerZ]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[room.width + 0.18, room.depth + 0.18]} />
        <meshStandardMaterial color="#111827" roughness={0.88} />
      </mesh>
      <RoomTiles room={room} />
      <mesh position={[room.centerX, ROOM_FLOOR_Y + wallHeight / 2, room.minZ - 0.09]} receiveShadow>
        <boxGeometry args={[room.width + 0.28, wallHeight, 0.08]} />
        <meshStandardMaterial color="#162238" roughness={0.82} />
      </mesh>
      <mesh position={[room.minX - 0.09, ROOM_FLOOR_Y + wallHeight / 2, room.centerZ]} receiveShadow>
        <boxGeometry args={[0.08, wallHeight, room.depth + 0.28]} />
        <meshStandardMaterial color="#1a2437" roughness={0.82} />
      </mesh>
      <mesh position={[room.maxX + 0.09, ROOM_FLOOR_Y + wallHeight / 2, room.centerZ]} receiveShadow>
        <boxGeometry args={[0.08, wallHeight, room.depth + 0.28]} />
        <meshStandardMaterial color="#1a2437" roughness={0.82} />
      </mesh>
      <mesh position={[room.minX + 1.15, ROOM_FLOOR_Y + 2.8, room.minZ - 0.14]}>
        <boxGeometry args={[1.25, 0.88, 0.05]} />
        <meshStandardMaterial color="#284a66" emissive="#102a3a" emissiveIntensity={0.16} roughness={0.56} />
      </mesh>
      <group position={[room.maxX - 1.0, ROOM_FLOOR_Y + 0.28, room.minZ + 0.54]}>
        <mesh position={[0, 0.24, 0]}>
          <boxGeometry args={[0.62, 0.08, 0.48]} />
          <meshStandardMaterial color="#574433" roughness={0.75} />
        </mesh>
        <mesh position={[0, 0.62, -0.2]}>
          <boxGeometry args={[0.62, 0.72, 0.08]} />
          <meshStandardMaterial color="#684f39" roughness={0.75} />
        </mesh>
      </group>
      <group position={[room.minX + 0.9, ROOM_FLOOR_Y + 0.14, room.maxZ - 0.72]}>
        <mesh position={[0, 0.16, 0]}>
          <cylinderGeometry args={[0.14, 0.2, 0.32, 18]} />
          <meshStandardMaterial color="#7d5744" roughness={0.76} />
        </mesh>
        <mesh position={[0, 0.56, 0]} scale={[0.28, 0.42, 0.28]}>
          <sphereGeometry args={[1, 24, 16]} />
          <meshStandardMaterial color="#2f8f62" roughness={0.62} />
        </mesh>
      </group>
      {room.waypoints.map((point) => (
        <group key={point.id} position={[point.x, ROOM_FLOOR_Y + 0.035, point.z]}>
          <mesh rotation={[-Math.PI / 2, 0, 0]}>
            <ringGeometry args={[0.12, 0.15, 24]} />
            <meshBasicMaterial color="#7df2e3" transparent opacity={0.78} />
          </mesh>
          {!minimal ? (
            <Billboard position={[0, 0.28, 0]}>
              <Text fontSize={0.11} color="#d6dcff" anchorX="center" anchorY="middle" outlineWidth={0.005} outlineColor="#050712">
                {point.id}
              </Text>
            </Billboard>
          ) : null}
        </group>
      ))}
      <TrajectoryPath points={trajectory} />
    </group>
  );
}

function SceneCamera({ minimal }) {
  const { camera } = useThree();
  useEffect(() => {
    if (minimal) {
      camera.position.set(0, 1.05, 8.2);
      camera.fov = 64;
      camera.lookAt(0, -1.05, 0);
    } else {
      camera.position.set(0, 8.5, 18);
      camera.fov = 42;
      camera.lookAt(0, 0, 0);
    }
    camera.updateProjectionMatrix();
  }, [camera, minimal]);
  return null;
}

export function WorldMap({ mode, minimal = false }) {
  const agents = useObserverStore((s) => s.agents).filter((a) => a && a.is_alive !== false);
  const snapshot = useObserverStore((s) => s.snapshot) || {};
  const selectedSoulId = useObserverStore((s) => s.selectedSoulId);
  const voicePlayback = useObserverStore((s) => s.voicePlayback);
  const activeAgent = activeAgentFor(agents, snapshot, selectedSoulId, voicePlayback, mode);
  const avatarState = snapshot.avatar || {};
  const speakingId = speakerSoulIdFromSnapshot(snapshot, voicePlayback);

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
        camera={minimal ? { position: [0, 1.15, 6.25], fov: 58 } : { position: [0, 8.5, 18], fov: 42 }}
        gl={minimal ? { preserveDrawingBuffer: true } : undefined}
        shadows
        legacy
      >
        <SceneCamera minimal={minimal} />
        <color attach="background" args={['#050712']} />
        <ambientLight intensity={0.85} />
        <directionalLight position={[8, 12, 8]} intensity={2.2} castShadow />
        <directionalLight position={[-8, 4, -6]} intensity={0.8} color="#66ccff" />

        <group position={[0, -0.15, 0]}>
          {mode === 'one' ? <RoomEnvironment avatarState={avatarState} minimal={minimal} /> : null}
          {layout.map(({ agent, pos }, index) => {
            if (!agent) return null;
            const isSelected = agent.soul_id === (selectedSoulId || activeAgent?.soul_id);
            const isSpeaking = agent.soul_id === speakingId &&
              (!voicePlayback?.status || ['starting', 'playing'].includes(voicePlayback.status));
            const modelUrl = agent.vrm_avatar_url || snapshot.avatar?.vrm_avatar_url || import.meta.env.VITE_DEFAULT_VRM_URL || '';
            const color = COLORS[index % COLORS.length];
            const controlActive = mode === 'one' && Boolean(
              avatarState?.control_mode === 'llm-avatar-control' ||
              avatarState?.controlMode === 'llm-avatar-control' ||
              avatarState?.body_motion ||
              avatarState?.motion_plan ||
              avatarState?.control_plan
            );
            return (
              <AgentAvatar
                key={agent.soul_id}
                agent={agent}
                avatarState={avatarState}
                selected={isSelected}
                speaking={controlActive || isSpeaking}
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
              {mode === 'one' ? 'solo avatar' : 'ensemble'}
            </Text>
          </Billboard>
        )}

        {minimal ? null : <OrbitControls enablePan={false} enableRotate={mode !== 'one'} enableZoom={mode !== 'one'} />}
      </Canvas>
    </div>
  );
}
