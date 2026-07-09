import test from 'node:test';
import assert from 'node:assert/strict';

import {
  AVATAR_INTENT_SCHEMA_VERSION,
  avatarIntentToJson,
  intentFromText,
  normalizeAvatarIntent,
  TEST_AVATAR_LINE,
} from '../src/avatarIntent.js';
import { compileAvatarIntentNodes } from '../src/avatarNodeCompiler.js';
import { sampleTextViseme, textToVisemes } from '../src/avatarVisemes.js';

test('normalizes LLM avatar intent into the bounded contract', () => {
  const intent = normalizeAvatarIntent({
    mood: 'happy',
    gesture: 'wave',
    gaze: 'left',
    tempo: 99,
    voice: { line: '  hello   world  ', energy: 2 },
    hair: { bend: -5, sway: 3 },
    hands: { leftFingerCurl: 9, rightFingerCurl: -1, openPalm: 0.75 },
    face: { brow: -9, smile: 8 },
    appearance: {
      avatar: 'rpm_default',
      outfit: 'studio_host',
      palette: 'electric_blue',
      accessory: 'glasses',
      description: '  host jacket with blue trim  ',
    },
    nodes: [
      {
        id: 'mouthOpen',
        target: 'morph',
        value: 2,
        weight: 5,
        rotation: [9, -9, 0.25],
        position: [1, -1, 0.1],
        scale: [1, -1, 0.2],
      },
    ],
  });

  assert.equal(intent.schema, AVATAR_INTENT_SCHEMA_VERSION);
  assert.equal(intent.mood, 'happy');
  assert.equal(intent.gesture, 'wave');
  assert.equal(intent.gaze, 'left');
  assert.equal(intent.tempo, 1.8);
  assert.equal(intent.voice.line, 'hello world');
  assert.equal(intent.voice.energy, 1);
  assert.equal(intent.hair.bend, -1);
  assert.equal(intent.hair.sway, 1);
  assert.equal(intent.hands.leftFingerCurl, 1);
  assert.equal(intent.hands.rightFingerCurl, 0);
  assert.equal(intent.hands.openPalm, 0.75);
  assert.equal(intent.face.brow, -1);
  assert.equal(intent.face.smile, 1);
  assert.equal(intent.appearance.outfit, 'studio_host');
  assert.equal(intent.appearance.palette, 'electric_blue');
  assert.equal(intent.appearance.accessory, 'glasses');
  assert.equal(intent.appearance.description, 'host jacket with blue trim');
  assert.equal(intent.nodes.length, 1);
  assert.equal(intent.nodes[0].id, 'mouthOpen');
  assert.equal(intent.nodes[0].value, 1);
  assert.equal(intent.nodes[0].weight, 1);
  assert.deepEqual(intent.nodes[0].rotation, [0.8, -0.8, 0.25]);
  assert.deepEqual(intent.nodes[0].position, [0.25, -0.25, 0.1]);
  assert.deepEqual(intent.nodes[0].scale, [0.35, -0.35, 0.2]);
});

test('falls back only to safe enums and explicit test text', () => {
  const intent = normalizeAvatarIntent({
    mood: 'raw_bone_write',
    gesture: 'execute',
    gaze: 'behind',
    voice: { line: '' },
    appearance: { outfit: 'remote_url_write', palette: 'shader_injection' },
  });

  assert.equal(intent.mood, 'neutral');
  assert.equal(intent.gesture, 'idle');
  assert.equal(intent.gaze, 'camera');
  assert.equal(intent.voice.line, '');
  assert.equal(intent.appearance.outfit, 'casual_dark');
  assert.equal(intent.appearance.palette, 'neutral');

  const testIntent = intentFromText('');
  assert.equal(testIntent.voice.line, TEST_AVATAR_LINE);
});

