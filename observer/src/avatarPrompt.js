import {
  AVATAR_APPEARANCE,
  AVATAR_BACKGROUNDS,
  AVATAR_CAMERA_VIEWS,
  AVATAR_GAZES,
  AVATAR_GESTURES,
  AVATAR_LIGHTING,
  AVATAR_MOODS,
  AVATAR_NODE_TARGETS,
  AVATAR_POSES,
  avatarIntentToJson,
  normalizeAvatarIntent,
} from './avatarIntent.js';

const MAX_NODE_IDS_IN_PROMPT = 256;

export const AVATAR_PROMPT_SYSTEM = [
  'You are the realtime performance director for one humanlike AI avatar.',
  'Return exactly one JSON object and no markdown.',
  'The JSON must describe everything visible: dialogue, camera framing, mood, gesture, gaze, pose, stage, lighting, wardrobe/body presentation, facial expression, hair, hands, and per-node controls.',
  'Use only allowed enum values and only node ids supplied by the renderer registry.',
  'Do not emit arbitrary code, URLs, CSS, shaders, filesystem paths, or prose outside JSON.',
  'Choose camera and staging intentionally for the current beat; do not leave framing as a renderer default.',
  'When hand, finger, wardrobe, or body controls matter, choose full or mid framing so the change is visible.',
  'When the requested beat mentions full body, body movement, posture, outfit, or a whole-avatar control demonstration, choose camera.view full unless the beat is explicitly a face close-up; use mid for hand/finger inspection beats.',
  'Prefer coherent human motion over noisy over-control. Use node controls deliberately and continuously.',
].join(' ');

export const AVATAR_INTENT_SHAPE = {
  mood: 'neutral',
  gesture: 'idle',
  gaze: 'camera',
  tempo: 1,
  camera: { view: 'full', distance: 0, x: 0, y: 0, rotateX: 0, rotateY: 0 },
  voice: { line: 'short spoken line', energy: 0.6 },
  hair: { bend: 0, sway: 0.35 },
  hands: { leftFingerCurl: 0.2, rightFingerCurl: 0.2, openPalm: 0.3 },
  face: { brow: 0, smile: 0.2 },
  motion: { pose: 'auto', bodyMovement: 0.55, headMovement: 0.55, gestureIntensity: 0.65 },
  stage: { lighting: 'neutral', background: 'default' },
  appearance: {
    avatar: 'rpm_default',
    outfit: 'casual_dark',
    palette: 'neutral',
    accessory: 'none',
    description: 'short wardrobe/body presentation description',
  },
  nodes: [],
};

function nodeDescriptors(nodeRegistry = []) {
  return nodeRegistry
    .slice(0, MAX_NODE_IDS_IN_PROMPT)
    .map((node) => {
      if (typeof node === 'string') return { id: node, target: 'morph' };
      if (!node?.id) return null;
      const descriptor = {
        id: node.id,
        target: node.target || 'morph',
      };
      if (node.values) descriptor.values = node.values;
      if (node.range) descriptor.range = node.range;
      if (node.description) descriptor.description = node.description;
      return descriptor;
    })
    .filter(Boolean);
}

export function buildAvatarIntentMessages({
  line = '',
  previousIntent = null,
  nodeRegistry = [],
  autonomous = false,
  repairError = '',
} = {}) {
  const rendererNodes = nodeDescriptors(nodeRegistry);
  const previous = previousIntent ? avatarIntentToJson(previousIntent) : avatarIntentToJson({});
  const mode = autonomous
    ? 'Create the next short spoken line and a complete avatar performance intent. Do not repeat the previous spoken line; change the camera, pose, hands, face, stage, wardrobe, or concrete nodes when the beat changes.'
    : 'Transform the requested line into a complete avatar performance intent. If the requested line is blank, create a short line.';

  const user = [
    mode,
    '',
    `Requested line: ${String(line || '').replace(/\s+/g, ' ').trim()}`,
    `Previous intent: ${previous}`,
    `Allowed moods: ${AVATAR_MOODS.join(', ')}`,
    `Allowed gestures: ${AVATAR_GESTURES.join(', ')}`,
    `Allowed gazes: ${AVATAR_GAZES.join(', ')}`,
    `Allowed camera views: ${AVATAR_CAMERA_VIEWS.join(', ')}`,
    `Allowed poses: ${AVATAR_POSES.join(', ')}`,
    `Allowed lighting: ${AVATAR_LIGHTING.join(', ')}`,
    `Allowed backgrounds: ${AVATAR_BACKGROUNDS.join(', ')}`,
    `Allowed appearance avatars: ${AVATAR_APPEARANCE.avatars.join(', ')}`,
    `Allowed outfits: ${AVATAR_APPEARANCE.outfits.join(', ')}`,
    `Allowed palettes: ${AVATAR_APPEARANCE.palettes.join(', ')}`,
    `Allowed accessories: ${AVATAR_APPEARANCE.accessories.join(', ')}`,
    `Allowed node targets: ${AVATAR_NODE_TARGETS.join(', ')}`,
    `Renderer nodes: ${JSON.stringify(rendererNodes)}`,
    `Required JSON shape: ${JSON.stringify(AVATAR_INTENT_SHAPE)}`,
    repairError ? `Repair this previous error: ${repairError}` : '',
    '',
    'Do not copy placeholder strings from the required JSON shape. voice.line must be a concrete spoken sentence. nodes may be empty, but any node id used must exactly match Renderer nodes.',
    'Avoid generic greetings or filler. The spoken line must directly respond to the requested line and mention at least one concrete requested detail when present.',
    'When Renderer nodes are available, include at least 6 meaningful direct node controls using exact ids. Prefer camera.view, stage.lighting, motion.pose, mouthOpen or jawOpen, handFistLeft/Right, hands.* curl nodes, Left/RightHand* finger bone nodes, face.smile, hair.bend/sway, and material or wardrobe proxy nodes when listed.',
    'If the requested action mentions full body, body movement, posture, outfit, wardrobe, legs, or whole-avatar node control, choose camera.view full unless the request explicitly asks for a close-up. Use camera.view mid for hand or finger inspection beats only when full-body context is not required.',
    autonomous ? 'For autonomous continuous performance, vary framing across beats, but keep full or mid for visible body, hands, wardrobe, and finger controls; do not hide those controls with upper/head framing.' : '',
    'Quality bar: one believable, humanlike performance beat; camera, wardrobe, pose, stage, and node controls must support the spoken line. The LLM owns every listed node: set direct nodes when they matter, leave irrelevant nodes neutral, and never invent node ids or renderer capabilities.',
  ].filter(Boolean).join('\n');

  return [
    { role: 'system', content: AVATAR_PROMPT_SYSTEM },
    { role: 'user', content: user },
  ];
}

