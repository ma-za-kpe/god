export function summarizeAnatomyMilestone(payload = {}) {
  const nodes = Array.isArray(payload.nodes) ? payload.nodes : [];
  const registry = Array.isArray(payload.llm_registry) ? payload.llm_registry : [];
  const focusNodes = Array.isArray(payload.focus_nodes) ? payload.focus_nodes : [];
  const actionBundles = Array.isArray(payload.action_bundles) ? payload.action_bundles : [];
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
  };
}
