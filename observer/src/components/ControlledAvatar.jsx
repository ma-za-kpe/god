import React, { Suspense, useEffect, useMemo, useRef } from 'react';
import { Html, Text } from '@react-three/drei';
import { useFrame, useLoader } from '@react-three/fiber';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';
import { resolveBodyMotionPlan, sampleBodyMotionPlan } from '../avatarMotion';
import { buildAlphabetVisemeTrack, sampleVisemeTrack, scaleVisemeSample, VRM_VISEMES } from '../lipSync';

function clamp(value, lower, upper) {
  return Math.max(lower, Math.min(upper, value));
}

function lifeNumber(life, key) {
  const parsed = Number(life?.[key]);
  return Number.isFinite(parsed) ? parsed : Number.NaN;
}

function nowMs() {
  return typeof performance !== 'undefined' ? performance.now() : Date.now();
}

function stablePhase(value) {
  const text = String(value || '');
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) {
    hash = ((hash << 5) - hash + text.charCodeAt(i)) | 0;
  }
  return (Math.abs(hash) % 6283) / 1000;
}

function playbackElapsedSeconds({ voicePlayback, playbackMatchesAgent, clock, phase }) {
  return playbackMatchesAgent && voicePlayback?.startedAtMs
    ? Math.max(0, (nowMs() - voicePlayback.startedAtMs) / 1000)
    : (clock.getElapsedTime() + phase) % Math.max(3.8, Number(voicePlayback?.durationSeconds || 0) || 3.8);
}

function voiceMatchesAgent(agent, voicePlayback) {
  return Boolean(
    voicePlayback?.status === 'playing' &&
    (
      (voicePlayback?.speakerSoulId && agent?.soul_id === voicePlayback.speakerSoulId) ||
      (!voicePlayback?.speakerSoulId && voicePlayback?.speakerName &&
        String(agent?.current_name || '').toLowerCase() === String(voicePlayback.speakerName).toLowerCase())
    )
  );
}

function rigState({
  agent,
  avatarState,
  voicePlayback,
  isActiveSpeaker,
  playbackMatchesAgent,
  track,
  bodyMotionPlan,
  phase,
  clock,
}) {
  const life = avatarState?.life || {};
  const elapsed = playbackElapsedSeconds({ voicePlayback, playbackMatchesAgent, clock, phase });
  const snapshotMouth = lifeNumber(life, 'mouth_amplitude');
  const playbackMouth = playbackMatchesAgent ? Number(voicePlayback?.mouthAmplitude || 0) : Number.NaN;
  const baseAmplitude = isActiveSpeaker
    ? clamp(
      Math.max(
        Number.isFinite(playbackMouth) ? playbackMouth : 0,
        Number.isFinite(snapshotMouth) ? snapshotMouth : 0,
        0.18
      ),
      0,
      1
    )
    : 0;
  const syllablePulse = isActiveSpeaker ? 0.82 + Math.abs(Math.sin(clock.getElapsedTime() * 17 + phase)) * 0.18 : 0;
  const sample = scaleVisemeSample(sampleVisemeTrack(track, elapsed), clamp(baseAmplitude * syllablePulse + 0.12, 0, 1));
  const localBreath = 0.5 + 0.5 * Math.sin(clock.getElapsedTime() * 2.1 + phase);
  const snapshotBreath = lifeNumber(life, 'breathing_phase');
  const breath = Number.isFinite(snapshotBreath)
    ? clamp(snapshotBreath * 0.7 + localBreath * 0.3, 0, 1)
    : localBreath;
  const headSway = {
    x: Math.sin(clock.getElapsedTime() * 0.8 + phase) * (isActiveSpeaker ? 0.05 : 0.028),
    y: Math.sin(clock.getElapsedTime() * 0.65 + phase) * (isActiveSpeaker ? 0.12 : 0.055),
    z: Math.sin(clock.getElapsedTime() * 1.25 + phase) * (isActiveSpeaker ? 0.035 : 0.018),
  };
  const blink = clamp(Math.pow(Math.max(0, Math.sin(clock.getElapsedTime() * 0.74 + phase) - 0.9) * 10, 2), 0, 1);
  const bodyMotion = sampleBodyMotionPlan(bodyMotionPlan, elapsed);

  return {
    ...sample,
    agentName: agent?.current_name || agent?.soul_id || '',
    breath,
    headSway,
    blink,
    speaking: isActiveSpeaker,
    mouth: clamp(sample.jaw + baseAmplitude * 0.38, 0, 1),
    bodyMotion,
  };
}

class RigErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) return this.props.fallback;
    return this.props.children;
  }
}

function RigTelemetry({
  kind,
  status,
  isActiveSpeaker,
  playbackMatchesAgent,
  voicePlayback,
  bodyMotionPlan,
}) {
  return (
    <Html
      center
      position={[0, -1.75, 0]}
      style={{
        width: '1px',
        height: '1px',
        overflow: 'hidden',
        opacity: 0,
        pointerEvents: 'none',
        userSelect: 'none',
      }}
      occlude={false}
    >
      <div
        data-avatar-source-kind={kind}
        data-avatar-source-status={status}
        data-live-lip-renderer-status="not-required"
        data-avatar-control-mode="speech-driven-rig"
        data-avatar-video-mode="disabled-for-one"
        data-body-motion-source={bodyMotionPlan?.source || ''}
        data-body-motion-target-runtime={bodyMotionPlan?.targetRuntime || ''}
        data-body-motion-status={bodyMotionPlan?.status || ''}
        data-voice-playback-status={playbackMatchesAgent ? voicePlayback?.status || '' : ''}
        data-voice-mouth-amplitude={playbackMatchesAgent ? Number(voicePlayback?.mouthAmplitude || 0).toFixed(4) : '0.0000'}
        data-voice-lip-sync-source={playbackMatchesAgent ? voicePlayback?.lipSyncSource || 'audio_analyser+viseme_track' : ''}
        data-avatar-speaking={isActiveSpeaker ? '1' : '0'}
      />
    </Html>
  );
}

