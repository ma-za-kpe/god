import test from 'node:test';
import assert from 'node:assert/strict';

import { buildMorphChannels, summarizeAnatomyMilestone } from '../src/anatomyMilestone.js';

test('summarizes anatomy milestone graph evidence for the browser morph gate', () => {
  const summary = summarizeAnatomyMilestone({
    milestone: 'M01',
    status: 'complete',
    summary: {
      node_count: 21,
      edge_count: 23,
      llm_handle_count: 5,
      working_set_node_count: 3,
    },
    nodes: [
      { id: 'skin:forehead', kind: 'skin' },
      { id: 'render:forehead_sweat_proxy', kind: 'render_proxy' },
      { id: 'population:scalp_hair_follicles', kind: 'population_template' },
    ],
    llm_registry: [
      { id: 'skin:forehead', control_channels: ['sweat'] },
    ],
  });

  assert.equal(summary.milestone, 'M01');
  assert.equal(summary.nodeCount, 21);
  assert.equal(summary.edgeCount, 23);
  assert.equal(summary.llmHandleCount, 5);
  assert.equal(summary.workingSetNodeCount, 3);
  assert.equal(summary.hasForeheadSkin, true);
  assert.equal(summary.hasSweatProxy, true);
  assert.equal(summary.hasHairPopulation, true);
});

test('builds visible morph channels from sourced anatomy graph features', () => {
  const channels = buildMorphChannels({
    nodeCount: 21,
    workingSetNodeCount: 3,
    llmHandleCount: 5,
    hasForeheadSkin: true,
    hasSweatProxy: true,
    hasHairPopulation: true,
  });

  assert.equal(channels.headTiltDegrees, 7);
  assert.equal(channels.sweatPulse, 0.5);
  assert.equal(channels.hairSway, 0.625);
  assert.equal(channels.bodyScale > 1, true);
  assert.equal(channels.registryReach > 0, true);
});
