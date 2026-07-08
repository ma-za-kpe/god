import test from 'node:test';
import assert from 'node:assert/strict';

import {
  BODY_MOTION_SOURCE,
  POSE_STREAM_SOURCE,
  buildAlphabetBodyMotionPlan,
  normalizeBodyMotionPlan,
  normalizeMotionCommand,
  normalizePoseStream,
  resolveBodyMotionPlan,
  sampleBodyMotionPlan,
  samplePoseStream,
} from '../src/avatarMotion.js';

test('builds an AI4AnimationPy-targeted alphabet body motion plan', () => {
  const plan = buildAlphabetBodyMotionPlan({
    agentId: 's-alpha',
    line: 'A B C D E F G.',
    durationSeconds: 5,
    speaking: true,
  });

  assert.equal(plan.source, BODY_MOTION_SOURCE);
  assert.equal(plan.target_runtime, 'ai4animationpy');
  assert.equal(plan.agent_id, 's-alpha');
  assert.ok(plan.commands.some((command) => command.type === 'walk_to'));
  assert.ok(plan.commands.some((command) => command.name === 'counting_left_hand'));
  assert.ok(plan.pose_stream_contract.includes('joint_rotations'));
});

test('normalizes and clamps body motion commands', () => {
  const command = normalizeMotionCommand({
    type: 'walk_to',
    at_ms: -10,
    duration_ms: 10,
    x: 9,
    z: -9,
  });

  assert.equal(command.atMs, 0);
  assert.equal(command.durationMs, 250);
  assert.equal(command.x, 4.2);
  assert.equal(command.z, -2.8);
  assert.equal(normalizeMotionCommand({ type: 'gesture', name: 'unknown' }), null);
  assert.equal(normalizeMotionCommand({ type: 'run_to', x: 0.5, z: 0.2 }).type, 'run_to');
  assert.equal(normalizeMotionCommand({ type: 'pose', name: 'sit' }).name, 'sit');
  assert.equal(normalizeMotionCommand({ type: 'expression', name: 'smile', intensity: 2 }).intensity, 1);
  assert.equal(normalizeMotionCommand({ type: 'expression', name: 'mouth_open' }).name, 'mouth_open');
});

test('samples root movement and gesture rotations from the motion plan', () => {
  const raw = buildAlphabetBodyMotionPlan({ durationSeconds: 6, speaking: true });
  const plan = normalizeBodyMotionPlan(raw);
  const sample = sampleBodyMotionPlan(plan, 1.25);

  assert.equal(sample.source, BODY_MOTION_SOURCE);
  assert.equal(sample.targetRuntime, 'ai4animationpy');
  assert.ok(Math.abs(sample.root.position[0]) > 0.001);
  assert.ok(Math.abs(sample.joints.leftUpperArm[0]) > 0 || Math.abs(sample.joints.rightUpperArm[0]) > 0);
  assert.ok(typeof sample.contacts.leftFoot === 'boolean');
});

test('blocks empty plans instead of inventing fallback motion', () => {
  const plan = normalizeBodyMotionPlan({ root_start: [0.4, -0.3] }, { speaking: false, line: '' });
  const sample = sampleBodyMotionPlan(plan, 0.5);

  assert.equal(plan.status, 'blocked');
  assert.equal(plan.commands.length, 0);
  assert.equal(sample.gestureLabel, 'blocked');
  assert.equal(sample.source, BODY_MOTION_SOURCE);
  assert.deepEqual(sample.root.position, [0.4, 0, -0.3]);
  assert.equal(sample.expression.mouthOpen, 0);
});

test('normalizes model-authored avatar control plans without choosing actions', () => {
  const plan = normalizeBodyMotionPlan(modelPlan('inspect_plant', [
    { type: 'walk_to', at_ms: 0, duration_ms: 1400, x: -1.2, z: 0.8 },
    { type: 'turn_to', at_ms: 1300, duration_ms: 450, yaw_degrees: -35 },
    { type: 'gesture', at_ms: 1500, duration_ms: 900, name: 'point' },
    { type: 'expression', at_ms: 1500, duration_ms: 700, name: 'focus', intensity: 0.7 },
  ]));

  assert.equal(plan.provider, 'ollama:llama3.1:8b');
  assert.equal(plan.controlLabel, 'inspect_plant');
  assert.equal(plan.commands[0].type, 'walk_to');
  assert.equal(plan.commands[1].type, 'turn_to');
  assert.equal(plan.commands[2].name, 'point');
  assert.equal(plan.commands[3].name, 'focus');
});

