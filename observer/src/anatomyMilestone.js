const RIGHT_HAND_DIGIT_IDS = new Set([
  'digit:right_pollex',
  'digit:right_index_finger',
  'digit:right_middle_finger',
  'digit:right_ring_finger',
  'digit:right_little_finger',
]);

const RIGHT_HAND_PHALANX_PREFIXES = [
  'bone:right_pollex_',
  'bone:right_index_finger_',
  'bone:right_middle_finger_',
  'bone:right_ring_finger_',
  'bone:right_little_finger_',
];

export function summarizeAnatomyMilestone(payload = {}) {
  const nodes = Array.isArray(payload.nodes) ? payload.nodes : [];
  const registry = Array.isArray(payload.llm_registry) ? payload.llm_registry : [];
  const focusNodes = Array.isArray(payload.focus_nodes) ? payload.focus_nodes : [];
  const actionBundles = Array.isArray(payload.action_bundles) ? payload.action_bundles : [];
  const controlContract =
    payload.control_contract && typeof payload.control_contract === 'object'
      ? payload.control_contract
      : {};
  const validatedPlan =
    controlContract.validated_plan && typeof controlContract.validated_plan === 'object'
      ? controlContract.validated_plan
      : {};
  const motionProjection =
    payload.motion_projection && typeof payload.motion_projection === 'object'
      ? payload.motion_projection
      : {};
  const workingSet = Array.isArray(payload.forehead_working_set) ? payload.forehead_working_set : [];
  const byKind = nodes.reduce((summary, node) => {
    const kind = node?.kind || 'unknown';
    summary[kind] = (summary[kind] || 0) + 1;
    return summary;
  }, {});
  return {
    milestone: payload.milestone || 'unknown',
    status: payload.status || 'unknown',
    nodeCount: Number(payload.summary?.node_count || nodes.length || 0),
    edgeCount: Number(payload.summary?.edge_count || 0),
    llmHandleCount: Number(payload.summary?.llm_handle_count || registry.length || 0),
    workingSetNodeCount: Number(payload.summary?.working_set_node_count || workingSet.length || 0),
    focusNodeCount: Number(payload.summary?.focus_node_count || focusNodes.length || 0),
    actionBundleCount: Number(payload.summary?.action_bundle_count || actionBundles.length || 0),
    maxActionBundleNodeCount: Number(payload.summary?.max_action_bundle_node_count || 0),
    controlPlanCount: Number(payload.summary?.control_plan_count || validatedPlan.control_count || 0),
    controlRejectionCount: Number(payload.summary?.control_rejection_count || 0),
    controlSchema: controlContract.schema || '',
    renderLayerCount: Number(payload.summary?.render_layer_count || 0),
    renderPrimitiveCount: Number(payload.summary?.render_primitive_count || 0),
    renderMissingMappingCount: Number(payload.summary?.render_missing_mapping_count || 0),
    motionPlanCount: Number(payload.summary?.motion_plan_count || motionProjection.plan_count || 0),
    motionRendererControlCount: Number(
      payload.summary?.motion_renderer_control_count || motionProjection.renderer_control_count || 0,
    ),
    motionSimulationHintCount: Number(
      payload.summary?.motion_simulation_hint_count || motionProjection.simulation_hint_count || 0,
    ),
    motionVisualCueCount: Number(
      payload.summary?.motion_visual_cue_count || motionProjection.visual_cue_count || 0,
    ),
    motionDiagnosticCount: Number(
      payload.summary?.motion_diagnostic_count || motionProjection.diagnostic_count || 0,
    ),
    byKind,
    hasForeheadSkin: nodes.some((node) => node.id === 'skin:forehead'),
    hasSweatProxy: nodes.some((node) => node.id === 'render:forehead_sweat_proxy'),
    hasHairPopulation: nodes.some((node) => node.id === 'population:scalp_hair_follicles'),
    hasRightHand: nodes.some((node) => node.id === 'region:right_hand'),
    rightHandDigitCount: nodes.filter((node) => RIGHT_HAND_DIGIT_IDS.has(node.id)).length,
    rightHandPhalanxCount: nodes.filter((node) => (
      typeof node.id === 'string'
      && RIGHT_HAND_PHALANX_PREFIXES.some((prefix) => node.id.startsWith(prefix))
      && node.id.endsWith('_phalanx')
    )).length,
    hasRightLittleFinger: nodes.some((node) => node.id === 'digit:right_little_finger'),
    rightLittleFingerPhalanxCount: nodes.filter((node) => (
      typeof node.id === 'string' && node.id.startsWith('bone:right_little_finger_')
    )).length,
    hasRightKnee: nodes.some((node) => node.id === 'joint:right_knee'),
    hasRightHallux: nodes.some((node) => node.id === 'digit:right_hallux'),
    hasSkull: nodes.some((node) => node.id === 'bone:skull'),
    neo4jNodeRecords: Number(payload.neo4j?.node_records || 0),
    neo4jRelationshipRecords: Number(payload.neo4j?.relationship_records || 0),
    neo4jSchemaStatementCount: Number(payload.neo4j?.schema_statement_count || 0),
    neo4jValidationQueryCount: Number(payload.neo4j?.validation_query_count || 0),
  };
}

