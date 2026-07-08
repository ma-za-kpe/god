import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildMorphChannels,
  getAnatomyRenderProjection,
  summarizeAnatomyMilestone,
} from '../src/anatomyMilestone.js';

test('summarizes anatomy milestone graph evidence for the browser morph gate', () => {
  const summary = summarizeAnatomyMilestone({
    milestone: 'M01',
    status: 'complete',
    summary: {
      node_count: 21,
      edge_count: 23,
      llm_handle_count: 5,
      working_set_node_count: 3,
      action_bundle_count: 3,
      max_action_bundle_node_count: 14,
      control_plan_count: 3,
      control_rejection_count: 2,
      render_layer_count: 5,
      render_primitive_count: 23,
      render_missing_mapping_count: 7,
    },
    neo4j: {
      node_records: 21,
      relationship_records: 23,
      schema_statement_count: 20,
      validation_query_count: 5,
    },
    action_bundles: [
      { action: 'wave', node_count: 12 },
      { action: 'run', node_count: 14 },
      { action: 'sweat_forehead', node_count: 8 },
    ],
    control_contract: {
      schema: 'god.body_control.v1',
      validated_plan: {
        control_count: 3,
        diagnostics: ['rejected_unknown_node:bone:made_up'],
      },
    },
    nodes: [
      { id: 'skin:forehead', kind: 'skin' },
      { id: 'render:forehead_sweat_proxy', kind: 'render_proxy' },
      { id: 'population:scalp_hair_follicles', kind: 'population_template' },
      { id: 'region:right_hand', kind: 'region' },
      { id: 'joint:right_knee', kind: 'joint' },
      { id: 'digit:right_hallux', kind: 'structure' },
      { id: 'bone:skull', kind: 'bone' },
    ],
    focus_nodes: [
      { id: 'region:right_hand' },
      { id: 'joint:right_knee' },
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
  assert.equal(summary.hasRightHand, true);
  assert.equal(summary.hasRightKnee, true);
  assert.equal(summary.hasRightHallux, true);
  assert.equal(summary.hasSkull, true);
  assert.equal(summary.focusNodeCount, 2);
  assert.equal(summary.neo4jNodeRecords, 21);
  assert.equal(summary.neo4jRelationshipRecords, 23);
  assert.equal(summary.neo4jSchemaStatementCount, 20);
  assert.equal(summary.neo4jValidationQueryCount, 5);
  assert.equal(summary.actionBundleCount, 3);
  assert.equal(summary.maxActionBundleNodeCount, 14);
  assert.equal(summary.controlPlanCount, 3);
  assert.equal(summary.controlRejectionCount, 2);
  assert.equal(summary.controlSchema, 'god.body_control.v1');
  assert.equal(summary.renderLayerCount, 5);
  assert.equal(summary.renderPrimitiveCount, 23);
  assert.equal(summary.renderMissingMappingCount, 7);
});

test('builds visible morph channels from sourced anatomy graph features', () => {
  const channels = buildMorphChannels({
    nodeCount: 21,
    workingSetNodeCount: 3,
    llmHandleCount: 5,
    hasForeheadSkin: true,
    hasSweatProxy: true,
    hasHairPopulation: true,
    hasRightHand: true,
    hasRightKnee: true,
    hasRightHallux: true,
    hasSkull: true,
    neo4jSchemaStatementCount: 20,
    actionBundleCount: 3,
    maxActionBundleNodeCount: 14,
    controlPlanCount: 3,
    controlRejectionCount: 2,
    renderPrimitiveCount: 23,
  });

  assert.equal(channels.headTiltDegrees, 11);
  assert.equal(channels.sweatPulse, 0.5);
  assert.equal(channels.hairSway, 0.625);
  assert.equal(channels.bodyScale > 1, true);
  assert.equal(channels.registryReach > 0, true);
  assert.equal(channels.handReach, 1);
  assert.equal(channels.kneeFlex, 1);
  assert.equal(channels.toePulse, 1);
  assert.equal(channels.graphPulse, 1);
  assert.equal(channels.lodPulse, 0.7);
  assert.equal(channels.contractPulse, 0.625);
  assert.equal(channels.renderPulse > 0, true);
});

test('builds graph-backed anatomy render projection layers without fake primitives', () => {
  const projection = getAnatomyRenderProjection({
    nodes: [
      { id: 'body:human', label: 'Human body', kind: 'body' },
      { id: 'bone:skull', label: 'Skull', kind: 'bone' },
      { id: 'joint:right_knee', label: 'Right knee joint', kind: 'joint' },
    ],
    render_projection: {
      schema: 'god.anatomy_render_projection.v1',
      status: 'degraded',
      diagnostics: ['missing_render_mapping:systems:system:muscular'],
      layers: [
        {
          id: 'body',
          label: 'Body',
          target_node_ids: ['body:human'],
          mapped_node_ids: ['body:human'],
          missing_node_ids: [],
        },
        {
          id: 'knee',
          label: 'Right knee',
          target_node_ids: ['joint:right_knee'],
          mapped_node_ids: ['joint:right_knee'],
          missing_node_ids: ['system:muscular'],
        },
      ],
      primitives: [
        {
          node_id: 'body:human',
          layer_id: 'body',
          shape: 'path',
          geometry: { d: 'M0 0 L1 1' },
        },
        {
          node_id: 'bone:made_up',
          layer_id: 'body',
          shape: 'circle',
          geometry: { cx: 1, cy: 1, r: 1 },
        },
        {
          node_id: 'joint:right_knee',
          layer_id: 'knee',
          shape: 'circle',
          geometry: { cx: 1, cy: 1, r: 1 },
        },
      ],
    },
  });

  assert.equal(projection.schema, 'god.anatomy_render_projection.v1');
  assert.equal(projection.layers.length, 2);
  assert.equal(projection.layers[0].primitives.length, 1);
  assert.equal(projection.layers[0].primitives[0].label, 'Human body');
  assert.equal(projection.layers[1].status, 'degraded');
  assert.equal(projection.layers[1].primitives[0].node_id, 'joint:right_knee');
  assert.equal(
    projection.layers.some((layer) =>
      layer.primitives.some((primitive) => primitive.node_id === 'bone:made_up'),
    ),
    false,
  );
});