test('samples model-authored root, pose, head, face, and mouth controls into rig state', () => {
  const runSample = sampleBodyMotionPlan(modelPlan('run_across_room', [
    { type: 'run_to', at_ms: 0, duration_ms: 950, x: 1.2, z: -0.2 },
  ]), 0.5);
  const sitSample = sampleBodyMotionPlan(modelPlan('sit_near_chair', [
    { type: 'pose', at_ms: 0, duration_ms: 900, name: 'sit' },
  ]), 1.2);
  const shakeSample = sampleBodyMotionPlan(modelPlan('disagree', [
    { type: 'gesture', at_ms: 0, duration_ms: 1300, name: 'shake_head' },
  ]), 0.55);
  const smileSample = sampleBodyMotionPlan(modelPlan('smile', [
    { type: 'expression', at_ms: 0, duration_ms: 1500, name: 'smile', intensity: 1 },
  ]), 0.6);
  const mouthSample = sampleBodyMotionPlan(modelPlan('open_mouth', [
    { type: 'expression', at_ms: 0, duration_ms: 1250, name: 'mouth_open', intensity: 1 },
  ]), 0.55);
  const lookLeftSample = sampleBodyMotionPlan(modelPlan('look_to_window', [
    { type: 'look_at', at_ms: 0, duration_ms: 1200, target: 'left' },
  ]), 0.4);
  const walkSample = sampleBodyMotionPlan(modelPlan('walk_to_plant', [
    { type: 'walk_to', at_ms: 0, duration_ms: 1100, x: -0.6, z: 0.18 },
  ]), 0.6);

  assert.equal(runSample.gestureLabel, 'run_across_room');
  assert.ok(Math.abs(runSample.root.position[0]) > 0.1);
  assert.ok(Math.abs(runSample.joints.leftUpperLeg[0]) > 0.1);
  assert.equal(walkSample.gestureLabel, 'walk_to_plant');
  assert.ok(Math.abs(walkSample.root.position[0]) > 0.05);
  assert.equal(sitSample.gestureLabel, 'sit_near_chair');
  assert.ok(sitSample.root.position[1] < -0.25);
  assert.ok(sitSample.joints.leftUpperLeg[0] > 0.7);
  assert.equal(shakeSample.gestureLabel, 'disagree');
  assert.ok(Math.abs(shakeSample.joints.head[1]) > 0.01);
  assert.ok(smileSample.expression.smile > 0.1);
  assert.ok(smileSample.expression.mouthOpen > 0.01);
  assert.ok(mouthSample.expression.mouthOpen > 0.2);
  assert.ok(lookLeftSample.joints.head[1] > 0.1);
});

test('uses model plan root_start as the locomotion anchor across plan windows', () => {
  const plan = normalizeBodyMotionPlan({
    ...modelPlan('continue_from_window', [
      { type: 'walk_to', at_ms: 0, duration_ms: 1000, x: 1.4, z: -0.2 },
    ]),
    root_start: [-1.2, 0.8],
  });
  const startSample = sampleBodyMotionPlan(plan, 0);
  const midSample = sampleBodyMotionPlan(plan, 0.5);
  const endSample = sampleBodyMotionPlan(plan, 1.2);

  assert.deepEqual(plan.rootStart, [-1.2, 0.8]);
  assert.equal(startSample.root.position[0], -1.2);
  assert.equal(startSample.root.position[2], 0.8);
  assert.ok(midSample.root.position[0] > -1.2);
  assert.ok(midSample.root.position[0] < 1.4);
  assert.ok(Math.abs(endSample.root.position[0] - 1.4) < 0.000001);
  assert.ok(Math.abs(endSample.root.position[2] + 0.2) < 0.000001);
});

test('does not upgrade stale idle plans into generated movement', () => {
  const idle = buildAlphabetBodyMotionPlan({ speaking: false });
  const plan = resolveBodyMotionPlan(idle, {
    speaking: true,
    action: 'wave',
    durationSeconds: 4,
  });

  assert.equal(plan.status, 'idle');
  assert.equal(plan.provider, 'god-deterministic-motion-contract');
  assert.ok(plan.commands.some((command) => command.name === 'idle_shift'));
});