export function buildMorphChannels(summary = {}) {
  const nodeCount = Math.max(1, Number(summary.nodeCount || 1));
  const workingSetNodeCount = Math.max(1, Number(summary.workingSetNodeCount || 1));
  const llmHandleCount = Math.max(1, Number(summary.llmHandleCount || 1));
  return {
    bodyScale: Math.min(1.18, 1 + nodeCount / 260),
    headTiltDegrees: summary.hasSkull ? 11 : (summary.hasForeheadSkin ? 7 : 0),
    sweatPulse: summary.hasSweatProxy ? Math.min(1, workingSetNodeCount / 6) : 0,
    hairSway: summary.hasHairPopulation ? Math.min(1, llmHandleCount / 8) : 0,
    registryReach: Math.min(1, llmHandleCount / Math.max(1, nodeCount)),
    handReach: summary.hasRightHand ? 1 : 0,
    handDigitReach: Math.min(1, Number(summary.rightHandDigitCount || 0) / 5),
    handPhalanxReach: Math.min(1, Number(summary.rightHandPhalanxCount || 0) / 14),
    pinkyReach: summary.hasRightLittleFinger
      ? Math.min(1, Number(summary.rightLittleFingerPhalanxCount || 0) / 3)
      : 0,
    kneeFlex: summary.hasRightKnee ? 1 : 0,
    toePulse: summary.hasRightHallux ? 1 : 0,
    graphPulse: summary.neo4jSchemaStatementCount ? 1 : 0,
    lodPulse: summary.actionBundleCount ? Math.min(1, summary.maxActionBundleNodeCount / 20) : 0,
    contractPulse: summary.controlPlanCount
      ? Math.min(1, (summary.controlPlanCount + summary.controlRejectionCount) / 8)
      : 0,
    renderPulse: summary.renderPrimitiveCount
      ? Math.min(1, summary.renderPrimitiveCount / Math.max(1, summary.nodeCount))
      : 0,
    motionPulse: summary.motionPlanCount
      ? Math.min(
        1,
        (
          summary.motionRendererControlCount
          + summary.motionSimulationHintCount
          + summary.motionVisualCueCount
        ) / 24,
      )
      : 0,
  };
}

