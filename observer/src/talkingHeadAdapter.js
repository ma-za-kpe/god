import {
  AVATAR_APPEARANCE,
  AVATAR_BACKGROUNDS,
  AVATAR_CAMERA_VIEWS,
  AVATAR_GESTURES,
  AVATAR_LIGHTING,
  AVATAR_MOODS,
  AVATAR_POSES,
  normalizeAvatarIntent,
} from './avatarIntent.js';

const MOOD_MAP = {
  neutral: 'neutral',
  happy: 'happy',
  focused: 'neutral',
  curious: 'happy',
  concerned: 'sad',
  angry: 'angry',
};

const GESTURE_MAP = {
  idle: '',
  open_palm: 'handup',
  point: 'index',
  wave: 'handup',
  thinking: 'shrug',
  nod_yes: 'thumbup',
  shake_no: 'thumbdown',
};

const PALETTE_COLORS = {
  neutral: '#9ee6b5',
  emerald: '#3ddc84',
  gold: '#f0c46a',
  crimson: '#f06f6f',
  electric_blue: '#69a7ff',
};

const LIGHTING_PRESETS = {
  neutral: {
    lightAmbientColor: '#ffffff',
    lightAmbientIntensity: 2,
    lightDirectColor: '#b9c5ff',
    lightDirectIntensity: 30,
    lightDirectPhi: 1,
    lightDirectTheta: 2,
    lightSpotIntensity: 0,
  },
  studio: {
    lightAmbientColor: '#ffffff',
    lightAmbientIntensity: 2.4,
    lightDirectColor: '#f3f6ff',
    lightDirectIntensity: 36,
    lightDirectPhi: 0.8,
    lightDirectTheta: 1.6,
    lightSpotIntensity: 0.45,
    lightSpotPhi: 0.5,
    lightSpotTheta: 3.7,
    lightSpotDispersion: 0.8,
  },
  dramatic: {
    lightAmbientColor: '#dce8ff',
    lightAmbientIntensity: 1.2,
    lightDirectColor: '#ffffff',
    lightDirectIntensity: 44,
    lightDirectPhi: 0.55,
    lightDirectTheta: 2.45,
    lightSpotIntensity: 1.1,
    lightSpotPhi: 0.35,
    lightSpotTheta: 4.1,
    lightSpotDispersion: 0.62,
  },
  soft: {
    lightAmbientColor: '#fff8e7',
    lightAmbientIntensity: 2.8,
    lightDirectColor: '#fff1ca',
    lightDirectIntensity: 18,
    lightDirectPhi: 1.15,
    lightDirectTheta: 2.2,
    lightSpotIntensity: 0,
  },
  alert: {
    lightAmbientColor: '#fff1f1',
    lightAmbientIntensity: 1.7,
    lightDirectColor: '#ffb1b1',
    lightDirectIntensity: 42,
    lightDirectPhi: 0.7,
    lightDirectTheta: 2.7,
    lightSpotColor: '#ff7171',
    lightSpotIntensity: 0.75,
    lightSpotPhi: 0.35,
    lightSpotTheta: 4.2,
    lightSpotDispersion: 0.7,
  },
};

const BACKGROUND_STYLES = {
  default: {
    background: 'radial-gradient(circle at 50% 40%, #133139 0%, #071014 58%, #050b0d 100%)',
  },
  transparent: {
    background: 'transparent',
  },
  studio: {
    background: 'linear-gradient(180deg, #17242a 0%, #0c1418 100%)',
  },
  night: {
    background: 'linear-gradient(180deg, #09111d 0%, #04070b 100%)',
  },
  warm: {
    background: 'linear-gradient(180deg, #241914 0%, #0d100d 100%)',
  },
};

const TALKINGHEAD_PSEUDO_MORPHS = [
  'handFistLeft',
  'handFistRight',
  'bodyRotateX',
  'bodyRotateY',
  'bodyRotateZ',
  'headRotateX',
  'headRotateY',
  'headRotateZ',
  'chestInhale',
];

const FINGER_BONE_PATTERN = /^(Left|Right)Hand(Thumb|Index|Middle|Ring|Pinky)[1234]\.(rotation|quaternion)$/;

function clamp(value, lower, upper) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return lower;
  return Math.max(lower, Math.min(upper, parsed));
}

function safeId(value) {
  return String(value || '').replace(/[^A-Za-z0-9_.:-]/g, '').slice(0, 96);
}

