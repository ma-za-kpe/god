import React, { Suspense, useEffect, useMemo, useRef } from 'react';
import { Html, Text } from '@react-three/drei';
import { useFrame, useLoader } from '@react-three/fiber';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';
import { buildAlphabetVisemeTrack, sampleVisemeTrack, scaleVisemeSample, VRM_VISEMES } from '../lipSync';
import { normalizeAvatarIntent } from '../avatarIntent';

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

function rigState({
  agent,
  avatarState,
  voicePlayback,
  avatarIntent,
  isActiveSpeaker,
  playbackMatchesAgent,
  track,
  phase,
  clock,
}) {
  const intent = normalizeAvatarIntent(avatarIntent || avatarState?.avatar_intent || { voice: { line: voicePlayback?.line || '' } });
  const life = avatarState?.life || {};
  const elapsed = playbackMatchesAgent && voicePlayback?.startedAtMs
    ? Math.max(0, (nowMs() - voicePlayback.startedAtMs) / 1000)
    : (clock.getElapsedTime() + phase) % Math.max(3.8, Number(voicePlayback?.durationSeconds || 0) || 3.8);
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
  const gazeY = intent.gaze === 'left' ? 0.26 : intent.gaze === 'right' ? -0.26 : 0;
  const gazeX = intent.gaze === 'down' ? 0.16 : 0;
  const gestureBeat = Math.sin(clock.getElapsedTime() * 4.2 * intent.tempo + phase);
  const blink = clamp(Math.pow(Math.max(0, Math.sin(clock.getElapsedTime() * 0.74 + phase) - 0.9) * 10, 2), 0, 1);

  return {
    ...sample,
    agentName: agent?.current_name || agent?.soul_id || '',
    intent,
    breath,
    headSway: {
      x: headSway.x + gazeX + intent.face.brow * 0.025,
      y: headSway.y + gazeY,
      z: headSway.z,
    },
    gestureBeat,
    blink,
    speaking: isActiveSpeaker,
    mouth: clamp(sample.jaw + baseAmplitude * 0.38 + intent.face.smile * 0.035, 0, 1),
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
  avatarIntent,
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
        data-voice-playback-status={playbackMatchesAgent ? voicePlayback?.status || '' : ''}
        data-voice-mouth-amplitude={playbackMatchesAgent ? Number(voicePlayback?.mouthAmplitude || 0).toFixed(4) : '0.0000'}
        data-voice-lip-sync-source={playbackMatchesAgent ? voicePlayback?.lipSyncSource || 'audio_analyser+viseme_track' : ''}
        data-avatar-speaking={isActiveSpeaker ? '1' : '0'}
        data-avatar-intent-mood={avatarIntent?.mood || ''}
        data-avatar-intent-gesture={avatarIntent?.gesture || ''}
        data-avatar-intent-gaze={avatarIntent?.gaze || ''}
        data-avatar-hair-bend={Number(avatarIntent?.hair?.bend || 0).toFixed(3)}
        data-avatar-left-finger-curl={Number(avatarIntent?.hands?.leftFingerCurl || 0).toFixed(3)}
        data-avatar-right-finger-curl={Number(avatarIntent?.hands?.rightFingerCurl || 0).toFixed(3)}
      />
    </Html>
  );
}