test('normalizes and samples AI4AnimationPy-style pose streams', () => {
  const stream = {
    source: POSE_STREAM_SOURCE,
    target_runtime: 'ai4animationpy',
    duration_seconds: 1,
    frames: [
      poseFrame(0, [1, 0.8, -1], {
        Head: [0, 0, 0, 1],
        LeftArm: [0, 0, 0, 1],
      }),
      poseFrame(1000, [1.4, 0.9, -1.2], {
        Head: [0, 0.2, 0, 0.98],
        LeftArm: [0.707, 0, 0, 0.707],
        RightArm: [0, 0.2, 0, 0.98],
      }),
    ],
  };

  const normalized = normalizePoseStream(stream);
  const sample = samplePoseStream(normalized, 0.75);

  assert.equal(normalized.source, POSE_STREAM_SOURCE);
  assert.equal(sample.source, POSE_STREAM_SOURCE);
  assert.equal(sample.targetRuntime, 'ai4animationpy');
  assert.ok(sample.root.position[0] > 0.2);
  assert.ok(sample.root.position[2] < -0.1);
  assert.ok(Math.abs(sample.joints.leftUpperArm[0]) > 0.3);
  assert.ok(Math.abs(sample.joints.rightUpperArm[1]) > 0.05);
});

test('pose stream root rotation preserves 180-degree yaw without rolling avatar', () => {
  const normalized = normalizePoseStream({
    frames: [
      poseFrame(0, [0, 0, 0], { Spine: [0, 0, 0, 1] }, [0, 1, 0, 0]),
      poseFrame(1000, [0, 0, 0.1], { Spine: [0, 0, 0, 1] }, [0, 1, 0, 0]),
    ],
  });
  const sample = samplePoseStream(normalized, 0.5);

  assert.equal(sample.root.rotation[0], 0);
  assert.ok(Math.abs(Math.abs(sample.root.rotation[1]) - Math.PI) < 0.000001);
  assert.equal(sample.root.rotation[2], 0);
});

test('body motion sampler consumes pose streams instead of command fallback', () => {
  const plan = normalizeBodyMotionPlan({
    source: POSE_STREAM_SOURCE,
    target_runtime: 'ai4animationpy',
    root_start: [1.2, -0.6],
    control_label: 'inspect_window',
    commands: [
      { type: 'expression', at_ms: 0, duration_ms: 1000, name: 'smile', intensity: 1 },
    ],
    pose_stream: {
      frames: [
        poseFrame(0, [0, 0, 0], { Spine: [0, 0, 0, 1] }),
        poseFrame(500, [0.3, 0, 0], { Spine: [0.2, 0, 0, 0.98] }),
      ],
    },
  });
  const sample = sampleBodyMotionPlan(plan, 0.5);

  assert.equal(plan.commands.length, 1);
  assert.equal(sample.source, POSE_STREAM_SOURCE);
  assert.ok(sample.root.position[0] > 1.45);
  assert.ok(sample.root.position[2] < -0.55);
  assert.ok(Math.abs(sample.joints.spine[0]) > 0.1);
  assert.ok(sample.expression.smile > 0.9);
  assert.ok(sample.expression.mouthOpen > 0.2);
  assert.equal(sample.gestureLabel, 'inspect_window');
});

test('pose streams reject non-monotonic frames and reuse normalized streams', () => {
  const invalid = normalizePoseStream({
    frames: [
      poseFrame(100, [0, 0, 0], { Spine: [0, 0, 0, 1] }),
      poseFrame(90, [0.1, 0, 0], { Spine: [0, 0, 0, 1] }),
    ],
  });
  assert.equal(invalid, null);

  const normalized = normalizePoseStream({
    frames: [
      poseFrame(0, [0, 0, 0], { Spine: [0, 0, 0, 1] }),
      poseFrame(100, [0.1, 0, 0], { Spine: [0.1, 0, 0, 1] }),
    ],
  });
  assert.equal(normalizePoseStream(normalized), normalized);
  assert.ok(samplePoseStream(normalized, 0.1).root.position[0] > 0.09);
});

function poseFrame(timestampMs, rootPosition, jointRotations, rootRotation = [0, 0, 0, 1]) {
  return {
    timestamp_ms: timestampMs,
    root_position: rootPosition,
    root_rotation: rootRotation,
    joint_rotations: jointRotations,
    contacts: { LeftFoot: true, RightFoot: timestampMs > 0 },
    gesture_label: 'motion_import',
  };
}

function modelPlan(controlLabel, commands) {
  return {
    schema_version: 1,
    source: 'ollama-llm-avatar-control',
    provider: 'ollama:llama3.1:8b',
    target_runtime: 'ai4animationpy',
    execution_mode: 'Manual',
    status: 'ready',
    agent_id: 'local-vrm-agent-001',
    duration_seconds: 4,
    control_label: controlLabel,
    commands,
  };
}
