import test from 'node:test';
import assert from 'node:assert/strict';

import {
  AVATAR_PROMPT_SYSTEM,
  buildAvatarIntentMessages,
  buildOllamaAvatarRequest,
  firstJsonObject,
  parseAvatarIntentResponse,
} from '../src/avatarPrompt.js';

test('builds a grounded prompt with allowed values and renderer nodes', () => {
  const messages = buildAvatarIntentMessages({
    line: 'Explain the node registry.',
    previousIntent: { voice: { line: 'previous' } },
    nodeRegistry: [{ id: 'mouthOpen', target: 'morph' }, { id: 'eyeBlinkLeft', target: 'morph' }],
  });

  assert.equal(messages[0].role, 'system');
  assert.equal(messages[0].content, AVATAR_PROMPT_SYSTEM);
  assert.equal(messages[1].role, 'user');
  assert.match(messages[1].content, /Allowed moods:/);
  assert.match(messages[1].content, /Allowed outfits:/);
  assert.match(messages[1].content, /Allowed camera views: full, mid, upper, head/);
  assert.match(messages[1].content, /Renderer nodes: \[\{"id":"mouthOpen","target":"morph"\},\{"id":"eyeBlinkLeft","target":"morph"\}\]/);
  assert.match(messages[1].content, /Required JSON shape:/);
  assert.match(messages[0].content, /choose camera\.view full/i);
  assert.match(messages[1].content, /whole-avatar node control, choose camera\.view full/i);
});

test('uses Ollama JSON mode with bounded generation options', () => {
  const request = buildOllamaAvatarRequest({
    model: 'llama3.1:8b',
    messages: [{ role: 'user', content: 'x' }],
  });

  assert.equal(request.model, 'llama3.1:8b');
  assert.equal(request.format, 'json');
  assert.equal(request.stream, false);
  assert.ok(request.options.num_predict > 0);
  assert.ok(request.options.num_predict <= 800);
});

test('extracts and normalizes an avatar intent response', () => {
  const payload = {
    message: {
      content: '```json\n{"mood":"happy","voice":{"line":"hello","energy":2},"nodes":[{"id":"mouthOpen","target":"morph","value":2}]}\n```',
    },
  };

  const intent = parseAvatarIntentResponse(payload);

  assert.equal(intent.mood, 'happy');
  assert.equal(intent.voice.line, 'hello');
  assert.equal(intent.voice.energy, 1);
  assert.equal(intent.nodes[0].id, 'mouthOpen');
  assert.equal(intent.nodes[0].value, 1);
});

test('can recover a requested line when valid JSON omits the line', () => {
  const intent = parseAvatarIntentResponse(
    { message: { content: '{"mood":"neutral","voice":{"energy":0.4}}' } },
    { requestedLine: 'Use my exact line.' },
  );

  assert.equal(intent.voice.line, 'Use my exact line.');
});

test('repairs safe bone shorthand and drops unknown renderer nodes', () => {
  const intent = parseAvatarIntentResponse(
    {
      message: {
        content: JSON.stringify({
          voice: { line: 'Make a fist.' },
          nodes: [
            { id: 'LeftHandIndex1', target: 'bone', rotation: [0.4, 0, 0] },
            { id: 'Camera:0', target: 'camera', value: 1 },
          ],
        }),
      },
    },
    {
      nodeRegistry: [
        { id: 'LeftHandIndex1.rotation', target: 'bone' },
        { id: 'camera.view', target: 'camera' },
      ],
    },
  );

  assert.equal(intent.nodes.length, 1);
  assert.equal(intent.nodes[0].id, 'LeftHandIndex1.rotation');
  assert.equal(intent.nodes[0].target, 'bone');
});

test('finds the first JSON object inside model chatter', () => {
  assert.equal(firstJsonObject('text {"ok":true} end'), '{"ok":true}');
  assert.equal(firstJsonObject(''), null);
});