function ProceduralRig({
  agent,
  avatarState,
  voicePlayback,
  isActiveSpeaker,
  playbackMatchesAgent,
  color,
  track,
  bodyMotionPlan,
  phase,
}) {
  const rootRef = useRef();
  const torsoRef = useRef();
  const headRef = useRef();
  const jawRef = useRef();
  const mouthRef = useRef();
  const lowerLipRef = useRef();
  const leftEyeRef = useRef();
  const rightEyeRef = useRef();
  const browLeftRef = useRef();
  const browRightRef = useRef();
  const haloRef = useRef();
  const leftUpperArmRef = useRef();
  const leftLowerArmRef = useRef();
  const rightUpperArmRef = useRef();
  const rightLowerArmRef = useRef();
  const leftUpperLegRef = useRef();
  const rightUpperLegRef = useRef();

  useFrame(({ clock }) => {
    const state = rigState({
      agent,
      avatarState,
      voicePlayback,
      isActiveSpeaker,
      playbackMatchesAgent,
      track,
      bodyMotionPlan,
      phase,
      clock,
    });
    const motion = state.bodyMotion || {};
    const rootMotion = motion.root || { position: [0, 0, 0], rotation: [0, 0, 0] };
    const joints = motion.joints || {};

    if (rootRef.current) {
      rootRef.current.position.x = rootMotion.position?.[0] || 0;
      rootRef.current.position.y = -1.05 + (rootMotion.position?.[1] || 0) + (state.breath - 0.5) * 0.22;
      rootRef.current.position.z = rootMotion.position?.[2] || 0;
      rootRef.current.rotation.y = state.headSway.y + (rootMotion.rotation?.[1] || 0);
      rootRef.current.rotation.z = state.headSway.z + (rootMotion.rotation?.[2] || 0);
    }
    if (torsoRef.current) {
      torsoRef.current.scale.y = 1 + (state.breath - 0.5) * 0.035;
      torsoRef.current.rotation.x = joints.spine?.[0] || 0;
      torsoRef.current.rotation.y = joints.spine?.[1] || 0;
      torsoRef.current.rotation.z = joints.spine?.[2] || 0;
    }
    if (headRef.current) {
      headRef.current.rotation.x = state.headSway.x + (joints.head?.[0] || 0);
      headRef.current.rotation.y = state.headSway.y * 0.55 + (joints.head?.[1] || 0);
      headRef.current.rotation.z = joints.head?.[2] || 0;
      headRef.current.position.y = state.mouth * 0.025;
    }
    if (leftUpperArmRef.current) {
      leftUpperArmRef.current.rotation.set(
        -0.18 + (joints.leftUpperArm?.[0] || 0),
        joints.leftUpperArm?.[1] || 0,
        0.36 + (joints.leftUpperArm?.[2] || 0)
      );
    }
    if (rightUpperArmRef.current) {
      rightUpperArmRef.current.rotation.set(
        -0.18 + (joints.rightUpperArm?.[0] || 0),
        joints.rightUpperArm?.[1] || 0,
        -0.36 + (joints.rightUpperArm?.[2] || 0)
      );
    }
    if (leftLowerArmRef.current) {
      leftLowerArmRef.current.rotation.set(
        -0.1 + (joints.leftLowerArm?.[0] || 0),
        joints.leftLowerArm?.[1] || 0,
        joints.leftLowerArm?.[2] || 0
      );
    }
    if (rightLowerArmRef.current) {
      rightLowerArmRef.current.rotation.set(
        -0.1 + (joints.rightLowerArm?.[0] || 0),
        joints.rightLowerArm?.[1] || 0,
        joints.rightLowerArm?.[2] || 0
      );
    }
    if (leftUpperLegRef.current) {
      leftUpperLegRef.current.rotation.x = joints.leftUpperLeg?.[0] || 0;
    }
    if (rightUpperLegRef.current) {
      rightUpperLegRef.current.rotation.x = joints.rightUpperLeg?.[0] || 0;
    }
    if (jawRef.current) {
      jawRef.current.position.y = -state.mouth * 0.18;
      jawRef.current.rotation.x = -state.mouth * 0.22;
    }
    if (mouthRef.current) {
      const rounded = state.weights.ou + state.weights.oh;
      const wide = state.weights.ee + state.weights.ih * 0.55;
      mouthRef.current.scale.x = clamp(0.34 + wide * 0.18 - rounded * 0.08, 0.24, 0.52);
      mouthRef.current.scale.y = clamp(0.035 + state.mouth * 0.22 + state.weights.aa * 0.06, 0.035, 0.32);
      mouthRef.current.position.y = 2.88 - state.mouth * 0.075;
    }
    if (lowerLipRef.current) {
      lowerLipRef.current.position.y = 2.78 - state.mouth * 0.19;
    }
    if (leftEyeRef.current && rightEyeRef.current) {
      const eyeScale = clamp(1 - state.blink * 0.86, 0.08, 1);
      leftEyeRef.current.scale.y = 0.075 * eyeScale;
      rightEyeRef.current.scale.y = 0.075 * eyeScale;
    }
    if (browLeftRef.current && browRightRef.current) {
      const lift = state.speaking ? 0.04 + state.mouth * 0.08 : 0;
      browLeftRef.current.position.y = 3.45 + lift;
      browRightRef.current.position.y = 3.45 + lift;
    }
    if (haloRef.current) {
      haloRef.current.scale.setScalar(state.speaking ? 1.0 + Math.sin(clock.getElapsedTime() * 5) * 0.045 : 0.96);
      haloRef.current.material.opacity = state.speaking ? 0.32 : 0.14;
    }
  });

  return (
    <group ref={rootRef} position={[0, -1.05, 0]} scale={1.15}>
      <mesh ref={haloRef} position={[0, 3.15, -0.2]}>
        <ringGeometry args={[1.28, 1.42, 72]} />
        <meshBasicMaterial color={isActiveSpeaker ? '#f4c95d' : color} transparent opacity={0.16} />
      </mesh>

      <group ref={torsoRef}>
        <mesh position={[0, 1.25, 0]}>
          <capsuleGeometry args={[0.72, 1.18, 12, 28]} />
          <meshStandardMaterial color="#16233a" roughness={0.72} metalness={0.05} />
        </mesh>
        <mesh position={[0, 1.82, 0.12]} scale={[0.92, 0.38, 0.18]}>
          <sphereGeometry args={[1, 32, 16]} />
          <meshStandardMaterial color={color} roughness={0.5} emissive={color} emissiveIntensity={0.06} />
        </mesh>
        <mesh position={[0, 2.08, 0]}>
          <cylinderGeometry args={[0.28, 0.34, 0.42, 24]} />
          <meshStandardMaterial color="#b97857" roughness={0.62} />
        </mesh>
        <group ref={leftUpperArmRef} position={[-0.78, 1.75, 0.08]}>
          <mesh position={[0, -0.46, 0]} rotation={[0, 0, 0.08]}>
            <capsuleGeometry args={[0.105, 0.62, 8, 16]} />
            <meshStandardMaterial color="#b97857" roughness={0.62} />
          </mesh>
          <group ref={leftLowerArmRef} position={[0, -0.86, 0]}>
            <mesh position={[0, -0.36, 0]}>
              <capsuleGeometry args={[0.09, 0.52, 8, 16]} />
              <meshStandardMaterial color="#b97857" roughness={0.62} />
            </mesh>
          </group>
        </group>
        <group ref={rightUpperArmRef} position={[0.78, 1.75, 0.08]}>
          <mesh position={[0, -0.46, 0]} rotation={[0, 0, -0.08]}>
            <capsuleGeometry args={[0.105, 0.62, 8, 16]} />
            <meshStandardMaterial color="#b97857" roughness={0.62} />
          </mesh>
          <group ref={rightLowerArmRef} position={[0, -0.86, 0]}>
            <mesh position={[0, -0.36, 0]}>
              <capsuleGeometry args={[0.09, 0.52, 8, 16]} />
              <meshStandardMaterial color="#b97857" roughness={0.62} />
            </mesh>
          </group>
        </group>
        <group ref={leftUpperLegRef} position={[-0.31, 0.62, 0]}>
          <mesh position={[0, -0.45, 0]}>
            <capsuleGeometry args={[0.14, 0.72, 8, 16]} />
            <meshStandardMaterial color="#26385a" roughness={0.72} />
          </mesh>
        </group>
        <group ref={rightUpperLegRef} position={[0.31, 0.62, 0]}>
          <mesh position={[0, -0.45, 0]}>
            <capsuleGeometry args={[0.14, 0.72, 8, 16]} />
            <meshStandardMaterial color="#26385a" roughness={0.72} />
          </mesh>
        </group>
      </group>

      <group ref={headRef}>
        <mesh position={[0, 3.08, 0]}>
          <sphereGeometry args={[0.86, 48, 32]} />
          <meshStandardMaterial color="#c98a69" roughness={0.58} emissive="#3a140c" emissiveIntensity={0.03} />
        </mesh>
        <mesh position={[0, 3.48, -0.42]} scale={[0.9, 0.42, 0.42]}>
          <sphereGeometry args={[1, 36, 18]} />
          <meshStandardMaterial color="#161820" roughness={0.78} />
        </mesh>
        <mesh position={[-0.92, 3.08, 0.02]} rotation={[0, 0, 0.18]}>
          <sphereGeometry args={[0.16, 20, 12]} />
          <meshStandardMaterial color="#b97857" roughness={0.64} />
        </mesh>
        <mesh position={[0.92, 3.08, 0.02]} rotation={[0, 0, -0.18]}>
          <sphereGeometry args={[0.16, 20, 12]} />
          <meshStandardMaterial color="#b97857" roughness={0.64} />
        </mesh>

        <mesh ref={leftEyeRef} position={[-0.31, 3.21, 0.94]} scale={[0.13, 0.075, 0.035]}>
          <sphereGeometry args={[1, 24, 12]} />
          <meshStandardMaterial color="#f8fbff" roughness={0.35} />
        </mesh>
        <mesh ref={rightEyeRef} position={[0.31, 3.21, 0.94]} scale={[0.13, 0.075, 0.035]}>
          <sphereGeometry args={[1, 24, 12]} />
          <meshStandardMaterial color="#f8fbff" roughness={0.35} />
        </mesh>
        <mesh position={[-0.31, 3.2, 1.0]} scale={[0.05, 0.05, 0.018]}>
          <sphereGeometry args={[1, 16, 8]} />
          <meshStandardMaterial color="#07101e" roughness={0.2} />
        </mesh>
        <mesh position={[0.31, 3.2, 1.0]} scale={[0.05, 0.05, 0.018]}>
          <sphereGeometry args={[1, 16, 8]} />
          <meshStandardMaterial color="#07101e" roughness={0.2} />
        </mesh>
        <mesh ref={browLeftRef} position={[-0.31, 3.45, 0.96]} rotation={[0, 0, 0.12]} scale={[0.18, 0.025, 0.025]}>
          <boxGeometry args={[1, 1, 1]} />
          <meshStandardMaterial color="#10131b" roughness={0.7} />
        </mesh>
        <mesh ref={browRightRef} position={[0.31, 3.45, 0.96]} rotation={[0, 0, -0.12]} scale={[0.18, 0.025, 0.025]}>
          <boxGeometry args={[1, 1, 1]} />
          <meshStandardMaterial color="#10131b" roughness={0.7} />
        </mesh>
        <mesh position={[0, 3.02, 1.0]} rotation={[Math.PI / 2, 0, 0]} scale={[0.08, 0.12, 0.08]}>
          <coneGeometry args={[1, 1, 18]} />
          <meshStandardMaterial color="#b97857" roughness={0.66} />
        </mesh>

        <group ref={jawRef}>
          <mesh position={[0, 2.73, 0.29]} scale={[0.63, 0.28, 0.42]}>
            <sphereGeometry args={[1, 32, 14]} />
            <meshStandardMaterial color="#b97857" roughness={0.62} />
          </mesh>
          <mesh ref={lowerLipRef} position={[0, 2.78, 1.0]} scale={[0.34, 0.035, 0.035]}>
            <sphereGeometry args={[1, 24, 8]} />
            <meshStandardMaterial color="#a45255" roughness={0.5} />
          </mesh>
        </group>

        <mesh position={[0, 2.97, 1.01]} scale={[0.38, 0.045, 0.035]}>
          <sphereGeometry args={[1, 24, 8]} />
          <meshStandardMaterial color="#b15c62" roughness={0.5} />
        </mesh>
        <mesh ref={mouthRef} position={[0, 2.87, 1.03]} scale={[0.36, 0.22, 0.035]}>
          <sphereGeometry args={[1, 32, 16]} />
          <meshStandardMaterial color="#19070c" roughness={0.7} />
        </mesh>
      </group>
    </group>
  );
}

