import test from 'node:test';
import assert from 'node:assert/strict';

import { compileAvatarIntentNodes } from '../src/avatarNodeCompiler.js';
import {
  applyTalkingHeadBeat,
  applyTalkingHeadFrame,
  buildTalkingHeadNodeRegistry,
} from '../src/talkingHeadAdapter.js';

function propMap(ids) {
  return Object.fromEntries(ids.map((id) => [`${id}.quaternion`, {}]));
}

function fakeHead() {
  const calls = [];
  const poseProps = propMap([
    'Hips',
    'Spine',
    'Spine1',
    'Spine2',
    'Neck',
    'Head',
    'LeftShoulder',
    'LeftArm',
    'LeftForeArm',
    'LeftHand',
    'RightShoulder',
    'RightArm',
    'RightForeArm',
    'RightHand',
    'LeftUpLeg',
    'RightUpLeg',
    'LeftLeg',
    'RightLeg',
    'LeftHandThumb1',
    'LeftHandThumb2',
    'LeftHandThumb3',
    'LeftHandIndex1',
    'LeftHandIndex2',
    'LeftHandIndex3',
    'LeftHandMiddle1',
    'LeftHandMiddle2',
    'LeftHandMiddle3',
    'LeftHandRing1',
    'LeftHandRing2',
    'LeftHandRing3',
    'LeftHandPinky1',
    'LeftHandPinky2',
    'LeftHandPinky3',
    'RightHandThumb1',
    'RightHandThumb2',
    'RightHandThumb3',
    'RightHandIndex1',
    'RightHandIndex2',
    'RightHandIndex3',
    'RightHandMiddle1',
    'RightHandMiddle2',
    'RightHandMiddle3',
    'RightHandRing1',
    'RightHandRing2',
    'RightHandRing3',
    'RightHandPinky1',
    'RightHandPinky2',
    'RightHandPinky3',
  ]);
  return {
    calls,
    gestureTemplates: {},
    mtAvatar: {
      handFistLeft: {},
      handFistRight: {},
      bodyRotateX: {},
      bodyRotateY: {},
      bodyRotateZ: {},
      headRotateX: {},
      headRotateZ: {},
      chestInhale: {},
    },
    mtCustoms: ['handFistLeft', 'handFistRight', 'bodyRotateX', 'bodyRotateY', 'bodyRotateZ', 'headRotateX', 'headRotateZ', 'chestInhale'],
    poseTarget: { props: poseProps },
    poseBase: { props: poseProps },
    getMorphTargetNames() {
      return ['mouthOpen', 'jawOpen', 'mouthSmile'];
    },
    getMoodNames() {
      return ['neutral', 'happy'];
    },
    getViewNames() {
      return ['full', 'mid', 'upper', 'head'];
    },
    setView() {},
    setLighting() {},
    setMood() {},
    lookAtCamera() {},
    setValue(name, value, transitionMs) {
      calls.push({ name, value, transitionMs, kind: 'value' });
    },
    setFixedValue(name, value, transitionMs) {
      calls.push({ name, value, transitionMs, kind: 'fixed' });
    },
    playGesture(name, durationSeconds, mirror, transitionMs) {
      calls.push({ name, durationSeconds, mirror, transitionMs, template: this.gestureTemplates[name] });
    },
  };
}

test('publishes pseudo morphs and full-body bone nodes', () => {
  const registry = buildTalkingHeadNodeRegistry(fakeHead());
  const ids = registry.map((node) => node.id);

  assert.ok(ids.includes('handFistLeft'));
  assert.ok(ids.includes('handFistRight'));
  assert.ok(ids.includes('Hips.rotation'));
  assert.ok(ids.includes('Spine.rotation'));
  assert.ok(ids.includes('RightArm.rotation'));
  assert.ok(ids.includes('LeftHandIndex2.rotation'));
});