test('serializes the same bounded contract that renderers consume', () => {
  const json = avatarIntentToJson({ voice: { line: 'move from LLM intent' } });
  const parsed = JSON.parse(json);

  assert.equal(parsed.schema, AVATAR_INTENT_SCHEMA_VERSION);
  assert.equal(parsed.voice.line, 'move from LLM intent');
  assert.ok(Object.hasOwn(parsed.hair, 'bend'));
  assert.ok(Object.hasOwn(parsed.hands, 'leftFingerCurl'));
  assert.ok(Object.hasOwn(parsed.appearance, 'outfit'));
  assert.ok(Array.isArray(parsed.nodes));
});

test('compiles semantic LLM intent into concrete renderer node controls', () => {
  const registry = [
    { id: 'camera.view', target: 'camera' },
    { id: 'stage.lighting', target: 'lighting' },
    { id: 'motion.pose', target: 'pose' },
    { id: 'mouthOpen', target: 'morph' },
    { id: 'jawOpen', target: 'morph' },
    { id: 'handFistLeft', target: 'morph' },
    { id: 'bodyRotateX', target: 'morph' },
    { id: 'bodyRotateY', target: 'morph' },
    { id: 'headRotateX', target: 'morph' },
    { id: 'chestInhale', target: 'morph' },
    { id: 'hair.bend', target: 'dynamic_bone' },
    { id: 'Hips.rotation', target: 'bone' },
    { id: 'Spine.rotation', target: 'bone' },
    { id: 'Head.rotation', target: 'bone' },
    { id: 'RightArm.rotation', target: 'bone' },
    { id: 'LeftHandIndex1.rotation', target: 'bone' },
    { id: 'LeftHandIndex2.rotation', target: 'bone' },
    { id: 'LeftHandIndex3.rotation', target: 'bone' },
    { id: 'material:0', target: 'material' },
  ];
  const compiled = compileAvatarIntentNodes({
    voice: { line: 'LLM controls this avatar.', energy: 0.7 },
    camera: { view: 'full' },
    stage: { lighting: 'dramatic' },
    motion: { pose: 'straight', bodyMovement: 0.8 },
    gesture: 'point',
    hair: { bend: 0.4 },
    hands: { leftFingerCurl: 0.8 },
  }, registry);

  const ids = compiled.nodes.map((node) => node.id);
  assert.ok(ids.includes('camera.view'));
  assert.ok(ids.includes('stage.lighting'));
  assert.ok(ids.includes('mouthOpen'));
  assert.ok(ids.includes('hair.bend'));
  assert.ok(ids.includes('bodyRotateX'));
  assert.ok(ids.includes('bodyRotateY'));
  assert.ok(ids.includes('headRotateX'));
  assert.ok(ids.includes('chestInhale'));
  assert.ok(ids.includes('LeftHandIndex1.rotation'));
  assert.ok(ids.includes('LeftHandIndex2.rotation'));
  assert.ok(ids.includes('LeftHandIndex3.rotation'));
  assert.ok(ids.includes('material:0'));
  assert.equal(compiled.nodes.find((node) => node.id === 'camera.view').option, 'full');
  assert.equal(compiled.nodes.find((node) => node.id === 'stage.lighting').option, 'dramatic');
  assert.equal(compiled.nodes.find((node) => node.id === 'bodyRotateX').target, 'morph');
  assert.equal(compiled.nodes.find((node) => node.id === 'RightArm.rotation'), undefined);
  assert.ok(compiled.nodes.find((node) => node.id === 'LeftHandIndex2.rotation').rotation[0] > 0);
});

test('samples text into changing speech visemes', () => {
  const visemes = textToVisemes('Through Llama, move my mouth.');
  assert.ok(visemes.includes('TH'));
  assert.ok(visemes.includes('PP'));

  const early = sampleTextViseme({ text: 'Through Llama, move my mouth.', elapsedSeconds: 0.1, durationSeconds: 3 });
  const later = sampleTextViseme({ text: 'Through Llama, move my mouth.', elapsedSeconds: 2.2, durationSeconds: 3 });
  assert.notEqual(early.current, later.current);
  assert.ok(early.intensity >= 0);
  assert.ok(later.intensity >= 0);
});