function LoadedVrmRig({
  vrmUrl,
  agent,
  avatarState,
  voicePlayback,
  isActiveSpeaker,
  playbackMatchesAgent,
  track,
  bodyMotionPlan,
  phase,
}) {
  const gltf = useLoader(GLTFLoader, vrmUrl, (loader) => {
    loader.register((parser) => new VRMLoaderPlugin(parser));
  });
  const vrm = gltf.userData.vrm;

  useEffect(() => {
    if (!vrm) return;
    VRMUtils.rotateVRM0(vrm);
    vrm.scene.traverse((object) => {
      object.frustumCulled = false;
    });
  }, [vrm]);

  useFrame(({ clock }, delta) => {
    if (!vrm) return;
    const state = rigState({
      agent,
      avatarState,
      voicePlayback,
      isActiveSpeaker,
      playbackMatchesAgent,
      track,
      bodyMotionPlan,
      phase,
      clock,
    });
    const motion = state.bodyMotion || {};
    const rootMotion = motion.root || { position: [0, 0, 0], rotation: [0, 0, 0] };
    const joints = motion.joints || {};
    const manager = vrm.expressionManager;
    if (manager) {
      for (const name of VRM_VISEMES) {
        manager.setValue(name, state.weights[name] || 0);
      }
      manager.setValue('blink', state.blink);
    }
    const head = vrm.humanoid?.getNormalizedBoneNode?.('head');
    if (head) {
      head.rotation.x = state.headSway.x + (joints.head?.[0] || 0);
      head.rotation.y = state.headSway.y + (joints.head?.[1] || 0);
      head.rotation.z = state.headSway.z + (joints.head?.[2] || 0);
    }
    for (const [boneName, rotation] of Object.entries({
      spine: joints.spine,
      chest: joints.chest,
      leftUpperArm: joints.leftUpperArm,
      leftLowerArm: joints.leftLowerArm,
      rightUpperArm: joints.rightUpperArm,
      rightLowerArm: joints.rightLowerArm,
      leftUpperLeg: joints.leftUpperLeg,
      rightUpperLeg: joints.rightUpperLeg,
    })) {
      const bone = vrm.humanoid?.getNormalizedBoneNode?.(boneName);
      if (bone && rotation) {
        bone.rotation.x = rotation[0] || 0;
        bone.rotation.y = rotation[1] || 0;
        bone.rotation.z = rotation[2] || 0;
      }
    }
    vrm.scene.position.x = rootMotion.position?.[0] || 0;
    vrm.scene.position.y = -1.35 + (rootMotion.position?.[1] || 0) + (state.breath - 0.5) * 0.12;
    vrm.scene.position.z = rootMotion.position?.[2] || 0;
    vrm.scene.rotation.y = rootMotion.rotation?.[1] || 0;
    vrm.update(delta);
  });

  return <primitive object={vrm.scene} position={[0, -1.35, 0]} scale={2.2} />;
}