function ProceduralRig({
  agent,
  avatarState,
  voicePlayback,
  avatarIntent,
  isActiveSpeaker,
  playbackMatchesAgent,
  color,
  track,
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
  const hairFrontRef = useRef();
  const hairLeftRef = useRef();
  const hairRightRef = useRef();
  const leftArmRef = useRef();
  const rightArmRef = useRef();
  const leftHandRef = useRef();
  const rightHandRef = useRef();
  const leftFingerRefs = useRef([]);
  const rightFingerRefs = useRef([]);

  useFrame(({ clock }) => {
    const state = rigState({
      agent,
      avatarState,
      voicePlayback,
      avatarIntent,
      isActiveSpeaker,
      playbackMatchesAgent,
      track,
      phase,
      clock,
    });

    if (rootRef.current) {
      rootRef.current.position.y = -1.05 + (state.breath - 0.5) * 0.22;
      rootRef.current.rotation.y = state.headSway.y;
      rootRef.current.rotation.z = state.headSway.z;
    }
    if (torsoRef.current) {
      torsoRef.current.scale.y = 1 + (state.breath - 0.5) * 0.035;
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
      mouthRef.current.scale.x = clamp(0.34 + wide * 0.18 - rounded * 0.08 + state.intent.face.smile * 0.16, 0.24, 0.62);
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
      const lift = (state.speaking ? 0.04 + state.mouth * 0.08 : 0) + state.intent.face.brow * 0.12;
      browLeftRef.current.position.y = 3.45 + lift;
      browRightRef.current.position.y = 3.45 + lift;
      browLeftRef.current.rotation.z = 0.12 - state.intent.face.brow * 0.18;
      browRightRef.current.rotation.z = -0.12 + state.intent.face.brow * 0.18;
    }
    if (haloRef.current) {
      haloRef.current.scale.setScalar(state.speaking ? 1.0 + Math.sin(clock.getElapsedTime() * 5) * 0.045 : 0.96);
      haloRef.current.material.opacity = state.speaking ? 0.32 : 0.14;
    }
    const hairMotion = state.intent.hair.bend * 0.32 + Math.sin(clock.getElapsedTime() * 2.9 + phase) * state.intent.hair.sway * 0.18;
    if (hairFrontRef.current) hairFrontRef.current.rotation.x = hairMotion;
    if (hairLeftRef.current) hairLeftRef.current.rotation.z = -0.32 + hairMotion;
    if (hairRightRef.current) hairRightRef.current.rotation.z = 0.32 + hairMotion;

    const gesture = state.intent.gesture;
    const wave = gesture === 'wave' ? state.gestureBeat * 0.65 : 0;
    const point = gesture === 'point' ? 0.95 : 0;
    const thinking = gesture === 'thinking' ? 0.85 : 0;
    const openPalm = state.intent.hands.openPalm;
    if (leftArmRef.current) {
      leftArmRef.current.rotation.z = 0.48 - openPalm * 0.34 + thinking * 0.65;
      leftArmRef.current.rotation.x = -0.1 - thinking * 0.5;
    }
    if (rightArmRef.current) {
      rightArmRef.current.rotation.z = -0.48 + point * 0.64 - wave * 0.42;
      rightArmRef.current.rotation.x = -0.08 - point * 0.55;
    }
    if (leftHandRef.current) {
      leftHandRef.current.rotation.z = thinking * 0.35;
      leftHandRef.current.position.y = thinking ? 2.48 : 1.28;
      leftHandRef.current.position.x = thinking ? -0.42 : -0.98;
    }
    if (rightHandRef.current) {
      rightHandRef.current.rotation.z = wave;
    }
    leftFingerRefs.current.forEach((finger, index) => {
      if (!finger) return;
      finger.rotation.x = -state.intent.hands.leftFingerCurl * (0.45 + index * 0.14) - thinking * 0.32;
      finger.rotation.z = openPalm * (index - 1.5) * 0.04;
    });
    rightFingerRefs.current.forEach((finger, index) => {
      if (!finger) return;
      const pointingFinger = point && index === 1;
      finger.rotation.x = pointingFinger ? -0.04 : -state.intent.hands.rightFingerCurl * (0.45 + index * 0.14);
      finger.rotation.z = wave * 0.16 + openPalm * (index - 1.5) * 0.04;
    });
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
        <mesh ref={hairFrontRef} position={[0, 3.58, 0.24]} scale={[0.62, 0.22, 0.16]}>
          <capsuleGeometry args={[0.18, 0.42, 8, 16]} />
          <meshStandardMaterial color="#12151d" roughness={0.78} />
        </mesh>
        <mesh ref={hairLeftRef} position={[-0.48, 3.38, 0.08]} scale={[0.2, 0.52, 0.16]}>
          <capsuleGeometry args={[0.18, 0.62, 8, 16]} />
          <meshStandardMaterial color="#12151d" roughness={0.78} />
        </mesh>
        <mesh ref={hairRightRef} position={[0.48, 3.38, 0.08]} scale={[0.2, 0.52, 0.16]}>
          <capsuleGeometry args={[0.18, 0.62, 8, 16]} />
          <meshStandardMaterial color="#12151d" roughness={0.78} />
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

      <group ref={leftArmRef} position={[-0.74, 1.82, 0.08]} rotation={[0, 0, 0.42]}>
        <mesh position={[-0.1, -0.42, 0]} scale={[0.12, 0.48, 0.12]}>
          <capsuleGeometry args={[0.32, 0.72, 8, 16]} />
          <meshStandardMaterial color="#b97857" roughness={0.64} />
        </mesh>
      </group>
      <group ref={rightArmRef} position={[0.74, 1.82, 0.08]} rotation={[0, 0, -0.42]}>
        <mesh position={[0.1, -0.42, 0]} scale={[0.12, 0.48, 0.12]}>
          <capsuleGeometry args={[0.32, 0.72, 8, 16]} />
          <meshStandardMaterial color="#b97857" roughness={0.64} />
        </mesh>
      </group>
      <group ref={leftHandRef} position={[-0.98, 1.28, 0.14]}>
        <mesh scale={[0.16, 0.13, 0.08]}>
          <sphereGeometry args={[1, 18, 10]} />
          <meshStandardMaterial color="#b97857" roughness={0.62} />
        </mesh>
        {[0, 1, 2, 3].map((index) => (
          <group key={`left-finger-${index}`} ref={(node) => { leftFingerRefs.current[index] = node; }} position={[-0.08 + index * 0.052, -0.11, 0.02]}>
            <mesh position={[0, -0.06, 0]} scale={[0.018, 0.09, 0.018]}>
              <capsuleGeometry args={[0.7, 0.9, 6, 8]} />
              <meshStandardMaterial color="#c98a69" roughness={0.62} />
            </mesh>
          </group>
        ))}
      </group>
      <group ref={rightHandRef} position={[0.98, 1.28, 0.14]}>
        <mesh scale={[0.16, 0.13, 0.08]}>
          <sphereGeometry args={[1, 18, 10]} />
          <meshStandardMaterial color="#b97857" roughness={0.62} />
        </mesh>
        {[0, 1, 2, 3].map((index) => (
          <group key={`right-finger-${index}`} ref={(node) => { rightFingerRefs.current[index] = node; }} position={[-0.08 + index * 0.052, -0.11, 0.02]}>
            <mesh position={[0, -0.06, 0]} scale={[0.018, 0.09, 0.018]}>
              <capsuleGeometry args={[0.7, 0.9, 6, 8]} />
              <meshStandardMaterial color="#c98a69" roughness={0.62} />
            </mesh>
          </group>
        ))}
      </group>
    </group>
  );
}

function LoadedVrmRig({
  vrmUrl,
  agent,
  avatarState,
  voicePlayback,
  avatarIntent,
  isActiveSpeaker,
  playbackMatchesAgent,
  track,
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
      avatarIntent,
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
      manager.setValue('happy', state.intent.face.smile);
      manager.setValue('angry', state.intent.mood === 'angry' ? 0.65 : 0);
    }
    const head = vrm.humanoid?.getNormalizedBoneNode?.('head');
    if (head) {
      head.rotation.x = state.headSway.x;
      head.rotation.y = state.headSway.y;
      head.rotation.z = state.headSway.z;
    }
    const leftUpperArm = vrm.humanoid?.getNormalizedBoneNode?.('leftUpperArm');
    const rightUpperArm = vrm.humanoid?.getNormalizedBoneNode?.('rightUpperArm');
    const leftHand = vrm.humanoid?.getNormalizedBoneNode?.('leftHand');
    const rightHand = vrm.humanoid?.getNormalizedBoneNode?.('rightHand');
    if (leftUpperArm) leftUpperArm.rotation.z = 0.45 - state.intent.hands.openPalm * 0.28;
    if (rightUpperArm) rightUpperArm.rotation.z = -0.45 + (state.intent.gesture === 'point' ? 0.55 : 0);
    if (leftHand) leftHand.rotation.x = -state.intent.hands.leftFingerCurl * 0.35;
    if (rightHand) rightHand.rotation.x = -state.intent.hands.rightFingerCurl * 0.35 + (state.intent.gesture === 'wave' ? state.gestureBeat * 0.4 : 0);
    vrm.scene.position.y = -1.35 + (state.breath - 0.5) * 0.12;
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
  avatarIntent,
}) {
  const normalizedIntent = useMemo(
    () => normalizeAvatarIntent(avatarIntent || avatarState?.avatar_intent || { voice: { line: voicePlayback?.line || '' } }),
    [avatarIntent, avatarState?.avatar_intent, voicePlayback?.line]
  );
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
  const kind = vrmUrl ? 'vrm-rig' : 'procedural-rig';
  const status = vrmUrl ? 'vrm-speech-controlled' : 'procedural-speech-controlled';
  const fallbackRig = (
    <ProceduralRig
      agent={agent}
      avatarState={avatarState}
      voicePlayback={voicePlayback}
      avatarIntent={normalizedIntent}
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
        avatarIntent={normalizedIntent}
      />
      {vrmUrl ? (
        <RigErrorBoundary fallback={fallbackRig}>
          <Suspense fallback={fallbackRig}>
            <LoadedVrmRig
              vrmUrl={vrmUrl}
              agent={agent}
              avatarState={avatarState}
              voicePlayback={voicePlayback}
              avatarIntent={normalizedIntent}
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
