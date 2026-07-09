import { normalizeAvatarIntent } from './avatarIntent.js';

const MOOD_NODE_MAP = {
  neutral: 'neutral',
  happy: 'happy',
  focused: 'neutral',
  curious: 'happy',
  concerned: 'sad',
  angry: 'angry',
};

const GESTURE_NODE_MAP = {
  idle: '',
  open_palm: 'handup',
  point: 'index',
  wave: 'handup',
  thinking: 'shrug',
  nod_yes: 'thumbup',
  shake_no: 'thumbdown',
};

function clamp(value, lower, upper) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return lower;
  return Math.max(lower, Math.min(upper, parsed));
}

function registryMap(nodeRegistry = []) {
  const map = new Map();
  nodeRegistry.forEach((node) => {
    if (typeof node === 'string') map.set(node, { id: node, target: 'morph' });
    else if (node?.id) map.set(node.id, node);
  });
  return map;
}

function mergeNode(existing, compiled) {
  return {
    id: existing.id,
    target: compiled.target || existing.target || 'morph',
    weight: compiled.weight ?? existing.weight ?? 1,
    value: compiled.value ?? existing.value ?? 0,
    rotation: compiled.rotation || existing.rotation || [0, 0, 0],
    position: compiled.position || existing.position || [0, 0, 0],
    scale: compiled.scale || existing.scale || [0, 0, 0],
    option: compiled.option ?? existing.option ?? '',
    transitionMs: compiled.transitionMs ?? existing.transitionMs ?? 120,
    durationMs: compiled.durationMs ?? existing.durationMs ?? 1600,
  };
}

function addNode(nodes, map, id, patch) {
  const registered = map.get(id);
  if (!registered) return;
  const existingIndex = nodes.findIndex((node) => node.id === id);
  const existing = existingIndex >= 0 ? nodes[existingIndex] : {
    id,
    target: registered.target || patch.target || 'morph',
    weight: 1,
    value: 0,
    rotation: [0, 0, 0],
    position: [0, 0, 0],
    scale: [0, 0, 0],
    option: '',
    transitionMs: 120,
    durationMs: 1600,
  };
  const next = mergeNode(existing, { target: registered.target, ...patch });
  if (existingIndex >= 0) nodes[existingIndex] = next;
  else nodes.push(next);
}

function addOption(nodes, map, id, option, target = null) {
  addNode(nodes, map, id, {
    target: target || map.get(id)?.target,
    option,
    value: 1,
    weight: 1,
  });
}

function addValue(nodes, map, id, value, target = null) {
  addNode(nodes, map, id, {
    target: target || map.get(id)?.target,
    value: clamp(value, -1, 1),
    weight: 1,
  });
}

function addRotation(nodes, map, id, rotation, weight = 1) {
  addNode(nodes, map, id, {
    target: 'bone',
    value: 1,
    weight: clamp(weight, 0, 1),
    rotation: [
      clamp(rotation[0], -0.8, 0.8),
      clamp(rotation[1], -0.8, 0.8),
      clamp(rotation[2], -0.8, 0.8),
    ],
    transitionMs: 140,
    durationMs: 1800,
  });
}

function addHandCurlBones(nodes, map, side, curl) {
  const amount = clamp(curl, 0, 1);
  if (amount <= 0.01) return;
  const sign = side === 'Left' ? -1 : 1;
  const fingerCurl = amount * 0.8;
  const thumbCurl = amount * 0.72;

  addRotation(nodes, map, `${side}HandThumb1.rotation`, [thumbCurl * 0.25, sign * thumbCurl * 0.2, sign * thumbCurl * 0.42], amount);
  addRotation(nodes, map, `${side}HandThumb2.rotation`, [0, 0, sign * thumbCurl * 0.8], amount);
  addRotation(nodes, map, `${side}HandThumb3.rotation`, [0, 0, sign * thumbCurl * 0.72], amount);

  ['Index', 'Middle', 'Ring', 'Pinky'].forEach((finger, index) => {
    const baseSpread = (index - 1.5) * 0.035;
    addRotation(nodes, map, `${side}Hand${finger}1.rotation`, [fingerCurl * 0.72, sign * baseSpread, sign * baseSpread], amount);
    addRotation(nodes, map, `${side}Hand${finger}2.rotation`, [fingerCurl, 0, 0], amount);
    addRotation(nodes, map, `${side}Hand${finger}3.rotation`, [fingerCurl, 0, 0], amount);
  });
}

