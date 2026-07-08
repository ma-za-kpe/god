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
    byKind,
    hasForeheadSkin: nodes.some((node) => node.id === 'skin:forehead'),
    hasSweatProxy: nodes.some((node) => node.id === 'render:forehead_sweat_proxy'),
    hasHairPopulation: nodes.some((node) => node.id === 'population:scalp_hair_follicles'),
    hasRightHand: nodes.some((node) => node.id === 'region:right_hand'),
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
