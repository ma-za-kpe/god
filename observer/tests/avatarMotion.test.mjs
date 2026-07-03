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
  assert.equal(command.x, 2.5);
  assert.equal(command.z, -2.5);
  assert.equal(normalizeMotionCommand({ type: 'gesture', name: 'unknown' }), null);
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

test('falls back to deterministic idle motion when no commands are present', () => {
  const plan = normalizeBodyMotionPlan({}, { speaking: false, line: '' });
  const sample = sampleBodyMotionPlan(plan, 0.5);

  assert.equal(plan.status, 'idle');
  assert.equal(sample.gestureLabel, 'idle_shift');
  assert.equal(sample.source, BODY_MOTION_SOURCE);
});

test('upgrades stale idle runtime plans when browser speech is active', () => {
  const idle = buildAlphabetBodyMotionPlan({ speaking: false });
  const plan = resolveBodyMotionPlan(idle, {
    speaking: true,
    line: 'A B C D.',
    durationSeconds: 4,
  });

  assert.equal(plan.status, 'ready');
  assert.ok(plan.commands.some((command) => command.type === 'walk_to'));
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

test('body motion sampler consumes pose streams instead of command fallback', () => {
  const plan = normalizeBodyMotionPlan({
    source: POSE_STREAM_SOURCE,
    target_runtime: 'ai4animationpy',
    pose_stream: {
      frames: [
        poseFrame(0, [0, 0, 0], { Spine: [0, 0, 0, 1] }),
        poseFrame(500, [0.3, 0, 0], { Spine: [0.2, 0, 0, 0.98] }),
      ],
    },
  });
  const sample = sampleBodyMotionPlan(plan, 0.5);

  assert.equal(plan.commands.length, 0);
  assert.equal(sample.source, POSE_STREAM_SOURCE);
  assert.ok(sample.root.position[0] > 0.25);
  assert.ok(Math.abs(sample.joints.spine[0]) > 0.1);
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

function poseFrame(timestampMs, rootPosition, jointRotations) {
  return {
    timestamp_ms: timestampMs,
    root_position: rootPosition,
    root_rotation: [0, 0, 0, 1],
    joint_rotations: jointRotations,
    contacts: { LeftFoot: true, RightFoot: timestampMs > 0 },
    gesture_label: 'motion_import',
  };
}