export function compileAvatarIntentNodes(intent, nodeRegistry = []) {
  const normalized = normalizeAvatarIntent(intent);
  const map = registryMap(nodeRegistry);
  if (!map.size) return normalized;
  const nodes = [...normalized.nodes];
  const mouth = clamp(0.12 + normalized.voice.energy * 0.45, 0, 0.85);
  const brow = normalized.face.brow;
  const smile = normalized.face.smile;
  const openPalmDamping = 1 - normalized.hands.openPalm * 0.82;
  const leftCurl = normalized.hands.leftFingerCurl * openPalmDamping;
  const rightCurl = normalized.hands.rightFingerCurl * openPalmDamping;

  addOption(nodes, map, 'camera.view', normalized.camera.view, 'camera');
  addValue(nodes, map, 'camera.distance', normalized.camera.distance / 6, 'camera');
  addValue(nodes, map, 'camera.x', normalized.camera.x / 1.5, 'camera');
  addValue(nodes, map, 'camera.y', normalized.camera.y / 1.5, 'camera');
  addValue(nodes, map, 'camera.rotateX', normalized.camera.rotateX / 0.75, 'camera');
  addValue(nodes, map, 'camera.rotateY', normalized.camera.rotateY / 0.75, 'camera');
  addOption(nodes, map, 'stage.lighting', normalized.stage.lighting, 'lighting');
  addOption(nodes, map, 'stage.background', normalized.stage.background, 'stage');
  addOption(nodes, map, 'motion.pose', normalized.motion.pose, 'pose');
  addOption(nodes, map, 'mood', MOOD_NODE_MAP[normalized.mood] || normalized.mood, 'gesture');
  addOption(nodes, map, 'gesture', GESTURE_NODE_MAP[normalized.gesture] || normalized.gesture, 'gesture');
  addOption(nodes, map, 'appearance.palette', normalized.appearance.palette, 'wardrobe');
  addOption(nodes, map, 'appearance.outfit', normalized.appearance.outfit, 'wardrobe');

  addValue(nodes, map, 'face.smile', smile, 'morph');
  addValue(nodes, map, 'face.brow', brow, 'morph');
  addValue(nodes, map, 'hands.leftFingerCurl', leftCurl, 'morph');
  addValue(nodes, map, 'hands.rightFingerCurl', rightCurl, 'morph');
  addValue(nodes, map, 'hands.openPalm', normalized.hands.openPalm, 'morph');
  addValue(nodes, map, 'hair.bend', normalized.hair.bend, 'dynamic_bone');
  addValue(nodes, map, 'hair.sway', normalized.hair.sway, 'dynamic_bone');
  addValue(nodes, map, 'motion.bodyMovement', normalized.motion.bodyMovement, 'morph');
  addValue(nodes, map, 'motion.headMovement', normalized.motion.headMovement, 'morph');

  addValue(nodes, map, 'mouthOpen', mouth, 'morph');
  addValue(nodes, map, 'jawOpen', mouth * 0.82, 'morph');
  addValue(nodes, map, 'mouthSmile', smile, 'morph');
  addValue(nodes, map, 'browInnerUp', Math.max(0, brow), 'morph');
  addValue(nodes, map, 'browDownLeft', Math.max(0, -brow), 'morph');
  addValue(nodes, map, 'browDownRight', Math.max(0, -brow), 'morph');
  addValue(nodes, map, 'handFistLeft', leftCurl, 'morph');
  addValue(nodes, map, 'handFistRight', rightCurl, 'morph');
  addValue(nodes, map, 'bodyRotateX', (normalized.voice.energy - 0.5) * 0.12 + normalized.motion.bodyMovement * 0.1, 'morph');
  addValue(nodes, map, 'bodyRotateY', normalized.hair.bend * 0.12, 'morph');
  addValue(nodes, map, 'bodyRotateZ', normalized.hair.bend * 0.08, 'morph');
  addValue(nodes, map, 'headRotateX', (normalized.motion.headMovement - 0.5) * 0.15, 'morph');
  addValue(nodes, map, 'headRotateZ', normalized.hair.bend * 0.1, 'morph');
  addValue(nodes, map, 'chestInhale', 0.18 + normalized.voice.energy * 0.32, 'morph');
  addValue(nodes, map, 'viseme_aa', mouth * 0.92, 'morph');
  addValue(nodes, map, 'viseme_E', mouth * 0.34, 'morph');
  addValue(nodes, map, 'viseme_I', mouth * 0.22, 'morph');
  addValue(nodes, map, 'viseme_O', mouth * 0.28, 'morph');
  addValue(nodes, map, 'viseme_U', mouth * 0.18, 'morph');
  addHandCurlBones(nodes, map, 'Left', leftCurl);
  addHandCurlBones(nodes, map, 'Right', rightCurl);

  for (const node of map.values()) {
    if (node.target !== 'material') continue;
    addValue(nodes, map, node.id, 0.24, 'material');
  }

  return normalizeAvatarIntent({
    ...normalized,
    nodes,
  });
}