export function ControlledAvatar({
  agent,
  avatarState,
  selected,
  speaking,
  vrmUrl,
  position,
  color = '#54c8ff',
  voicePlayback,
}) {
  const phase = useMemo(() => stablePhase(agent?.soul_id || agent?.current_name), [agent?.current_name, agent?.soul_id]);
  const playbackMatchesAgent = voiceMatchesAgent(agent, voicePlayback);
  const browserPlaybackActive = Boolean(!voicePlayback?.status || ['starting', 'playing'].includes(voicePlayback.status));
  const snapshotSpeakerActive = Boolean(
    avatarState?.speaker_soul_id &&
    agent?.soul_id === avatarState.speaker_soul_id &&
    avatarState?.speaking &&
    browserPlaybackActive
  );
  const isActiveSpeaker = Boolean(speaking || playbackMatchesAgent || snapshotSpeakerActive);
  const track = useMemo(
    () => buildAlphabetVisemeTrack(voicePlayback?.line || '', voicePlayback?.durationSeconds || 0),
    [voicePlayback?.durationSeconds, voicePlayback?.line, voicePlayback?.utteranceId]
  );
  const bodyMotionPlan = useMemo(
    () => resolveBodyMotionPlan(
      avatarState?.body_motion || avatarState?.plan?.body_motion || {},
      {
        agentId: agent?.soul_id || agent?.current_name || '',
        line: voicePlayback?.line || '',
        durationSeconds: voicePlayback?.durationSeconds || 0,
        speaking: isActiveSpeaker,
      }
    ),
    [
      avatarState?.body_motion,
      avatarState?.plan?.body_motion,
      agent?.current_name,
      agent?.soul_id,
      isActiveSpeaker,
      voicePlayback?.durationSeconds,
      voicePlayback?.line,
      voicePlayback?.utteranceId,
    ]
  );
  const kind = vrmUrl ? 'vrm-rig' : 'procedural-rig';
  const status = vrmUrl ? 'vrm-speech-controlled' : 'procedural-speech-controlled';
  const fallbackRig = (
    <ProceduralRig
      agent={agent}
      avatarState={avatarState}
      voicePlayback={voicePlayback}
      isActiveSpeaker={isActiveSpeaker}
      playbackMatchesAgent={playbackMatchesAgent}
      color={color}
      track={track}
      bodyMotionPlan={bodyMotionPlan}
      phase={phase}
    />
  );

  return (
    <group position={position || [0, 0, 0]}>
      <RigTelemetry
        kind={kind}
        status={status}
        isActiveSpeaker={isActiveSpeaker}
        playbackMatchesAgent={playbackMatchesAgent}
        voicePlayback={voicePlayback}
        bodyMotionPlan={bodyMotionPlan}
      />
      {vrmUrl ? (
        <RigErrorBoundary fallback={fallbackRig}>
          <Suspense fallback={fallbackRig}>
            <LoadedVrmRig
              vrmUrl={vrmUrl}
              agent={agent}
              avatarState={avatarState}
              voicePlayback={voicePlayback}
              isActiveSpeaker={isActiveSpeaker}
              playbackMatchesAgent={playbackMatchesAgent}
              track={track}
              bodyMotionPlan={bodyMotionPlan}
              phase={phase}
            />
          </Suspense>
        </RigErrorBoundary>
      ) : fallbackRig}
      <Text
        position={[0, -2.2, 0]}
        fontSize={0.22}
        color={isActiveSpeaker ? '#f4c95d' : (selected ? '#ffffff' : '#d6dcff')}
        anchorX="center"
        anchorY="middle"
        outlineWidth={0.01}
        outlineColor="#050712"
      >
        {agent?.current_name || agent?.soul_id?.slice(0, 8) || 'avatar'}
      </Text>
    </group>
  );
}
