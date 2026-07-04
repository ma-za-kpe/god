import React, { Suspense, useEffect, useMemo, useRef } from 'react';
import { Html, Text } from '@react-three/drei';
import { useFrame, useLoader } from '@react-three/fiber';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';
import { buildAlphabetVisemeTrack, sampleVisemeTrack, scaleVisemeSample, VRM_VISEMES } from '../lipSync';
import {
  resolveBodyMotionPlan,
  sampleBodyMotionPlan,
} from '../avatarMotion';

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

function avatarMotionPlan(agent, avatarState) {
  return (
    avatarState?.body_motion ||
    avatarState?.motion_plan ||
    avatarState?.control_plan ||
    avatarState?.plan?.body_motion ||
    agent?.body_motion ||
    agent?.avatar_control ||
    null
  );
}

function planStartedAtMs(plan, avatarState) {
  const raw =
    avatarState?.control_started_at_ms ??
    avatarState?.controlStartedAtMs ??
    plan?.started_at_ms ??
    plan?.startedAtMs;
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
}

function sampleAvatarMotion({ agent, avatarState, clock, phase, speaking }) {
  const rawPlan = avatarMotionPlan(agent, avatarState);
  const plan = resolveBodyMotionPlan(rawPlan || {}, {
    agentId: agent?.soul_id || '',
    action: avatarState?.control_label || avatarState?.controlLabel || 'stand',
    speaking,
    durationSeconds: Number(rawPlan?.duration_seconds || rawPlan?.durationSeconds || 4),
    allowFallback: false,
  });
  const duration = Math.max(0.25, Number(plan.durationSeconds || 4));
  const startedAtMs = planStartedAtMs(rawPlan || plan, avatarState);
  const elapsedSeconds = startedAtMs
    ? ((Math.max(0, Date.now() - startedAtMs) / 1000) % duration)
    : ((clock.getElapsedTime() + phase) % duration);
  const sample = sampleBodyMotionPlan(plan, elapsedSeconds);
  return { plan, sample, elapsedSeconds };
}

function addRotation(base = [0, 0, 0], extra = [0, 0, 0], weight = 1) {
  return [
    Number(base[0] || 0) + Number(extra[0] || 0) * weight,
    Number(base[1] || 0) + Number(extra[1] || 0) * weight,
    Number(base[2] || 0) + Number(extra[2] || 0) * weight,
  ];
}

function vector3(value, fallback = [0, 0, 0]) {
  return Array.isArray(value) && value.length === 3
    ? [
      Number(value[0] || 0),
      Number(value[1] || 0),
      Number(value[2] || 0),
    ]
    : [...fallback];
}

function setRotation(object, rotation = [0, 0, 0], base = [0, 0, 0]) {
  if (!object) return;
  object.rotation.set(
    Number(base[0] || 0) + Number(rotation[0] || 0),
    Number(base[1] || 0) + Number(rotation[1] || 0),
    Number(base[2] || 0) + Number(rotation[2] || 0)
  );
}

function applyVrmBone(vrm, name, rotation = [0, 0, 0], base = [0, 0, 0]) {
  const bone = vrm?.humanoid?.getNormalizedBoneNode?.(name);
  setRotation(bone, rotation, base);
}