export function buildOllamaAvatarRequest({ model, messages }) {
  return {
    model,
    stream: false,
    format: 'json',
    keep_alive: '10m',
    options: {
      num_predict: 520,
      temperature: 0.72,
      top_p: 0.9,
      repeat_penalty: 1.08,
    },
    messages,
  };
}

export function firstJsonObject(text) {
  const raw = String(text || '').trim();
  if (!raw) return null;
  if (raw.startsWith('{')) return raw;
  const start = raw.indexOf('{');
  const end = raw.lastIndexOf('}');
  if (start >= 0 && end > start) return raw.slice(start, end + 1);
  return null;
}

function nodeIdSet(nodeRegistry = []) {
  return new Set(
    nodeRegistry
      .map((node) => (typeof node === 'string' ? node : node?.id))
      .filter(Boolean),
  );
}

function sanitizeRendererNodes(parsed, nodeRegistry = []) {
  const allowed = nodeIdSet(nodeRegistry);
  if (!allowed.size || !Array.isArray(parsed?.nodes)) return parsed;
  const nodeById = new Map(
    nodeRegistry
      .map((node) => (typeof node === 'string' ? { id: node, target: 'morph' } : node))
      .filter((node) => node?.id)
      .map((node) => [node.id, node]),
  );
  const nodes = parsed.nodes.flatMap((node) => {
    const id = String(node?.id || '').trim();
    if (!id) return [];
    if (allowed.has(id)) return [node];
    const rotationId = `${id}.rotation`;
    if (allowed.has(rotationId)) {
      return [{
        ...node,
        id: rotationId,
        target: nodeById.get(rotationId)?.target || 'bone',
      }];
    }
    const positionId = `${id}.position`;
    if (allowed.has(positionId)) {
      return [{
        ...node,
        id: positionId,
        target: nodeById.get(positionId)?.target || 'bone',
      }];
    }
    return [];
  });
  return {
    ...parsed,
    nodes,
  };
}

function isPlaceholderLine(line) {
  return /^(short spoken line|spoken line|say one concise sentence|example|placeholder)$/i.test(
    String(line || '').trim(),
  );
}

function isGenericLine(line) {
  return /^(hello|hi|hey|hello[,! ]+how are you( today)?[?!.]?|how are you( today)?[?!.]?|i am ready[.!]?|let'?s begin[.!]?)$/i.test(
    String(line || '').trim(),
  );
}

function validateParsedIntent(parsed, { nodeRegistry = [], requestedLine = '' } = {}) {
  const line = parsed?.voice?.line || parsed?.line || '';
  if (isPlaceholderLine(line)) throw new Error('intent:placeholder-line');
  const requested = String(requestedLine || '').trim();
  if (requested && requested.length > 12 && isGenericLine(line)) {
    throw new Error('intent:generic-line');
  }
  const allowed = nodeIdSet(nodeRegistry);
  if (!allowed.size) return;
  const nodes = Array.isArray(parsed?.nodes) ? parsed.nodes : [];
  const unknown = nodes
    .map((node) => String(node?.id || '').trim())
    .filter((id) => id && !allowed.has(id));
  if (unknown.length) {
    throw new Error(`intent:unknown-node:${unknown.slice(0, 8).join(',')}`);
  }
}

export function parseAvatarIntentResponse(payload, { requestedLine = '', nodeRegistry = [] } = {}) {
  const jsonText = firstJsonObject(payload?.message?.content || payload?.response || '');
  if (!jsonText) throw new Error('intent:no-json');
  const parsed = sanitizeRendererNodes(JSON.parse(jsonText), nodeRegistry);
  validateParsedIntent(parsed, { nodeRegistry, requestedLine });
  const nextIntent = normalizeAvatarIntent(parsed);
  if (!nextIntent.voice.line && requestedLine) {
    nextIntent.voice.line = String(requestedLine).replace(/\s+/g, ' ').trim();
  }
  if (isPlaceholderLine(nextIntent.voice.line)) throw new Error('intent:placeholder-line');
  if (String(requestedLine || '').trim().length > 12 && isGenericLine(nextIntent.voice.line)) {
    throw new Error('intent:generic-line');
  }
  if (!nextIntent.voice.line) throw new Error('intent:missing-line');
  return nextIntent;
}
