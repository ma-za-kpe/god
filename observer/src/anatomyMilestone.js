export function summarizeAnatomyMilestone(payload = {}) {
  const nodes = Array.isArray(payload.nodes) ? payload.nodes : [];
  const registry = Array.isArray(payload.llm_registry) ? payload.llm_registry : [];
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
    byKind,
    hasForeheadSkin: nodes.some((node) => node.id === 'skin:forehead'),
    hasSweatProxy: nodes.some((node) => node.id === 'render:forehead_sweat_proxy'),
    hasHairPopulation: nodes.some((node) => node.id === 'population:scalp_hair_follicles'),
  };
}

export function buildMorphChannels(summary = {}) {
  const nodeCount = Math.max(1, Number(summary.nodeCount || 1));
  const workingSetNodeCount = Math.max(1, Number(summary.workingSetNodeCount || 1));
  const llmHandleCount = Math.max(1, Number(summary.llmHandleCount || 1));
  return {
    bodyScale: Math.min(1.18, 1 + nodeCount / 260),
    headTiltDegrees: summary.hasForeheadSkin ? 7 : 0,
    sweatPulse: summary.hasSweatProxy ? Math.min(1, workingSetNodeCount / 6) : 0,
    hairSway: summary.hasHairPopulation ? Math.min(1, llmHandleCount / 8) : 0,
    registryReach: Math.min(1, llmHandleCount / Math.max(1, nodeCount)),
  };
}
