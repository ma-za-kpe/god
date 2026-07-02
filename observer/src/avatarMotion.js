export const BODY_MOTION_SOURCE = 'ai4animationpy-contract';

const ALLOWED_COMMANDS = new Set(['idle', 'look_at', 'walk_to', 'turn_to', 'gesture', 'dance']);
const ALLOWED_GESTURES = new Set([
  'introduce',
  'counting_left_hand',
  'emphasis_right_hand',
  'alphabet_sweep',
  'idle_shift',
]);

function clamp(value, lower, upper) {
  return Math.max(lower, Math.min(upper, value));
}

function number(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function smoothstep(value) {
  const x = clamp(value, 0, 1);
  return x * x * (3 - 2 * x);
}

function emptyJoints() {
  return {
    spine: [0, 0, 0],
    chest: [0, 0, 0],
    neck: [0, 0, 0],
    head: [0, 0, 0],
    leftUpperArm: [0, 0, 0],
    leftLowerArm: [0, 0, 0],
    rightUpperArm: [0, 0, 0],
    rightLowerArm: [0, 0, 0],
    leftUpperLeg: [0, 0, 0],
    rightUpperLeg: [0, 0, 0],
  };
}

function addRotation(target, name, rotation, weight = 1) {
  const current = target[name] || [0, 0, 0];
  target[name] = [
    current[0] + rotation[0] * weight,
    current[1] + rotation[1] * weight,
    current[2] + rotation[2] * weight,
  ];
}

export function normalizeMotionCommand(raw = {}) {
  const type = String(raw.type || '').trim().toLowerCase();
  if (!ALLOWED_COMMANDS.has(type)) return null;
  const atMs = clamp(Math.round(number(raw.at_ms ?? raw.atMs, 0)), 0, 120000);
  const durationDefault = ['walk_to', 'gesture', 'dance'].includes(type) ? 900 : 0;
  const durationMs = clamp(
    Math.round(number(raw.duration_ms ?? raw.durationMs, durationDefault)),
    0,
    30000
  );

  if (type === 'walk_to') {
    return {
      type,
      atMs,
      durationMs: Math.max(250, durationMs),
      x: clamp(number(raw.x), -2.5, 2.5),
      z: clamp(number(raw.z), -2.5, 2.5),
    };
  }
  if (type === 'turn_to') {
    return {
      type,
      atMs,
      durationMs: Math.max(150, durationMs),
      yawDegrees: clamp(number(raw.yaw_degrees ?? raw.yawDegrees), -180, 180),
    };
  }
  if (type === 'look_at') {
    return {
      type,
      atMs,
      durationMs,
      target: String(raw.target || 'camera').trim().toLowerCase(),
    };
  }
  if (type === 'gesture' || type === 'dance') {
    const name = String(raw.name || (type === 'dance' ? 'alphabet_sweep' : '')).trim();
    if (!ALLOWED_GESTURES.has(name)) return null;
    return { type, atMs, durationMs: Math.max(250, durationMs), name };
  }
  return { type, atMs, durationMs };
}

function safeDurationSeconds(value, line = '') {
  const parsed = number(value, 0);
  if (parsed > 0) return clamp(parsed, 1, 120);
  const letters = String(line || '').toUpperCase().match(/[A-Z]/g) || [];
  return Math.max(3.8, (letters.length || 26) * 0.14);
}

export function buildAlphabetBodyMotionPlan({
  agentId = '',
  line = '',
  durationSeconds = 0,
  speaking = true,
} = {}) {
  const duration = safeDurationSeconds(durationSeconds, line);
  const durationMs = Math.round(duration * 1000);
  if (!speaking) {
    return {
      schema_version: 1,
      source: BODY_MOTION_SOURCE,
      provider: 'god-deterministic-motion-contract',
      target_runtime: 'ai4animationpy',
      status: 'idle',
      agent_id: agentId,
      duration_seconds: duration,
      commands: [
        { type: 'look_at', at_ms: 0, target: 'camera' },
        { type: 'gesture', at_ms: 0, duration_ms: 1200, name: 'idle_shift' },
      ],
    };
  }
  return {
    schema_version: 1,
    source: BODY_MOTION_SOURCE,
    provider: 'god-deterministic-motion-contract',
    target_runtime: 'ai4animationpy',
    status: 'ready',
    agent_id: agentId,
    duration_seconds: duration,
    pose_stream_contract: [
      'timestamp_ms',
      'root_position',
      'root_rotation',
      'joint_rotations',
      'contacts',
      'gesture_label',
    ],
    commands: [
      { type: 'look_at', at_ms: 0, target: 'camera' },
      { type: 'gesture', at_ms: 120, duration_ms: 900, name: 'introduce' },
      { type: 'walk_to', at_ms: 650, duration_ms: 1300, x: -0.34, z: 0 },
      {
        type: 'gesture',
        at_ms: Math.max(900, Math.round(durationMs * 0.28)),
        duration_ms: 1500,
        name: 'counting_left_hand',
      },
      {
        type: 'walk_to',
        at_ms: Math.max(1800, Math.round(durationMs * 0.48)),
        duration_ms: 1400,
        x: 0.34,
        z: 0,
      },
      {
        type: 'gesture',
        at_ms: Math.max(2200, Math.round(durationMs * 0.58)),
        duration_ms: 1200,
        name: 'emphasis_right_hand',
      },
      {
        type: 'turn_to',
        at_ms: Math.max(2600, Math.round(durationMs * 0.68)),
        duration_ms: 900,
        yaw_degrees: 8,
      },
      {
        type: 'dance',
        at_ms: Math.max(3000, Math.round(durationMs * 0.76)),
        duration_ms: Math.max(800, Math.min(1800, Math.round(durationMs / 5))),
        name: 'alphabet_sweep',
      },
      {
        type: 'walk_to',
        at_ms: Math.max(3400, Math.round(durationMs * 0.84)),
        duration_ms: 1000,
        x: 0,
        z: 0,
      },
    ],
  };
}

export function normalizeBodyMotionPlan(raw = {}, fallback = {}) {
  const plan = raw && typeof raw === 'object' ? raw : {};
  const commands = Array.isArray(plan.commands)
    ? plan.commands.map((command) => normalizeMotionCommand(command)).filter(Boolean)
    : [];
  if (!commands.length) {
    return normalizeBodyMotionPlan(buildAlphabetBodyMotionPlan(fallback));
  }
  return {
    schemaVersion: Number(plan.schema_version || plan.schemaVersion || 1),
    source: String(plan.source || BODY_MOTION_SOURCE),
    provider: String(plan.provider || 'external'),
    targetRuntime: String(plan.target_runtime || plan.targetRuntime || 'ai4animationpy'),
    status: String(plan.status || 'ready'),
    agentId: String(plan.agent_id || plan.agentId || fallback.agentId || ''),
    durationSeconds: safeDurationSeconds(plan.duration_seconds ?? plan.durationSeconds, fallback.line || ''),
    commands: commands.sort((left, right) => left.atMs - right.atMs),
  };
}

export function resolveBodyMotionPlan(raw = {}, fallback = {}) {
  const candidate = raw && typeof raw === 'object' ? raw : {};
  const status = String(candidate.status || '').toLowerCase();
  if (fallback.speaking && status === 'idle') {
    return normalizeBodyMotionPlan({}, fallback);
  }
  return normalizeBodyMotionPlan(candidate, fallback);
}

function gesturePose(name, progress, wave) {
  const joints = emptyJoints();
  if (name === 'introduce') {
    addRotation(joints, 'rightUpperArm', [-0.75, -0.2, -0.58], wave);
    addRotation(joints, 'rightLowerArm', [-0.52, 0.08, 0.16], wave);
    addRotation(joints, 'chest', [0.05, -0.08, 0.04], wave);
  } else if (name === 'counting_left_hand') {
    addRotation(joints, 'leftUpperArm', [-0.82, 0.26, 0.48], wave);
    addRotation(joints, 'leftLowerArm', [-0.35 - Math.sin(progress * Math.PI * 6) * 0.22, 0, -0.12], wave);
    addRotation(joints, 'head', [0.02, -0.08, 0.02], wave);
  } else if (name === 'emphasis_right_hand') {
    addRotation(joints, 'rightUpperArm', [-1.0, -0.1, -0.36], wave);
    addRotation(joints, 'rightLowerArm', [-0.5 + Math.sin(progress * Math.PI * 4) * 0.18, 0.05, 0.2], wave);
    addRotation(joints, 'spine', [0.02, 0.1, -0.04], wave);
  } else if (name === 'alphabet_sweep') {
    addRotation(joints, 'leftUpperArm', [-0.7, 0.25, 0.62], wave);
    addRotation(joints, 'rightUpperArm', [-0.7, -0.25, -0.62], wave);
    addRotation(joints, 'leftLowerArm', [-0.26, 0, -0.18], wave);
    addRotation(joints, 'rightLowerArm', [-0.26, 0, 0.18], wave);
    addRotation(joints, 'spine', [0.03, Math.sin(progress * Math.PI * 2) * 0.18, 0], wave);
  } else if (name === 'idle_shift') {
    addRotation(joints, 'spine', [0.02, 0, 0.04], wave);
    addRotation(joints, 'head', [0.01, 0.05, -0.03], wave);
  }
  return joints;
}

function applyGesture(target, name, progress) {
  const wave = Math.sin(clamp(progress, 0, 1) * Math.PI);
  const pose = gesturePose(name, progress, wave);
  for (const [joint, rotation] of Object.entries(pose)) {
    addRotation(target, joint, rotation, 1);
  }
}

export function sampleBodyMotionPlan(rawPlan, elapsedSeconds = 0) {
  const plan = normalizeBodyMotionPlan(rawPlan);
  const durationMs = Math.max(1, Math.round(plan.durationSeconds * 1000));
  const tMs = clamp(Math.round(number(elapsedSeconds, 0) * 1000), 0, durationMs);
  const t = tMs / 1000;
  const rootPosition = [0, 0, 0];
  const rootRotation = [0, 0, 0];
  const joints = emptyJoints();
  const contacts = { leftFoot: true, rightFoot: true };
  let gestureLabel = plan.status === 'idle' ? 'idle_shift' : 'stage_blocking';

  const speakSway = plan.status === 'idle' ? 0.35 : 1;
  rootPosition[1] += Math.sin(t * 5.2) * 0.025 * speakSway;
  rootRotation[2] += Math.sin(t * 2.2) * 0.025 * speakSway;
  addRotation(joints, 'spine', [Math.sin(t * 2.1) * 0.018, Math.sin(t * 1.4) * 0.04, 0], 1);
  addRotation(joints, 'head', [Math.sin(t * 1.7) * 0.025, Math.sin(t * 1.1) * 0.055, 0], 1);

  for (const command of plan.commands) {
    const progress = command.durationMs > 0 ? (tMs - command.atMs) / command.durationMs : (tMs >= command.atMs ? 1 : 0);
    if (progress < 0) continue;
    const eased = smoothstep(progress);
    if (command.type === 'walk_to') {
      rootPosition[0] = command.x * eased;
      rootPosition[2] = command.z * eased;
      const step = Math.sin(eased * Math.PI * 4);
      addRotation(joints, 'leftUpperLeg', [step * 0.34, 0, 0], 1);
      addRotation(joints, 'rightUpperLeg', [-step * 0.34, 0, 0], 1);
      addRotation(joints, 'leftUpperArm', [-step * 0.16, 0, 0.1], 1);
      addRotation(joints, 'rightUpperArm', [step * 0.16, 0, -0.1], 1);
      contacts.leftFoot = step <= 0.2;
      contacts.rightFoot = step >= -0.2;
      gestureLabel = 'walk_to';
    } else if (command.type === 'turn_to') {
      rootRotation[1] = (command.yawDegrees * Math.PI / 180) * eased;
      gestureLabel = 'turn_to';
    } else if (command.type === 'look_at') {
      addRotation(joints, 'head', [0, command.target === 'camera' ? 0 : 0.12, 0], 1);
    } else if ((command.type === 'gesture' || command.type === 'dance') && progress <= 1) {
      applyGesture(joints, command.name, progress);
      gestureLabel = command.name;
    }
  }

  return {
    schemaVersion: plan.schemaVersion,
    source: plan.source,
    provider: plan.provider,
    targetRuntime: plan.targetRuntime,
    timestampMs: tMs,
    root: {
      position: rootPosition,
      rotation: rootRotation,
    },
    joints,
    contacts,
    gestureLabel,
  };
}