export function getAnatomyRenderProjection(payload = {}) {
  const projection = payload.render_projection && typeof payload.render_projection === 'object'
    ? payload.render_projection
    : {};
  const layers = Array.isArray(projection.layers) ? projection.layers : [];
  const primitives = Array.isArray(projection.primitives) ? projection.primitives : [];
  const diagnostics = Array.isArray(projection.diagnostics) ? projection.diagnostics : [];
  const nodeById = new Map((Array.isArray(payload.nodes) ? payload.nodes : []).map((node) => [node.id, node]));
  return {
    schema: projection.schema || '',
    status: projection.status || 'unknown',
    diagnostics,
    layers: layers.map((layer) => {
      const targetNodeIds = Array.isArray(layer.target_node_ids) ? layer.target_node_ids : [];
      const mappedNodeIds = Array.isArray(layer.mapped_node_ids) ? layer.mapped_node_ids : [];
      const missingNodeIds = Array.isArray(layer.missing_node_ids) ? layer.missing_node_ids : [];
      return {
        id: String(layer.id || ''),
        label: String(layer.label || layer.id || ''),
        targetNodeIds,
        mappedNodeIds,
        missingNodeIds,
        primitives: primitives
          .filter((primitive) => primitive.layer_id === layer.id && nodeById.has(primitive.node_id))
          .map((primitive) => ({
            ...primitive,
            label: nodeById.get(primitive.node_id)?.label || primitive.node_id,
            kind: nodeById.get(primitive.node_id)?.kind || 'unknown',
          })),
        status: missingNodeIds.length ? 'degraded' : 'complete',
      };
    }),
  };
}

export function getAnatomyMotionProjection(payload = {}) {
  const projection = payload.motion_projection && typeof payload.motion_projection === 'object'
    ? payload.motion_projection
    : {};
  const plans = Array.isArray(projection.plans) ? projection.plans : [];
  const diagnostics = Array.isArray(projection.diagnostics) ? projection.diagnostics : [];
  const nodeById = new Map((Array.isArray(payload.nodes) ? payload.nodes : []).map((node) => [node.id, node]));
  const hydratedPlans = plans.map((plan) => {
    const sourceBundleNodeIds = (Array.isArray(plan.source_bundle_node_ids)
      ? plan.source_bundle_node_ids
      : []
    ).filter((nodeId) => nodeById.has(nodeId));
    const sourceBundleNodeIdSet = new Set(sourceBundleNodeIds);
    const planDiagnostics = Array.isArray(plan.diagnostics) ? [...plan.diagnostics] : [];
    const rendererControls = sanitizeMotionRecords(
      plan.renderer_controls,
      nodeById,
      sourceBundleNodeIdSet,
    );
    const simulationHints = sanitizeMotionRecords(
      plan.simulation_hints,
      nodeById,
      sourceBundleNodeIdSet,
    );
    const visualCues = sanitizeMotionRecords(
      plan.visual_cues,
      nodeById,
      sourceBundleNodeIdSet,
    );
    const rawRecordCount =
      safeArray(plan.renderer_controls).length
      + safeArray(plan.simulation_hints).length
      + safeArray(plan.visual_cues).length;
    const acceptedRecordCount =
      rendererControls.length + simulationHints.length + visualCues.length;
    const droppedRecordCount = rawRecordCount - acceptedRecordCount;
    if (droppedRecordCount > 0) {
      planDiagnostics.push(`dropped_unbacked_motion_records:${droppedRecordCount}`);
    }

    return {
      action: String(plan.action || ''),
      status: planDiagnostics.length ? 'degraded' : (plan.status || 'complete'),
      rendererControls,
      simulationHints,
      visualCues,
      sourceBundleNodeIds,
      diagnostics: planDiagnostics,
    };
  });

  return {
    schema: projection.schema || '',
    status: diagnostics.length ? 'degraded' : (projection.status || 'unknown'),
    diagnostics,
    plans: hydratedPlans,
    planCount: hydratedPlans.length,
    rendererControlCount: hydratedPlans.reduce(
      (count, plan) => count + plan.rendererControls.length,
      0,
    ),
    simulationHintCount: hydratedPlans.reduce(
      (count, plan) => count + plan.simulationHints.length,
      0,
    ),
    visualCueCount: hydratedPlans.reduce((count, plan) => count + plan.visualCues.length, 0),
  };
}

function safeArray(value) {
  return Array.isArray(value) ? value : [];
}

function sanitizeMotionRecords(records, nodeById, sourceBundleNodeIdSet) {
  return safeArray(records)
    .filter((record) => (
      nodeById.has(record?.node_id)
      && (!sourceBundleNodeIdSet.size || sourceBundleNodeIdSet.has(record.node_id))
    ))
    .map((record) => ({
      ...record,
      label: nodeById.get(record.node_id)?.label || record.node_id,
      kind: nodeById.get(record.node_id)?.kind || 'unknown',
    }));
}
