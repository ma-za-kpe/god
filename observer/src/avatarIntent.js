export const AVATAR_INTENT_SCHEMA_VERSION = 'god.avatar_intent.v1';

export const AVATAR_MOODS = [
  'neutral',
  'happy',
  'focused',
  'curious',
  'concerned',
  'angry',
];

export const AVATAR_GESTURES = [
  'idle',
  'open_palm',
  'point',
  'wave',
  'thinking',
  'nod_yes',
  'shake_no',
];

export const AVATAR_GAZES = ['camera', 'left', 'right', 'down'];

export const AVATAR_CAMERA_VIEWS = ['full', 'mid', 'upper', 'head'];

export const AVATAR_POSES = [
  'auto',
  'side',
  'hip',
  'turn',
  'bend',
  'back',
  'straight',
  'wide',
  'oneknee',
  'kneel',
];

export const AVATAR_LIGHTING = ['neutral', 'studio', 'dramatic', 'soft', 'alert'];

export const AVATAR_BACKGROUNDS = ['default', 'transparent', 'studio', 'night', 'warm'];

export const AVATAR_APPEARANCE = {
  avatars: ['rpm_default'],
  outfits: ['casual_dark', 'studio_host', 'field_operator', 'formal_black'],
  palettes: ['neutral', 'emerald', 'gold', 'crimson', 'electric_blue'],
  accessories: ['none', 'glasses', 'earpiece', 'hood'],
};

export const AVATAR_NODE_TARGETS = [
  'morph',
  'bone',
  'material',
  'dynamic_bone',
  'camera',
  'lighting',
  'stage',
  'pose',
  'gesture',
  'animation',
  'voice',
  'wardrobe',
];

export const TEST_AVATAR_LINE =
  'This is a local test fallback before the LLM is connected.';

function clamp(value, lower, upper) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return lower;
  return Math.max(lower, Math.min(upper, parsed));
}

function pickAllowed(value, allowed, fallback) {
  const normalized = String(value || '').trim().toLowerCase();
  return allowed.includes(normalized) ? normalized : fallback;
}

function boundedVector(value, lower, upper) {
  const input = Array.isArray(value) ? value : [];
  return [0, 1, 2].map((index) => clamp(input[index] ?? 0, lower, upper));
}

function normalizeNodeControls(value) {
  const input = Array.isArray(value) ? value : [];
  return input.slice(0, 256).map((item) => {
    const node = item && typeof item === 'object' ? item : {};
    return {
      id: String(node.id || '').replace(/[^A-Za-z0-9_.:-]/g, '').slice(0, 96),
      target: pickAllowed(node.target, AVATAR_NODE_TARGETS, 'morph'),
      weight: clamp(node.weight ?? 1, 0, 1),
      value: clamp(node.value ?? 0, -1, 1),
      rotation: boundedVector(node.rotation, -0.8, 0.8),
      position: boundedVector(node.position, -0.25, 0.25),
      scale: boundedVector(node.scale, -0.35, 0.35),
      option: String(node.option || '').replace(/[^A-Za-z0-9_.:-]/g, '').slice(0, 96),
      transitionMs: clamp(node.transitionMs ?? 90, 0, 5000),
      durationMs: clamp(node.durationMs ?? 1200, 0, 12000),
    };
  }).filter((node) => node.id);
}

export function normalizeAvatarIntent(raw = {}) {
  const source = raw && typeof raw === 'object' ? raw : {};
  const voice = source.voice && typeof source.voice === 'object' ? source.voice : {};
  const hair = source.hair && typeof source.hair === 'object' ? source.hair : {};
  const hands = source.hands && typeof source.hands === 'object' ? source.hands : {};
  const face = source.face && typeof source.face === 'object' ? source.face : {};
  const appearance = source.appearance && typeof source.appearance === 'object' ? source.appearance : {};
  const camera = source.camera && typeof source.camera === 'object' ? source.camera : {};
  const motion = source.motion && typeof source.motion === 'object' ? source.motion : {};
  const stage = source.stage && typeof source.stage === 'object' ? source.stage : {};

  return {
    schema: AVATAR_INTENT_SCHEMA_VERSION,
    mood: pickAllowed(source.mood, AVATAR_MOODS, 'neutral'),
    gesture: pickAllowed(source.gesture, AVATAR_GESTURES, 'idle'),
    gaze: pickAllowed(source.gaze, AVATAR_GAZES, 'camera'),
    tempo: clamp(source.tempo ?? 1, 0.5, 1.8),
    camera: {
      view: pickAllowed(camera.view ?? source.cameraView, AVATAR_CAMERA_VIEWS, 'full'),
      distance: clamp(camera.distance ?? 0, -4, 6),
      x: clamp(camera.x ?? 0, -1.5, 1.5),
      y: clamp(camera.y ?? 0, -1.5, 1.5),
      rotateX: clamp(camera.rotateX ?? 0, -0.75, 0.75),
      rotateY: clamp(camera.rotateY ?? 0, -0.75, 0.75),
    },
    voice: {
      line: String(voice.line || source.line || '').replace(/\s+/g, ' ').trim(),
      energy: clamp(voice.energy ?? source.energy ?? 0.55, 0, 1),
    },
    hair: {
      bend: clamp(hair.bend ?? 0, -1, 1),
      sway: clamp(hair.sway ?? 0.35, 0, 1),
    },
    hands: {
      leftFingerCurl: clamp(hands.leftFingerCurl ?? 0.2, 0, 1),
      rightFingerCurl: clamp(hands.rightFingerCurl ?? 0.2, 0, 1),
      openPalm: clamp(hands.openPalm ?? 0.3, 0, 1),
    },
    face: {
      brow: clamp(face.brow ?? 0, -1, 1),
      smile: clamp(face.smile ?? 0, 0, 1),
    },
    motion: {
      pose: pickAllowed(motion.pose, AVATAR_POSES, 'auto'),
      bodyMovement: clamp(motion.bodyMovement ?? 0.55, 0, 1),
      headMovement: clamp(motion.headMovement ?? 0.55, 0, 1),
      gestureIntensity: clamp(motion.gestureIntensity ?? 0.65, 0, 1),
    },
    stage: {
      lighting: pickAllowed(stage.lighting, AVATAR_LIGHTING, 'neutral'),
      background: pickAllowed(stage.background, AVATAR_BACKGROUNDS, 'default'),
    },
    appearance: {
      avatar: pickAllowed(appearance.avatar, AVATAR_APPEARANCE.avatars, 'rpm_default'),
      outfit: pickAllowed(appearance.outfit, AVATAR_APPEARANCE.outfits, 'casual_dark'),
      palette: pickAllowed(appearance.palette, AVATAR_APPEARANCE.palettes, 'neutral'),
      accessory: pickAllowed(appearance.accessory, AVATAR_APPEARANCE.accessories, 'none'),
      description: String(appearance.description || '').replace(/\s+/g, ' ').trim().slice(0, 180),
    },
    nodes: normalizeNodeControls(source.nodes),
  };
}