test('applies only calibrated finger bones through the bone overlay', () => {
  const head = fakeHead();
  const registry = buildTalkingHeadNodeRegistry(head);
  const intent = compileAvatarIntentNodes({
    voice: { line: 'Make a visible full-body point and left fist.', energy: 0.8 },
    camera: { view: 'full' },
    gesture: 'point',
    gaze: 'left',
    hair: { bend: 0.35 },
    hands: { leftFingerCurl: 1, rightFingerCurl: 0.2, openPalm: 0 },
    motion: { bodyMovement: 0.9, headMovement: 0.7, gestureIntensity: 0.9 },
  }, registry);

  const diagnostics = applyTalkingHeadBeat({
    head,
    intent,
    state: {
      cameraKey: JSON.stringify(intent.camera),
      lightingKey: `${intent.stage.lighting}:${intent.appearance.palette}`,
      materialKey: `${intent.appearance.outfit}:${intent.appearance.palette}:${intent.appearance.accessory}`,
      mood: 'neutral',
    },
  });

  const overlay = head.calls.find((call) => call.name === '__llm_bone_overlay');
  assert.ok(overlay);
  assert.equal(overlay.template['Hips.rotation'], undefined);
  assert.equal(overlay.template['Spine.rotation'], undefined);
  assert.equal(overlay.template['RightArm.rotation'], undefined);
  assert.ok(overlay.template['LeftHandIndex2.rotation']);
  assert.ok(overlay.template['LeftHandIndex2.rotation'].x > 0);
  assert.ok(diagnostics.applied.some((item) => item.startsWith('bone_overlay:')));
  assert.deepEqual(diagnostics.unsupported.filter((item) => item.startsWith('bone:')), []);
});

test('blocks uncalibrated absolute limb bones from LLM nodes', () => {
  const head = fakeHead();
  const intent = compileAvatarIntentNodes({
    voice: { line: 'Move hands without unsafe absolute limb overlays.', energy: 0.6 },
    nodes: [
      {
        id: 'RightArm.rotation',
        target: 'bone',
        value: 1,
        weight: 1,
        rotation: [0.8, 0.8, 0.8],
      },
      {
        id: 'LeftHandIndex2.rotation',
        target: 'bone',
        value: 1,
        weight: 1,
        rotation: [0.5, 0, 0],
      },
    ],
  }, buildTalkingHeadNodeRegistry(head));

  const diagnostics = applyTalkingHeadBeat({
    head,
    intent,
    state: {},
  });

  const overlay = head.calls.find((call) => call.name === '__llm_bone_overlay');
  assert.ok(overlay);
  assert.equal(overlay.template['RightArm.rotation'], undefined);
  assert.ok(overlay.template['LeftHandIndex2.rotation']);
  assert.ok(diagnostics.degraded.includes('bone:RightArm.rotation:blocked_uncalibrated_absolute_pose'));
});

test('applies speech-frame lips and bounded body motion without limb overlays', () => {
  const head = fakeHead();
  const intent = compileAvatarIntentNodes({
    voice: { line: 'Natural speech drives visemes and subtle body motion.', energy: 0.75 },
    hair: { bend: 0.25, sway: 0.7 },
    hands: { leftFingerCurl: 0.85, rightFingerCurl: 0.2 },
    motion: { bodyMovement: 0.8, headMovement: 0.7, gestureIntensity: 0.5 },
  }, buildTalkingHeadNodeRegistry(head));

  const diagnostics = applyTalkingHeadFrame({
    head,
    intent,
    mouthPulse: 0.28,
    speaking: true,
    elapsedSeconds: 1.4,
    visemeFrame: {
      current: 'aa',
      next: 'O',
      intensity: 0.9,
    },
  });

  assert.ok(diagnostics.applied.some((item) => item.startsWith('lips:aa:')));
  assert.ok(diagnostics.applied.some((item) => item.startsWith('body_motion:')));
  assert.ok(head.calls.some((call) => call.name === 'mouthOpen' && call.kind === 'fixed'));
  assert.ok(head.calls.some((call) => call.name === 'bodyRotateX' && call.kind === 'value'));
  assert.ok(head.calls.some((call) => call.name === 'headRotateX' && call.kind === 'value'));
  assert.ok(head.calls.some((call) => call.name === 'chestInhale' && call.kind === 'value'));
  assert.equal(head.calls.some((call) => call.name === '__llm_bone_overlay'), false);
});
