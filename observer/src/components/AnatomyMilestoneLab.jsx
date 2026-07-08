import { useEffect, useMemo, useState } from 'react';
import { buildMorphChannels, summarizeAnatomyMilestone } from '../anatomyMilestone';

const ASSET_URL = '/assets/anatomy/latest-graph.json';

export function AnatomyMilestoneLab() {
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    fetch(ASSET_URL, { cache: 'no-store' })
      .then((response) => {
        if (!response.ok) throw new Error(`asset_load_failed:${response.status}`);
        return response.json();
      })
      .then((json) => {
        if (alive) {
          setPayload(json);
          setError('');
        }
      })
      .catch((caught) => {
        if (alive) setError(String(caught?.message || caught));
      });
    return () => {
      alive = false;
    };
  }, []);

  const summary = useMemo(() => summarizeAnatomyMilestone(payload || {}), [payload]);
  const morph = useMemo(() => buildMorphChannels(summary), [summary]);
  const workingSet = Array.isArray(payload?.focus_nodes) && payload.focus_nodes.length
    ? payload.focus_nodes
    : (Array.isArray(payload?.forehead_working_set) ? payload.forehead_working_set : []);
  const registry = Array.isArray(payload?.llm_registry) ? payload.llm_registry : [];
  const morphStyle = {
    '--body-scale': morph.bodyScale,
    '--head-tilt': `${morph.headTiltDegrees}deg`,
    '--sweat-pulse': morph.sweatPulse,
    '--hair-sway': morph.hairSway,
    '--registry-reach': morph.registryReach,
    '--hand-reach': morph.handReach,
    '--knee-flex': morph.kneeFlex,
    '--toe-pulse': morph.toePulse,
    '--graph-pulse': morph.graphPulse,
    '--lod-pulse': morph.lodPulse,
    '--contract-pulse': morph.contractPulse,
  };

  return (
    <main
      className="anatomy-lab"
      data-testid="anatomy-milestone-lab"
      data-milestone={summary.milestone}
      data-morph-state={payload && !error ? 'active' : 'loading'}
      data-node-count={summary.nodeCount}
      data-working-set-count={summary.workingSetNodeCount}
    >
      <section className="anatomy-stage" style={morphStyle}>
        <div className="anatomy-stage-header">
          <span>{summary.milestone} Anatomy Body Projection</span>
          <strong>{error || summary.status}</strong>
        </div>
        <svg
          className="anatomy-body-svg"
          viewBox="0 0 420 760"
          role="img"
          aria-label="Morphing anatomy body projection"
          data-testid="anatomy-body-morph"
        >
          <defs>
            <linearGradient id="anatomySkin" x1="0" x2="1" y1="0" y2="1">
              <stop offset="0%" stopColor="#d9b58f" />
              <stop offset="100%" stopColor="#8fb8d9" />
            </linearGradient>
            <linearGradient id="anatomySystem" x1="0" x2="1" y1="0" y2="1">
              <stop offset="0%" stopColor="#44d7a8" />
              <stop offset="100%" stopColor="#4aa3ff" />
            </linearGradient>
          </defs>
          <g className="anatomy-shadow">
            <ellipse cx="210" cy="716" rx="112" ry="24" />
          </g>
          <g className="anatomy-graph-grid" aria-hidden="true">
            <path d="M116 198 H304 M104 322 H316 M98 446 H322 M210 190 V704" />
          </g>
          <g className="anatomy-lod-ring" aria-hidden="true">
            <ellipse cx="210" cy="430" rx="166" ry="294" />
          </g>
          <g className="anatomy-contract-ring" aria-hidden="true">
            <ellipse cx="210" cy="430" rx="190" ry="318" />
          </g>
          <g className="anatomy-figure">
            <g className="anatomy-head">
              <path className="anatomy-hair" d="M165 108 C166 55 254 54 257 109 C242 86 185 84 165 108 Z" />
              <circle className="anatomy-skin" cx="210" cy="119" r="52" />
              <path className="anatomy-skull" d="M174 115 C174 73 246 73 246 115 C246 154 174 154 174 115 Z" />
              <path className="anatomy-forehead" d="M176 101 C188 76 233 76 246 101 C228 92 194 92 176 101 Z" />
              <g className="anatomy-sweat">
                <circle cx="190" cy="96" r="5" />
                <circle cx="211" cy="88" r="4" />
                <circle cx="232" cy="97" r="5" />
              </g>
              <circle className="anatomy-eye" cx="193" cy="121" r="4" />
              <circle className="anatomy-eye" cx="228" cy="121" r="4" />
              <path className="anatomy-mouth" d="M194 143 Q210 153 227 143" />
              <text className="anatomy-node-label" x="252" y="111">skull</text>
            </g>
            <path className="anatomy-neck" d="M190 167 L230 167 L238 210 L181 210 Z" />
            <path className="anatomy-torso" d="M149 210 C169 187 250 187 271 210 L291 433 C256 467 165 467 129 433 Z" />
            <path className="anatomy-spine" d="M210 214 C204 280 220 340 211 435" />
            <path className="anatomy-ribs" d="M170 261 C193 244 227 244 250 261 M161 305 C193 287 227 287 260 305" />
            <g className="anatomy-arm anatomy-arm-left">
              <path d="M150 225 C98 253 84 333 75 414" />
              <path d="M75 414 C70 454 80 493 104 525" />
              <circle cx="72" cy="424" r="17" />
              <path d="M91 529 C82 548 102 570 121 556" />
            </g>
            <g className="anatomy-arm anatomy-arm-right">
              <path d="M270 225 C323 253 336 333 345 414" />
              <path d="M345 414 C350 454 340 493 316 525" />
              <circle cx="348" cy="424" r="17" />
              <path d="M329 529 C338 548 318 570 299 556" />
            </g>
            <g className="anatomy-leg anatomy-leg-left">
              <path d="M174 454 C161 528 150 605 142 685" />
              <circle className="anatomy-knee" cx="153" cy="560" r="18" />
              <path d="M142 685 C130 699 159 707 181 696" />
            </g>
            <g className="anatomy-leg anatomy-leg-right">
              <path d="M246 454 C259 528 270 605 278 685" />
              <circle className="anatomy-knee" cx="267" cy="560" r="18" />
              <path d="M278 685 C290 699 261 707 239 696" />
              <circle className="anatomy-toe-pulse" cx="278" cy="690" r="10" />
            </g>
          </g>
          <g className="anatomy-annotations" aria-hidden="true">
            <path className="anatomy-leader" d="M342 514 L326 538" />
            <text className="anatomy-node-label" x="346" y="514">right hand</text>
            <path className="anatomy-leader" d="M314 588 L274 562" />
            <text className="anatomy-node-label" x="318" y="592">right knee</text>
            <path className="anatomy-leader" d="M310 716 L280 694" />
            <text className="anatomy-node-label" x="314" y="720">hallux</text>
          </g>
        </svg>
        <div className="anatomy-morph-readout" data-testid="anatomy-morph-readout">
          <span>morph active</span>
          <span>{summary.milestone}</span>
          <span>skin:forehead</span>
          <span>forehead sweat proxy</span>
          <span>scalp hair population</span>
          {summary.hasRightHand && <span>right hand</span>}
          {summary.hasRightKnee && <span>right knee</span>}
          {summary.hasRightHallux && <span>right hallux</span>}
          {summary.neo4jSchemaStatementCount > 0 && <span>neo4j schema {summary.neo4jSchemaStatementCount}</span>}
          {summary.neo4jValidationQueryCount > 0 && <span>cypher checks {summary.neo4jValidationQueryCount}</span>}
          {summary.actionBundleCount > 0 && <span>lod bundles {summary.actionBundleCount}</span>}
          {summary.controlPlanCount > 0 && <span>control plan {summary.controlPlanCount}</span>}
          {summary.controlRejectionCount > 0 && <span>rejected {summary.controlRejectionCount}</span>}
        </div>
      </section>
      <aside className="anatomy-panel">
        <header>
          <span>Milestone Gate</span>
          <strong>{summary.milestone}</strong>
        </header>
        <div className="anatomy-metrics">
          <div><strong>{summary.nodeCount}</strong><span>nodes</span></div>
          <div><strong>{summary.edgeCount}</strong><span>edges</span></div>
          <div><strong>{summary.llmHandleCount}</strong><span>LLM handles</span></div>
          <div><strong>{summary.focusNodeCount || summary.workingSetNodeCount}</strong><span>focus nodes</span></div>
          {summary.neo4jSchemaStatementCount > 0 && (
            <div><strong>{summary.neo4jSchemaStatementCount}</strong><span>schema</span></div>
          )}
          {summary.neo4jValidationQueryCount > 0 && (
            <div><strong>{summary.neo4jValidationQueryCount}</strong><span>cypher checks</span></div>
          )}
          {summary.actionBundleCount > 0 && (
            <div><strong>{summary.actionBundleCount}</strong><span>LOD bundles</span></div>
          )}
          {summary.maxActionBundleNodeCount > 0 && (
            <div><strong>{summary.maxActionBundleNodeCount}</strong><span>max bundle</span></div>
          )}
          {summary.controlPlanCount > 0 && (
            <div><strong>{summary.controlPlanCount}</strong><span>accepted controls</span></div>
          )}
          {summary.controlRejectionCount > 0 && (
            <div><strong>{summary.controlRejectionCount}</strong><span>rejected controls</span></div>
          )}
        </div>
        <section>
          <h2>Working Set</h2>
          <ul>
            {workingSet.map((node) => (
              <li key={node.id}>
                <strong>{node.id}</strong>
                <span>{node.kind} / {node.materialization}</span>
              </li>
            ))}
          </ul>
        </section>
        <section>
          <h2>LLM Registry</h2>
          <ul>
            {registry.map((node) => (
              <li key={node.id}>
                <strong>{node.id}</strong>
                <span>{node.control_channels.join(', ')}</span>
              </li>
            ))}
          </ul>
        </section>
      </aside>
    </main>
  );
}