export function intentFromText(text) {
  const line = String(text || TEST_AVATAR_LINE).replace(/\s+/g, ' ').trim();
  const lower = line.toLowerCase();
  const excited = /!|great|win|alive|success|yes|good|happy/.test(lower);
  const worried = /risk|fail|wrong|concern|problem|danger|blocked/.test(lower);
  const thinking = /think|why|how|reason|maybe|consider|plan/.test(lower);
  const rejecting = /\b(no|not|never|stop|wrong)\b/.test(lower);
  const pointing = /\b(this|that|there|look|watch|see)\b/.test(lower);
  const waving = /\b(hello|hi|wave|greet)\b/.test(lower);

  let mood = 'curious';
  if (excited) mood = 'happy';
  if (thinking) mood = 'focused';
  if (worried) mood = 'concerned';
  if (/\b(angry|mad|furious)\b/.test(lower)) mood = 'angry';

  let gesture = 'open_palm';
  if (waving) gesture = 'wave';
  else if (pointing) gesture = 'point';
  else if (thinking) gesture = 'thinking';
  else if (rejecting) gesture = 'shake_no';
  else if (excited) gesture = 'nod_yes';

  const intensity = clamp((line.match(/[!?]/g)?.length || 0) * 0.18 + line.length / 240, 0.12, 0.95);
  return normalizeAvatarIntent({
    mood,
    gesture,
    gaze: pointing ? 'left' : 'camera',
    tempo: excited ? 1.25 : thinking ? 0.82 : 1,
    camera: {
      view: excited ? 'full' : thinking ? 'upper' : pointing ? 'mid' : 'full',
      distance: 0,
      x: pointing ? -0.12 : 0,
      y: 0,
      rotateX: 0,
      rotateY: pointing ? -0.06 : 0,
    },
    voice: {
      line,
      energy: worried ? 0.44 : Math.max(0.48, intensity),
    },
    hair: {
      bend: rejecting ? -0.35 : pointing ? 0.28 : excited ? 0.18 : 0.08,
      sway: Math.max(0.22, intensity),
    },
    hands: {
      leftFingerCurl: thinking ? 0.75 : 0.18,
      rightFingerCurl: pointing ? 0.05 : rejecting ? 0.65 : 0.22,
      openPalm: gesture === 'open_palm' || gesture === 'wave' ? 0.85 : 0.35,
    },
    face: {
      brow: worried ? -0.35 : thinking ? 0.28 : 0.08,
      smile: excited ? 0.78 : mood === 'happy' ? 0.6 : 0.12,
    },
    motion: {
      pose: thinking ? 'hip' : excited ? 'straight' : pointing ? 'side' : 'auto',
      bodyMovement: excited ? 0.82 : thinking ? 0.32 : 0.55,
      headMovement: worried ? 0.28 : 0.62,
      gestureIntensity: excited ? 0.86 : 0.62,
    },
    stage: {
      lighting: worried ? 'alert' : thinking ? 'studio' : 'neutral',
      background: 'default',
    },
    appearance: {
      outfit: thinking ? 'studio_host' : worried ? 'field_operator' : 'casual_dark',
      palette: excited ? 'gold' : worried ? 'crimson' : 'emerald',
      accessory: thinking ? 'glasses' : 'none',
      description: 'Explicit test fallback appearance.',
    },
    nodes: [],
  });
}

export function avatarIntentToJson(intent) {
  return JSON.stringify(normalizeAvatarIntent(intent), null, 2);
}