function rigState({
  agent,
  avatarState,
  voicePlayback,
  isActiveSpeaker,
  playbackMatchesAgent,
  track,
  phase,
  clock,
}) {
  const life = avatarState?.life || {};
  const localControlMode = Boolean(
    avatarState?.control_mode === 'llm-avatar-control' ||
    avatarState?.controlMode === 'llm-avatar-control' ||
    avatarMotionPlan(agent, avatarState)
  );
  const elapsed = playbackMatchesAgent && voicePlayback?.startedAtMs
    ? Math.max(0, (nowMs() - voicePlayback.startedAtMs) / 1000)
    : (clock.getElapsedTime() + phase) % Math.max(3.8, Number(voicePlayback?.durationSeconds || 0) || 3.8);
  const snapshotMouth = lifeNumber(life, 'mouth_amplitude');
  const playbackMouth = playbackMatchesAgent ? Number(voicePlayback?.mouthAmplitude || 0) : Number.NaN;
  const baseAmplitude = isActiveSpeaker && !localControlMode
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
  const syllablePulse = isActiveSpeaker && !localControlMode ? 0.82 + Math.abs(Math.sin(clock.getElapsedTime() * 17 + phase)) * 0.18 : 0;
  const sample = localControlMode
    ? scaleVisemeSample(sampleVisemeTrack([], elapsed), 0)
    : scaleVisemeSample(sampleVisemeTrack(track, elapsed), clamp(baseAmplitude * syllablePulse + 0.12, 0, 1));
  const localBreath = localControlMode ? 0.5 : 0.5 + 0.5 * Math.sin(clock.getElapsedTime() * 2.1 + phase);
  const snapshotBreath = lifeNumber(life, 'breathing_phase');
  const breath = localControlMode
    ? 0.5
    : Number.isFinite(snapshotBreath)
    ? clamp(snapshotBreath * 0.7 + localBreath * 0.3, 0, 1)
    : localBreath;
  const headSway = localControlMode
    ? { x: 0, y: 0, z: 0 }
    : {
      x: Math.sin(clock.getElapsedTime() * 0.8 + phase) * (isActiveSpeaker ? 0.05 : 0.028),
      y: Math.sin(clock.getElapsedTime() * 0.65 + phase) * (isActiveSpeaker ? 0.12 : 0.055),
      z: Math.sin(clock.getElapsedTime() * 1.25 + phase) * (isActiveSpeaker ? 0.035 : 0.018),
    };
  const blink = localControlMode
    ? 0
    : clamp(Math.pow(Math.max(0, Math.sin(clock.getElapsedTime() * 0.74 + phase) - 0.9) * 10, 2), 0, 1);
  const motion = sampleAvatarMotion({ agent, avatarState, clock, phase, speaking: isActiveSpeaker });
  const motionSample = motion.sample || {};
  const motionJoints = motionSample.joints || {};
  const motionExpression = motionSample.expression || {};
  const localMouth = clamp(
    Math.max(
      sample.jaw + baseAmplitude * 0.38,
      Number(motionExpression.mouthOpen || 0)
    ),
    0,
    1
  );
  const expressionSmile = clamp(Number(motionExpression.smile || 0), 0, 1);
  const expressionSurprise = clamp(Number(motionExpression.surprise || 0), 0, 1);
  const expressionFocus = clamp(Number(motionExpression.focus || 0), 0, 1);

  return {
    ...sample,
    agentName: agent?.current_name || agent?.soul_id || '',
    breath,
    headSway: {
      x: headSway.x + Number(motionJoints.head?.[0] || 0),
      y: headSway.y + Number(motionJoints.head?.[1] || 0),
      z: headSway.z + Number(motionJoints.head?.[2] || 0),
    },
    blink: clamp(blink + expressionFocus * 0.08, 0, 1),
    speaking: isActiveSpeaker,
    mouth: localMouth,
    motion: motionSample,
    joints: {
      spine: addRotation([0, 0, 0], motionJoints.spine),
      chest: addRotation([0, 0, 0], motionJoints.chest),
      neck: addRotation([0, 0, 0], motionJoints.neck),
      head: addRotation([0, 0, 0], motionJoints.head),
      leftUpperArm: addRotation([0, 0, 0], motionJoints.leftUpperArm),
      leftLowerArm: addRotation([0, 0, 0], motionJoints.leftLowerArm),
      rightUpperArm: addRotation([0, 0, 0], motionJoints.rightUpperArm),
      rightLowerArm: addRotation([0, 0, 0], motionJoints.rightLowerArm),
      leftUpperLeg: addRotation([0, 0, 0], motionJoints.leftUpperLeg),
      leftLowerLeg: addRotation([0, 0, 0], motionJoints.leftLowerLeg),
      rightUpperLeg: addRotation([0, 0, 0], motionJoints.rightUpperLeg),
      rightLowerLeg: addRotation([0, 0, 0], motionJoints.rightLowerLeg),
    },
    expression: {
      smile: expressionSmile,
      surprise: expressionSurprise,
      focus: expressionFocus,
      mouthOpen: localMouth,
    },
    controlLabel: motion.plan?.controlLabel || motionSample.gestureLabel || avatarState?.control_label || 'stand',
    controlProvider: motion.plan?.provider || 'none',
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
  controlLabel,
  controlProvider,
  controlActive,
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
        data-avatar-control-mode="llm-avatar-control"
        data-avatar-control-active={controlActive ? '1' : '0'}
        data-avatar-motion-label={controlLabel || ''}
        data-avatar-control-provider={controlProvider || ''}
        data-avatar-local-audio-mode="disabled"
        data-avatar-video-mode="disabled-for-one"
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
  phase,
}) {
  const rootRef = useRef();
  const torsoRef = useRef();
  const chestRef = useRef();
  const neckRef = useRef();
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
  const leftLowerLegRef = useRef();
  const rightUpperLegRef = useRef();
  const rightLowerLegRef = useRef();
  const localControlMode = Boolean(
    avatarState?.control_mode === 'llm-avatar-control' ||
    avatarState?.controlMode === 'llm-avatar-control' ||
    avatarMotionPlan(agent, avatarState)
  );
  const avatarScale = localControlMode ? 0.52 : 1.15;
  const rootBaseY = localControlMode ? -1.72 : -1.05;

  useFrame(({ clock }) => {
    const state = rigState({
      agent,
      avatarState,
      voicePlayback,
      isActiveSpeaker,
      playbackMatchesAgent,
      track,
      phase,
      clock,
    });
    const root = state.motion?.root || {};
    const rootPosition = vector3(root.position);
    const rootRotation = vector3(root.rotation);
    const smile = Number(state.expression?.smile || 0);
    const surprise = Number(state.expression?.surprise || 0);
    const focus = Number(state.expression?.focus || 0);

    if (rootRef.current) {
      rootRef.current.position.set(
        rootPosition[0],
        rootBaseY + rootPosition[1] + (state.breath - 0.5) * 0.22,
        rootPosition[2]
      );
      rootRef.current.rotation.set(rootRotation[0], rootRotation[1], rootRotation[2] + state.headSway.z * 0.18);
    }
    if (torsoRef.current) {
      torsoRef.current.scale.y = 1 + (state.breath - 0.5) * 0.035;
      setRotation(torsoRef.current, state.joints.spine);
    }
    if (chestRef.current) {
      setRotation(chestRef.current, state.joints.chest);
    }
    if (neckRef.current) {
      setRotation(neckRef.current, state.joints.neck);
    }
    if (headRef.current) {
      headRef.current.rotation.x = state.headSway.x;
      headRef.current.rotation.y = state.headSway.y * 0.55;
      headRef.current.position.y = state.mouth * 0.025;
    }
    if (jawRef.current) {
      jawRef.current.position.y = -state.mouth * 0.18;
      jawRef.current.rotation.x = -state.mouth * 0.22;
    }
    if (mouthRef.current) {
      const rounded = state.weights.ou + state.weights.oh;
      const wide = state.weights.ee + state.weights.ih * 0.55;
      mouthRef.current.scale.x = clamp(0.34 + wide * 0.18 - rounded * 0.08 + smile * 0.14 - surprise * 0.04, 0.24, 0.62);
      mouthRef.current.scale.y = clamp(0.035 + state.mouth * 0.22 + state.weights.aa * 0.06 + surprise * 0.08, 0.035, 0.4);
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
      const lift = (state.speaking ? 0.04 + state.mouth * 0.08 : 0) + surprise * 0.12 - focus * 0.04;
      browLeftRef.current.position.y = 3.45 + lift;
      browRightRef.current.position.y = 3.45 + lift;
      browLeftRef.current.rotation.z = 0.12 + focus * 0.16 - surprise * 0.1;
      browRightRef.current.rotation.z = -0.12 - focus * 0.16 + surprise * 0.1;
    }
    if (haloRef.current) {
      haloRef.current.scale.setScalar(state.speaking ? 1.0 + Math.sin(clock.getElapsedTime() * 5) * 0.045 : 0.96);
      haloRef.current.material.opacity = state.speaking ? 0.32 : 0.14;
    }
    setRotation(leftUpperArmRef.current, state.joints.leftUpperArm, [0, 0, 0.16]);
    setRotation(leftLowerArmRef.current, state.joints.leftLowerArm);
    setRotation(rightUpperArmRef.current, state.joints.rightUpperArm, [0, 0, -0.16]);
    setRotation(rightLowerArmRef.current, state.joints.rightLowerArm);
    setRotation(leftUpperLegRef.current, state.joints.leftUpperLeg, [0, 0, 0.04]);
    setRotation(leftLowerLegRef.current, state.joints.leftLowerLeg);
    setRotation(rightUpperLegRef.current, state.joints.rightUpperLeg, [0, 0, -0.04]);
    setRotation(rightLowerLegRef.current, state.joints.rightLowerLeg);
  });

  return (
    <group ref={rootRef} position={[0, rootBaseY, 0]} scale={avatarScale}>
      <mesh ref={haloRef} position={[0, 3.15, -0.2]}>
        <ringGeometry args={[1.28, 1.42, 72]} />
        <meshBasicMaterial color={isActiveSpeaker ? '#f4c95d' : color} transparent opacity={0.16} />
      </mesh>

      <group ref={torsoRef}>
        <mesh position={[0, 1.25, 0]}>
          <capsuleGeometry args={[0.72, 1.18, 12, 28]} />
          <meshStandardMaterial color="#16233a" roughness={0.72} metalness={0.05} />
        </mesh>
        <group ref={chestRef}>
          <mesh position={[0, 1.82, 0.12]} scale={[0.92, 0.38, 0.18]}>
            <sphereGeometry args={[1, 32, 16]} />
            <meshStandardMaterial color={color} roughness={0.5} emissive={color} emissiveIntensity={0.06} />
          </mesh>
          <group ref={neckRef}>
            <mesh position={[0, 2.08, 0]}>
              <cylinderGeometry args={[0.28, 0.34, 0.42, 24]} />
              <meshStandardMaterial color="#b97857" roughness={0.62} />
            </mesh>
          </group>
        </group>
      </group>

      <group ref={leftUpperArmRef} position={[-0.78, 1.88, 0.02]}>
        <mesh position={[0, -0.42, 0]}>
          <capsuleGeometry args={[0.16, 0.68, 10, 16]} />
          <meshStandardMaterial color="#b97857" roughness={0.66} />
        </mesh>
        <group ref={leftLowerArmRef} position={[0, -0.82, 0]}>
          <mesh position={[0, -0.34, 0]}>
            <capsuleGeometry args={[0.14, 0.58, 10, 16]} />
            <meshStandardMaterial color="#c98a69" roughness={0.62} />
          </mesh>
          <mesh position={[0, -0.72, 0.04]} scale={[0.16, 0.12, 0.16]}>
            <sphereGeometry args={[1, 16, 10]} />
            <meshStandardMaterial color="#c98a69" roughness={0.62} />
          </mesh>
        </group>
      </group>

      <group ref={rightUpperArmRef} position={[0.78, 1.88, 0.02]}>
        <mesh position={[0, -0.42, 0]}>
          <capsuleGeometry args={[0.16, 0.68, 10, 16]} />
          <meshStandardMaterial color="#b97857" roughness={0.66} />
        </mesh>
        <group ref={rightLowerArmRef} position={[0, -0.82, 0]}>
          <mesh position={[0, -0.34, 0]}>
            <capsuleGeometry args={[0.14, 0.58, 10, 16]} />
            <meshStandardMaterial color="#c98a69" roughness={0.62} />
          </mesh>
          <mesh position={[0, -0.72, 0.04]} scale={[0.16, 0.12, 0.16]}>
            <sphereGeometry args={[1, 16, 10]} />
            <meshStandardMaterial color="#c98a69" roughness={0.62} />
          </mesh>
        </group>
      </group>

      <group ref={leftUpperLegRef} position={[-0.34, 0.72, 0]}>
        <mesh position={[0, -0.5, 0]}>
          <capsuleGeometry args={[0.2, 0.86, 10, 18]} />
          <meshStandardMaterial color="#273a62" roughness={0.72} />
        </mesh>
        <group ref={leftLowerLegRef} position={[0, -0.98, 0]}>
          <mesh position={[0, -0.42, 0]}>
            <capsuleGeometry args={[0.16, 0.78, 10, 18]} />
            <meshStandardMaterial color="#1f3157" roughness={0.76} />
          </mesh>
          <mesh position={[0, -0.86, 0.12]} scale={[0.26, 0.08, 0.42]}>
            <boxGeometry args={[1, 1, 1]} />
            <meshStandardMaterial color="#10131b" roughness={0.7} />
          </mesh>
        </group>
      </group>

      <group ref={rightUpperLegRef} position={[0.34, 0.72, 0]}>
        <mesh position={[0, -0.5, 0]}>
          <capsuleGeometry args={[0.2, 0.86, 10, 18]} />
          <meshStandardMaterial color="#273a62" roughness={0.72} />
        </mesh>
        <group ref={rightLowerLegRef} position={[0, -0.98, 0]}>
          <mesh position={[0, -0.42, 0]}>
            <capsuleGeometry args={[0.16, 0.78, 10, 18]} />
            <meshStandardMaterial color="#1f3157" roughness={0.76} />
          </mesh>
          <mesh position={[0, -0.86, 0.12]} scale={[0.26, 0.08, 0.42]}>
            <boxGeometry args={[1, 1, 1]} />
            <meshStandardMaterial color="#10131b" roughness={0.7} />
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
  phase,
}) {
  const gltf = useLoader(GLTFLoader, vrmUrl, (loader) => {
    loader.register((parser) => new VRMLoaderPlugin(parser));
  });
  const vrm = gltf.userData.vrm;

  const localControlMode = Boolean(
    avatarState?.control_mode === 'llm-avatar-control' ||
    avatarState?.controlMode === 'llm-avatar-control' ||
    avatarMotionPlan(agent, avatarState)
  );
  const vrmScale = localControlMode ? 0.92 : 2.2;
  const vrmBaseY = localControlMode ? -1.98 : -1.35;

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
      phase,
      clock,
    });
    const manager = vrm.expressionManager;
    if (manager) {
      for (const name of VRM_VISEMES) {
        manager.setValue(name, state.weights[name] || 0);
      }
      manager.setValue('blink', state.blink);
      manager.setValue('happy', Number(state.expression?.smile || 0));
      manager.setValue('surprised', Number(state.expression?.surprise || 0));
      manager.setValue('relaxed', Number(state.expression?.smile || 0) * 0.18);
    }
    applyVrmBone(vrm, 'spine', state.joints.spine);
    applyVrmBone(vrm, 'chest', state.joints.chest);
    applyVrmBone(vrm, 'neck', state.joints.neck);
    applyVrmBone(vrm, 'head', [state.headSway.x, state.headSway.y, state.headSway.z]);
    applyVrmBone(vrm, 'leftUpperArm', state.joints.leftUpperArm);
    applyVrmBone(vrm, 'leftLowerArm', state.joints.leftLowerArm);
    applyVrmBone(vrm, 'rightUpperArm', state.joints.rightUpperArm);
    applyVrmBone(vrm, 'rightLowerArm', state.joints.rightLowerArm);
    applyVrmBone(vrm, 'leftUpperLeg', state.joints.leftUpperLeg);
    applyVrmBone(vrm, 'leftLowerLeg', state.joints.leftLowerLeg);
    applyVrmBone(vrm, 'rightUpperLeg', state.joints.rightUpperLeg);
    applyVrmBone(vrm, 'rightLowerLeg', state.joints.rightLowerLeg);
    const root = state.motion?.root || {};
    const rootPosition = vector3(root.position);
    const rootRotation = vector3(root.rotation);
    vrm.scene.position.set(rootPosition[0], vrmBaseY + rootPosition[1] + (state.breath - 0.5) * 0.12, rootPosition[2]);
    vrm.scene.rotation.set(rootRotation[0], rootRotation[1], rootRotation[2]);
    vrm.update(delta);
  });

  return <primitive object={vrm.scene} scale={vrmScale} />;
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
  const controlPlan = avatarMotionPlan(agent, avatarState);
  const controlActive = Boolean(
    controlPlan ||
    avatarState?.control_mode === 'llm-avatar-control' ||
    avatarState?.controlMode === 'llm-avatar-control'
  );
  const controlLabel =
    avatarState?.control_label ||
    avatarState?.controlLabel ||
    controlPlan?.control_label ||
    controlPlan?.controlLabel ||
    (controlActive ? 'direct-control' : 'stand');
  const controlProvider =
    avatarState?.control_provider ||
    avatarState?.controlProvider ||
    controlPlan?.provider ||
    'none';
  const browserPlaybackActive = Boolean(!voicePlayback?.status || ['starting', 'playing'].includes(voicePlayback.status));
  const snapshotSpeakerActive = Boolean(
    avatarState?.speaker_soul_id &&
    agent?.soul_id === avatarState.speaker_soul_id &&
    avatarState?.speaking &&
    browserPlaybackActive
  );
  const isActiveSpeaker = Boolean(controlActive || speaking || playbackMatchesAgent || snapshotSpeakerActive);
  const track = useMemo(
    () => (controlActive || !voicePlayback?.line
      ? []
      : buildAlphabetVisemeTrack(voicePlayback.line, voicePlayback?.durationSeconds || 0)),
    [controlActive, voicePlayback?.durationSeconds, voicePlayback?.line, voicePlayback?.utteranceId]
  );
  const kind = vrmUrl ? 'vrm-rig' : 'procedural-rig';
  const status = vrmUrl ? 'vrm-command-controlled' : 'procedural-command-controlled';
  const fallbackRig = (
    <ProceduralRig
      agent={agent}
      avatarState={avatarState}
      voicePlayback={voicePlayback}
      isActiveSpeaker={isActiveSpeaker}
      playbackMatchesAgent={playbackMatchesAgent}
      color={color}
      track={track}
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
        controlLabel={controlLabel}
        controlProvider={controlProvider}
        controlActive={controlActive}
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