function uniqueNodes(nodes) {
  const seen = new Set();
  return nodes.filter((node) => {
    if (!node?.id) return false;
    const key = `${node.target}:${node.id}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function materialsFromHead(head) {
  const materials = [];
  const seen = new Set();
  head?.armature?.traverse?.((object) => {
    const list = Array.isArray(object.material)
      ? object.material
      : object.material ? [object.material] : [];
    list.forEach((material) => {
      const key = material.uuid || `${object.name}:${material.name}`;
      if (seen.has(key)) return;
      seen.add(key);
      materials.push({ object, material });
    });
  });
  return materials;
}

function posePropKeys(head) {
  return Object.keys(head?.poseTarget?.props || head?.poseBase?.props || {});
}

function morphNames(head) {
  const names = new Set([
    ...(head?.getMorphTargetNames?.() || []),
    ...Object.keys(head?.mtAvatar || {}),
  ]);
  TALKINGHEAD_PSEUDO_MORPHS.forEach((name) => {
    if (head?.mtAvatar?.[name] || head?.mtCustoms?.includes?.(name)) names.add(name);
  });
  return names;
}

function hasMorph(head, name) {
  return morphNames(head).has(name);
}

function setMorphValue(head, name, value, diagnostics, { fixed = false, optional = false, transitionMs = 90 } = {}) {
  if (!hasMorph(head, name)) {
    if (!optional) diagnostics.unsupported.push(`morph:${name}`);
    return false;
  }
  try {
    if (fixed && head.setFixedValue) head.setFixedValue(name, value, transitionMs);
    else if (head.setValue) head.setValue(name, value, transitionMs);
    else {
      if (!optional) diagnostics.unsupported.push(`morph:${name}:no_setter`);
      return false;
    }
    diagnostics.applied.push(`morph:${name}`);
    return true;
  } catch (error) {
    if (!optional) diagnostics.unsupported.push(`morph:${name}:${error instanceof Error ? error.message : String(error)}`);
    return false;
  }
}

function semanticNodes(head) {
  const views = head?.getViewNames?.() || AVATAR_CAMERA_VIEWS;
  const poses = Object.keys(head?.poseTemplates || {}).length
    ? ['auto', ...Object.keys(head.poseTemplates)]
    : AVATAR_POSES;
  const moods = head?.getMoodNames?.() || AVATAR_MOODS;
  const gestures = Object.keys(head?.gestureTemplates || {});
  return [
    { id: 'camera.view', target: 'camera', values: views, description: 'LLM-owned shot framing.' },
    { id: 'camera.distance', target: 'camera', range: [-4, 6], description: 'Camera distance offset.' },
    { id: 'camera.x', target: 'camera', range: [-1.5, 1.5], description: 'Camera horizontal offset.' },
    { id: 'camera.y', target: 'camera', range: [-1.5, 1.5], description: 'Camera vertical offset.' },
    { id: 'camera.rotateX', target: 'camera', range: [-0.75, 0.75], description: 'Camera pitch offset.' },
    { id: 'camera.rotateY', target: 'camera', range: [-0.75, 0.75], description: 'Camera yaw offset.' },
    { id: 'mood', target: 'gesture', values: moods, description: 'Renderer mood loop.' },
    { id: 'gesture', target: 'gesture', values: [...AVATAR_GESTURES, ...gestures], description: 'Semantic or renderer-native gesture.' },
    { id: 'gaze', target: 'gesture', values: ['camera', 'left', 'right', 'down'], description: 'Head and eye attention target.' },
    { id: 'motion.pose', target: 'pose', values: poses, description: 'Standing pose or auto pose loop.' },
    { id: 'motion.bodyMovement', target: 'morph', range: [0, 1], description: 'Upper body movement energy.' },
    { id: 'motion.headMovement', target: 'morph', range: [0, 1], description: 'Head movement energy.' },
    { id: 'stage.lighting', target: 'lighting', values: AVATAR_LIGHTING, description: 'Renderer lighting preset.' },
    { id: 'stage.background', target: 'stage', values: AVATAR_BACKGROUNDS, description: 'Browser stage background.' },
    { id: 'hair.bend', target: 'dynamic_bone', range: [-1, 1], description: 'Hair or hair-proxy bend.' },
    { id: 'hair.sway', target: 'dynamic_bone', range: [0, 1], description: 'Hair or hair-proxy sway.' },
    { id: 'hands.leftFingerCurl', target: 'morph', range: [0, 1], description: 'Left hand curl/fist proxy.' },
    { id: 'hands.rightFingerCurl', target: 'morph', range: [0, 1], description: 'Right hand curl/fist proxy.' },
    { id: 'hands.openPalm', target: 'morph', range: [0, 1], description: 'Open-palm hand shape proxy.' },
    { id: 'face.brow', target: 'morph', range: [-1, 1], description: 'Brow expression.' },
    { id: 'face.smile', target: 'morph', range: [0, 1], description: 'Smile expression.' },
    { id: 'appearance.avatar', target: 'wardrobe', values: AVATAR_APPEARANCE.avatars, description: 'Avatar identity request.' },
    { id: 'appearance.outfit', target: 'wardrobe', values: AVATAR_APPEARANCE.outfits, description: 'Outfit request; adapter degrades to material/stage styling when meshes are unavailable.' },
    { id: 'appearance.palette', target: 'wardrobe', values: AVATAR_APPEARANCE.palettes, description: 'Wardrobe/stage palette request.' },
    { id: 'appearance.accessory', target: 'wardrobe', values: AVATAR_APPEARANCE.accessories, description: 'Accessory request; requires an asset with matching meshes.' },
  ];
}

export function buildTalkingHeadNodeRegistry(head) {
  const morphs = [...morphNames(head)].map((id) => ({
    id,
    target: 'morph',
    range: id.startsWith('bodyRotate') || id.startsWith('headRotate') ? [-1, 1] : [0, 1],
    description: 'TalkingHead morph, viseme, or pseudo-morph value.',
  }));

  const bones = posePropKeys(head).map((key) => ({
    id: safeId(key.endsWith('.quaternion') ? key.replace('.quaternion', '.rotation') : key),
    target: 'bone',
    range: key.endsWith('.position') ? [-0.25, 0.25] : [-0.8, 0.8],
    description: 'Renderer bone surface. Only calibrated finger bones are applied directly; larger body motion routes through bounded pose and pseudo-morph controls.',
  }));

  const materials = materialsFromHead(head).map(({ object, material }, index) => ({
    id: `material:${index}`,
    target: 'material',
    range: [-1, 1],
    description: `Material tint/emissive fallback for ${material.name || object.name || `material ${index}`}.`,
  }));

  const dynamicBones = (head?.avatar?.modelDynamicBones || []).map((item) => ({
    id: safeId(item.bone),
    target: 'dynamic_bone',
    range: [-1, 1],
    description: 'Asset-provided dynamic bone.',
  }));

  return uniqueNodes([
    ...semanticNodes(head),
    ...morphs,
    ...bones,
    ...materials,
    ...dynamicBones,
  ]);
}

export function stageStyleForIntent(intent) {
  const normalized = normalizeAvatarIntent(intent);
  return BACKGROUND_STYLES[normalized.stage.background] || BACKGROUND_STYLES.default;
}

function lightingForIntent(intent) {
  const normalized = normalizeAvatarIntent(intent);
  const preset = LIGHTING_PRESETS[normalized.stage.lighting] || LIGHTING_PRESETS.neutral;
  const palette = PALETTE_COLORS[normalized.appearance.palette] || PALETTE_COLORS.neutral;
  return {
    ...preset,
    lightSpotColor: preset.lightSpotColor || palette,
  };
}

function cameraKey(intent) {
  const camera = normalizeAvatarIntent(intent).camera;
  return JSON.stringify(camera);
}

function lightingKey(intent) {
  const normalized = normalizeAvatarIntent(intent);
  return `${normalized.stage.lighting}:${normalized.appearance.palette}`;
}

function materialKey(intent) {
  const normalized = normalizeAvatarIntent(intent);
  return `${normalized.appearance.outfit}:${normalized.appearance.palette}:${normalized.appearance.accessory}`;
}

function applyMaterialFallback(head, intent, diagnostics) {
  const normalized = normalizeAvatarIntent(intent);
  const color = PALETTE_COLORS[normalized.appearance.palette] || PALETTE_COLORS.neutral;
  const materials = materialsFromHead(head);
  if (!materials.length) {
    diagnostics.unsupported.push('appearance.materials');
    return;
  }

  materials.forEach(({ material }) => {
    if (!material.userData) material.userData = {};
    if (!material.userData.llmBaseEmissive && material.emissive?.clone) {
      material.userData.llmBaseEmissive = material.emissive.clone();
    }
    if (material.emissive?.set) {
      material.emissive.set(color);
      material.emissiveIntensity = normalized.appearance.outfit === 'formal_black' ? 0.04 : 0.09;
      material.needsUpdate = true;
    } else if (material.color?.set) {
      material.color.set(color);
      material.needsUpdate = true;
    }
  });
  diagnostics.degraded.push('appearance.mesh_swap_unavailable_material_tint_applied');
}

function applyGaze(head, intent, container) {
  const normalized = normalizeAvatarIntent(intent);
  if (normalized.gaze === 'camera') {
    head.lookAtCamera?.(500);
    return;
  }
  const rect = container?.getBoundingClientRect?.();
  const width = rect?.width || 800;
  const height = rect?.height || 600;
  if (normalized.gaze === 'left') head.lookAt?.(width * 0.32, height * 0.46, 500);
  else if (normalized.gaze === 'right') head.lookAt?.(width * 0.68, height * 0.46, 500);
  else if (normalized.gaze === 'down') head.lookAt?.(width * 0.5, height * 0.72, 500);
}

function applyOptionNode(head, node, diagnostics, container = null) {
  const option = safeId(node.option);
  try {
    if (node.target === 'camera' && node.id === 'camera.view' && AVATAR_CAMERA_VIEWS.includes(option)) {
      head.setView?.(option);
      diagnostics.applied.push('node:camera.view');
      return true;
    }
    if (node.target === 'pose' && node.id === 'motion.pose') {
      if (!option || option === 'auto') {
        diagnostics.applied.push('node:motion.pose:auto');
        return true;
      }
      head.playPose?.(option, null, Math.max(0.2, node.durationMs / 1000));
      diagnostics.applied.push('node:motion.pose');
      return true;
    }
    if (node.target === 'gesture' && node.id === 'gesture' && option) {
      const gesture = GESTURE_MAP[option] || option;
      if (!gesture) return true;
      head.playGesture?.(gesture, Math.max(0.2, node.durationMs / 1000), option === 'wave', node.transitionMs);
      diagnostics.applied.push('node:gesture');
      return true;
    }
    if (node.target === 'gesture' && node.id === 'mood' && option) {
      head.setMood?.(option);
      diagnostics.applied.push('node:mood');
      return true;
    }
    if (node.target === 'lighting' && node.id === 'stage.lighting' && AVATAR_LIGHTING.includes(option)) {
      head.setLighting?.(LIGHTING_PRESETS[option] || LIGHTING_PRESETS.neutral);
      diagnostics.applied.push('node:stage.lighting');
      return true;
    }
    if (node.target === 'stage' && node.id === 'stage.background' && AVATAR_BACKGROUNDS.includes(option)) {
      if (container) {
        Object.assign(container.style, BACKGROUND_STYLES[option] || BACKGROUND_STYLES.default);
      }
      diagnostics.applied.push('node:stage.background');
      return true;
    }
    if (node.target === 'wardrobe' && node.id.startsWith('appearance.')) {
      diagnostics.degraded.push(`node:${node.id}:handled_by_material_stage_proxy`);
      return true;
    }
  } catch (error) {
    diagnostics.unsupported.push(`node:${node.id}:${error instanceof Error ? error.message : String(error)}`);
    return true;
  }
  return false;
}

function applyNumericCameraNodes(head, nodes, intent, diagnostics) {
  const normalized = normalizeAvatarIntent(intent);
  const camera = { ...normalized.camera };
  let changed = false;
  nodes.forEach((node) => {
    if (node.id === 'camera.distance') {
      camera.distance = clamp(node.value * 6, -4, 6);
      changed = true;
    } else if (node.id === 'camera.x') {
      camera.x = clamp(node.value * 1.5, -1.5, 1.5);
      changed = true;
    } else if (node.id === 'camera.y') {
      camera.y = clamp(node.value * 1.5, -1.5, 1.5);
      changed = true;
    } else if (node.id === 'camera.rotateX') {
      camera.rotateX = clamp(node.value * 0.75, -0.75, 0.75);
      changed = true;
    } else if (node.id === 'camera.rotateY') {
      camera.rotateY = clamp(node.value * 0.75, -0.75, 0.75);
      changed = true;
    }
  });
  if (!changed) return false;
  head.setView?.(camera.view, {
    cameraDistance: camera.distance,
    cameraX: camera.x,
    cameraY: camera.y,
    cameraRotateX: camera.rotateX,
    cameraRotateY: camera.rotateY,
  });
  diagnostics.applied.push('node:camera.numeric');
  return true;
}

function propNameForBoneNode(node) {
  if (node.id.endsWith('.rotation') || node.id.endsWith('.position')) return node.id;
  if (node.id.endsWith('.quaternion')) return node.id.replace('.quaternion', '.rotation');
  return `${node.id}.rotation`;
}

function isCalibratedBoneProp(prop) {
  return FINGER_BONE_PATTERN.test(prop);
}

function applyBoneOverlay(head, nodes, diagnostics) {
  const props = {};
  const available = new Set(posePropKeys(head));

  nodes.forEach((node) => {
    const prop = propNameForBoneNode(node);
    if (!isCalibratedBoneProp(prop)) {
      diagnostics.degraded.push(`bone:${prop}:blocked_uncalibrated_absolute_pose`);
      return;
    }
    const runtimeProp = prop.endsWith('.rotation') ? prop.replace('.rotation', '.quaternion') : prop;
    if (!available.has(runtimeProp)) {
      diagnostics.unsupported.push(`bone:${prop}`);
      return;
    }
    const values = prop.endsWith('.position') ? node.position : node.rotation;
    props[prop] = {
      x: clamp(values[0] * node.weight, -0.8, 0.8),
      y: clamp(values[1] * node.weight, -0.8, 0.8),
      z: clamp(values[2] * node.weight, -0.8, 0.8),
    };
  });

  if (!Object.keys(props).length) return false;
  const name = '__llm_bone_overlay';
  head.gestureTemplates[name] = props;
  const durationMs = Math.max(...nodes.map((node) => node.durationMs || 0), 1000);
  const transitionMs = Math.max(...nodes.map((node) => node.transitionMs || 0), 120);
  try {
    head.playGesture?.(name, durationMs / 1000, false, transitionMs);
    diagnostics.applied.push(`bone_overlay:${Object.keys(props).length}`);
    return true;
  } catch (error) {
    diagnostics.unsupported.push(`bone_overlay:${error instanceof Error ? error.message : String(error)}`);
    return false;
  }
}

function applyMaterialNodes(head, nodes, intent, diagnostics) {
  const materials = materialsFromHead(head);
  const palette = PALETTE_COLORS[normalizeAvatarIntent(intent).appearance.palette] || PALETTE_COLORS.neutral;
  nodes.forEach((node) => {
    const index = Number(String(node.id).replace('material:', ''));
    const target = materials[index]?.material;
    if (!target) {
      diagnostics.unsupported.push(`material:${node.id}`);
      return;
    }
    if (target.emissive?.set) {
      target.emissive.set(palette);
      target.emissiveIntensity = clamp(Math.abs(node.value * node.weight) * 0.35, 0, 0.35);
      target.needsUpdate = true;
      diagnostics.applied.push(`material:${node.id}`);
    } else if (target.color?.set) {
      target.color.set(palette);
      target.needsUpdate = true;
      diagnostics.degraded.push(`material:${node.id}:color_tint`);
    } else {
      diagnostics.unsupported.push(`material:${node.id}:no_emissive`);
    }
  });
}

export function applyTalkingHeadBeat({ head, intent, container, state }) {
  const normalized = normalizeAvatarIntent(intent);
  const current = state || {};
  const diagnostics = { applied: [], degraded: [], unsupported: [] };

  const viewKey = cameraKey(normalized);
  if (current.cameraKey !== viewKey) {
    head.setView?.(normalized.camera.view, {
      cameraDistance: normalized.camera.distance,
      cameraX: normalized.camera.x,
      cameraY: normalized.camera.y,
      cameraRotateX: normalized.camera.rotateX,
      cameraRotateY: normalized.camera.rotateY,
    });
    current.cameraKey = viewKey;
    diagnostics.applied.push(`camera:${normalized.camera.view}`);
  }

  const lightKey = lightingKey(normalized);
  if (current.lightingKey !== lightKey) {
    head.setLighting?.(lightingForIntent(normalized));
    current.lightingKey = lightKey;
    diagnostics.applied.push(`lighting:${normalized.stage.lighting}`);
  }

  const mood = MOOD_MAP[normalized.mood] || normalized.mood;
  if (current.mood !== mood) {
    try {
      head.setMood?.(mood);
      current.mood = mood;
      diagnostics.applied.push(`mood:${mood}`);
    } catch {
      diagnostics.unsupported.push(`mood:${mood}`);
    }
  }

  if (normalized.motion.pose !== 'auto' && current.pose !== normalized.motion.pose) {
    try {
      head.playPose?.(normalized.motion.pose, null, 3.5);
      current.pose = normalized.motion.pose;
      diagnostics.applied.push(`pose:${normalized.motion.pose}`);
    } catch {
      diagnostics.unsupported.push(`pose:${normalized.motion.pose}`);
    }
  }

  try {
    applyGaze(head, normalized, container);
    diagnostics.applied.push(`gaze:${normalized.gaze}`);
  } catch {
    diagnostics.unsupported.push(`gaze:${normalized.gaze}`);
  }

  const gesture = GESTURE_MAP[normalized.gesture] || normalized.gesture;
  if (gesture && current.gesture !== gesture) {
    try {
      head.playGesture?.(
        gesture,
        1.4 + normalized.motion.gestureIntensity * 1.8,
        normalized.gesture === 'wave',
        250 + normalized.motion.gestureIntensity * 500,
      );
      current.gesture = gesture;
      diagnostics.applied.push(`gesture:${gesture}`);
    } catch {
      diagnostics.unsupported.push(`gesture:${gesture}`);
    }
  }

  const materialIntentKey = materialKey(normalized);
  if (current.materialKey !== materialIntentKey) {
    applyMaterialFallback(head, normalized, diagnostics);
    current.materialKey = materialIntentKey;
  }

  const optionNodes = normalized.nodes.filter((node) => (
    node.target === 'camera'
    || node.target === 'pose'
    || node.target === 'gesture'
    || node.target === 'lighting'
    || node.target === 'stage'
    || node.target === 'wardrobe'
  ));
  optionNodes.forEach((node) => {
    if (!applyOptionNode(head, node, diagnostics, container)) {
      if (node.target === 'camera' && node.id !== 'camera.view') return;
      diagnostics.unsupported.push(`${node.target}:${node.id}`);
    }
  });
  applyNumericCameraNodes(
    head,
    normalized.nodes.filter((node) => node.target === 'camera'),
    normalized,
    diagnostics,
  );

  applyBoneOverlay(
    head,
    normalized.nodes.filter((node) => (
      node.target === 'bone'
      || (node.target === 'dynamic_bone' && !['hair.bend', 'hair.sway'].includes(node.id))
    )),
    diagnostics,
  );
  applyMaterialNodes(
    head,
    normalized.nodes.filter((node) => node.target === 'material'),
    normalized,
    diagnostics,
  );

  current.lastDiagnostics = diagnostics;
  return diagnostics;
}

function expressionTargets(intent, mouthPulse, speaking = false, elapsedSeconds = 0) {
  const normalized = normalizeAvatarIntent(intent);
  const energy = normalized.voice.energy || 0;
  const mouth = speaking ? clamp(0.08 + energy * 0.34 + mouthPulse * 1.55, 0, 0.95) : 0;
  const brow = normalized.face.brow;
  const leftCurl = normalized.hands.leftFingerCurl;
  const rightCurl = normalized.hands.rightFingerCurl;
  const tempo = normalized.tempo;
  const bodyEnergy = normalized.motion.bodyMovement * (0.25 + energy * 0.35);
  const headEnergy = normalized.motion.headMovement * (0.25 + energy * 0.35);
  const speechEnergy = speaking ? 0.42 : 0.18;
  const breath = Math.sin(elapsedSeconds * tempo * 1.9) * bodyEnergy * speechEnergy;
  const sway = Math.sin(elapsedSeconds * tempo * 0.72 + normalized.hair.bend) * bodyEnergy;
  const counterSway = Math.cos(elapsedSeconds * tempo * 0.86 + normalized.face.brow) * bodyEnergy;
  const headNod = Math.sin(elapsedSeconds * tempo * (speaking ? 2.7 : 1.1)) * headEnergy * (speaking ? 0.85 : 0.35);
  const headTilt = Math.cos(elapsedSeconds * tempo * 1.35 + normalized.hair.bend) * headEnergy * 0.65;
  const speechPulse = mouthPulse * energy * normalized.motion.gestureIntensity * 0.35;
  return {
    lipSyncMouth: mouth,
    mouthSmile: clamp(normalized.face.smile + (speaking ? 0.04 : 0), 0, 1),
    browInnerUp: clamp(Math.max(0, brow), 0, 1),
    browDownLeft: clamp(Math.max(0, -brow), 0, 1),
    browDownRight: clamp(Math.max(0, -brow), 0, 1),
    handFistLeft: clamp(leftCurl * (1 - normalized.hands.openPalm * 0.35), 0, 1),
    handFistRight: clamp(rightCurl * (1 - normalized.hands.openPalm * 0.35), 0, 1),
    bodyRotateX: clamp((energy - 0.5) * 0.025 + breath * 0.024 + speechPulse * 0.018, -0.18, 0.18),
    bodyRotateY: clamp(normalized.hair.bend * 0.028 + sway * 0.024, -0.18, 0.18),
    bodyRotateZ: clamp(normalized.hair.bend * 0.018 + counterSway * 0.018, -0.18, 0.18),
    headRotateX: clamp((normalized.motion.headMovement - 0.5) * 0.026 + headNod * 0.032 + speechPulse * 0.018, -0.18, 0.18),
    headRotateY: clamp(sway * 0.025, -0.18, 0.18),
    headRotateZ: clamp(normalized.hair.bend * 0.022 + headTilt * 0.032, -0.18, 0.18),
    chestInhale: clamp(0.12 + energy * 0.14 + Math.max(0, breath) * 0.16 + (speaking ? mouthPulse * 0.08 : 0), 0, 0.55),
  };
}

function applyLipSyncTargets(head, mouth, diagnostics, visemeFrame = null) {
  const current = visemeFrame?.current || 'aa';
  const next = visemeFrame?.next || 'sil';
  const intensity = clamp(visemeFrame?.intensity ?? 1, 0, 1);
  const visemeWeights = {
    aa: 0,
    E: 0,
    I: 0,
    O: 0,
    U: 0,
    PP: 0,
    SS: 0,
    TH: 0,
    DD: 0,
    FF: 0,
    kk: 0,
    nn: 0,
    RR: 0,
    CH: 0,
    sil: 0,
  };
  if (Object.hasOwn(visemeWeights, current)) visemeWeights[current] += 0.78 * intensity;
  if (Object.hasOwn(visemeWeights, next)) visemeWeights[next] += 0.22 * intensity;
  const closed = Math.max(visemeWeights.PP, visemeWeights.FF, visemeWeights.sil);
  const round = Math.max(visemeWeights.O, visemeWeights.U);
  const wide = Math.max(visemeWeights.E, visemeWeights.I, visemeWeights.SS, visemeWeights.CH);
  const mouthTargets = [
    ['mouthOpen', mouth * (1 - closed * 0.75)],
    ['jawOpen', mouth * (0.58 + visemeWeights.aa * 0.34 + round * 0.18)],
    ['mouthPucker', round * mouth],
    ['mouthFunnel', round * mouth * 0.65],
    ['mouthPressLeft', closed * 0.75],
    ['mouthPressRight', closed * 0.75],
    ['mouthStretchLeft', wide * mouth * 0.55],
    ['mouthStretchRight', wide * mouth * 0.55],
    ['viseme_aa', visemeWeights.aa * mouth],
    ['viseme_E', visemeWeights.E * mouth],
    ['viseme_I', visemeWeights.I * mouth],
    ['viseme_O', visemeWeights.O * mouth],
    ['viseme_U', visemeWeights.U * mouth],
    ['viseme_PP', visemeWeights.PP * mouth],
    ['viseme_SS', visemeWeights.SS * mouth],
    ['viseme_TH', visemeWeights.TH * mouth],
    ['viseme_DD', visemeWeights.DD * mouth],
    ['viseme_FF', visemeWeights.FF * mouth],
    ['viseme_kk', visemeWeights.kk * mouth],
    ['viseme_nn', visemeWeights.nn * mouth],
    ['viseme_RR', visemeWeights.RR * mouth],
    ['viseme_CH', visemeWeights.CH * mouth],
  ];
  let applied = 0;
  mouthTargets.forEach(([name, value]) => {
    if (setMorphValue(head, name, value, diagnostics, { fixed: true, transitionMs: 55 })) {
      applied += 1;
    }
  });
  if (!applied) {
    diagnostics.unsupported.push('lips:no_mouth_or_viseme_targets');
  } else {
    diagnostics.applied.unshift(`lips:${current}:${applied}`);
  }
}

function applySemanticMorphNode(head, node, diagnostics) {
  const value = clamp(node.value * node.weight, -1, 1);
  let applied = 0;
  switch (node.id) {
  case 'face.smile':
    applied += setMorphValue(head, 'mouthSmile', clamp(value, 0, 1), diagnostics, { transitionMs: node.transitionMs || 90 }) ? 1 : 0;
    if (applied) diagnostics.applied.push('semantic:face.smile');
    else diagnostics.unsupported.push('semantic:face.smile');
    return true;
  case 'face.brow':
    applied += setMorphValue(head, 'browInnerUp', clamp(Math.max(0, value), 0, 1), diagnostics, { transitionMs: node.transitionMs || 90 }) ? 1 : 0;
    applied += setMorphValue(head, 'browDownLeft', clamp(Math.max(0, -value), 0, 1), diagnostics, { transitionMs: node.transitionMs || 90 }) ? 1 : 0;
    applied += setMorphValue(head, 'browDownRight', clamp(Math.max(0, -value), 0, 1), diagnostics, { transitionMs: node.transitionMs || 90 }) ? 1 : 0;
    if (applied) diagnostics.applied.push('semantic:face.brow');
    else diagnostics.unsupported.push('semantic:face.brow');
    return true;
  case 'hands.leftFingerCurl':
    applied += setMorphValue(head, 'handFistLeft', clamp(value, 0, 1), diagnostics, { transitionMs: node.transitionMs || 90 }) ? 1 : 0;
    if (applied) diagnostics.applied.push('semantic:hands.leftFingerCurl');
    else diagnostics.unsupported.push('semantic:hands.leftFingerCurl');
    return true;
  case 'hands.rightFingerCurl':
    applied += setMorphValue(head, 'handFistRight', clamp(value, 0, 1), diagnostics, { transitionMs: node.transitionMs || 90 }) ? 1 : 0;
    if (applied) diagnostics.applied.push('semantic:hands.rightFingerCurl');
    else diagnostics.unsupported.push('semantic:hands.rightFingerCurl');
    return true;
  case 'hands.openPalm':
    diagnostics.degraded.push('semantic:hands.openPalm:handled_by_finger_bone_curl');
    return true;
  case 'hair.bend':
    applied += setMorphValue(head, 'bodyRotateY', clamp(value * 0.16, -1, 1), diagnostics, { transitionMs: node.transitionMs || 90 }) ? 1 : 0;
    applied += setMorphValue(head, 'bodyRotateZ', clamp(value * 0.08, -1, 1), diagnostics, { transitionMs: node.transitionMs || 90 }) ? 1 : 0;
    applied += setMorphValue(head, 'headRotateZ', clamp(value * 0.12, -1, 1), diagnostics, { transitionMs: node.transitionMs || 90 }) ? 1 : 0;
    if (applied) diagnostics.degraded.push('semantic:hair.bend:head_body_proxy');
    else diagnostics.unsupported.push('semantic:hair.bend');
    return true;
  case 'hair.sway':
    applied += setMorphValue(head, 'bodyRotateX', clamp(value * 0.08, -1, 1), diagnostics, { transitionMs: node.transitionMs || 90 }) ? 1 : 0;
    applied += setMorphValue(head, 'headRotateX', clamp(value * 0.08, -1, 1), diagnostics, { transitionMs: node.transitionMs || 90 }) ? 1 : 0;
    if (applied) diagnostics.degraded.push('semantic:hair.sway:head_body_proxy');
    else diagnostics.unsupported.push('semantic:hair.sway');
    return true;
  case 'motion.bodyMovement':
    applied += setMorphValue(head, 'bodyRotateX', clamp(value * 0.14, -1, 1), diagnostics, { transitionMs: node.transitionMs || 90 }) ? 1 : 0;
    if (applied) diagnostics.applied.push('semantic:motion.bodyMovement');
    else diagnostics.unsupported.push('semantic:motion.bodyMovement');
    return true;
  case 'motion.headMovement':
    applied += setMorphValue(head, 'headRotateX', clamp(value * 0.14, -1, 1), diagnostics, { transitionMs: node.transitionMs || 90 }) ? 1 : 0;
    if (applied) diagnostics.applied.push('semantic:motion.headMovement');
    else diagnostics.unsupported.push('semantic:motion.headMovement');
    return true;
  default:
    return false;
  }
}

export function applyTalkingHeadFrame({
  head,
  intent,
  mouthPulse,
  speaking = false,
  visemeFrame = null,
  elapsedSeconds = 0,
}) {
  const normalized = normalizeAvatarIntent(intent);
  const diagnostics = { applied: [], degraded: [], unsupported: [] };
  const targets = expressionTargets(normalized, mouthPulse, speaking, elapsedSeconds);

  applyLipSyncTargets(head, targets.lipSyncMouth, diagnostics, visemeFrame);

  let bodyApplied = 0;
  Object.entries(targets).forEach(([name, value]) => {
    if (name === 'lipSyncMouth') return;
    const applied = setMorphValue(head, name, value, diagnostics);
    if (applied && (
      name.startsWith('bodyRotate')
      || name.startsWith('headRotate')
      || name === 'chestInhale'
      || name.startsWith('handFist')
    )) {
      bodyApplied += 1;
    }
  });
  if (bodyApplied) {
    diagnostics.applied.unshift(`body_motion:${bodyApplied}`);
  }

  for (const node of normalized.nodes || []) {
    if (node.target !== 'morph') continue;
    if (applySemanticMorphNode(head, node, diagnostics)) continue;
    setMorphValue(head, node.id, node.value * node.weight, diagnostics, {
      transitionMs: node.transitionMs || 90,
    });
  }

  for (const node of normalized.nodes || []) {
    if (node.target !== 'dynamic_bone') continue;
    applySemanticMorphNode(head, node, diagnostics);
  }

  if (!normalized.nodes.some((node) => node.target === 'dynamic_bone')) {
    diagnostics.degraded.push('hair.dynamic_bone_proxy_via_head_body_motion');
  }
  return diagnostics;
}
