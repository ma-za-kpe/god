import { useEffect, useMemo, useState } from 'react';
import { useObserverStore } from '../store';

function defaultRuntimeUrl() {
  const { hostname, port, origin } = window.location;
  if ((hostname === 'localhost' || hostname === '127.0.0.1') && port === '3000') {
    return 'http://localhost:8888';
  }
  return origin;
}

const API_BASE = window.RUNTIME_URL || import.meta.env.VITE_RUNTIME_URL || defaultRuntimeUrl();

export function AgentInspector() {
  const agents = useObserverStore((s) => s.agents);
  const selectedSoulId = useObserverStore((s) => s.selectedSoulId);
  const selectAgent = useObserverStore((s) => s.selectAgent);
  const [status, setStatus] = useState(null);

  const agent = useMemo(
    () => agents.find((item) => item?.soul_id === selectedSoulId) || agents[0] || null,
    [agents, selectedSoulId]
  );

  useEffect(() => {
    if (!agent?.soul_id) return;
    let alive = true;
    fetch(`${API_BASE}/status/${agent.soul_id}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((json) => {
        if (alive) setStatus(json);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [agent?.soul_id]);

  if (!agent) return null;

  return (
    <aside className="inspector">
      <div className="inspector-head">
        <div>
          <div className="inspector-name">{agent.current_name || agent.soul_id}</div>
          <div className="inspector-sub">{agent.archetype}</div>
        </div>
        <button className="close-btn" onClick={() => selectAgent(null)}>
          ×
        </button>
      </div>
      <div className="inspector-body">
        <div><span>balance</span><strong>${Number(agent.balance_usdc || 0).toFixed(3)}</strong></div>
        <div><span>rent</span><strong>{agent.rent_paid_count}/{agent.rent_miss_count}</strong></div>
        <div><span>avatar</span><strong>{agent.avatar_cid ? 'yes' : 'no'}</strong></div>
        <div><span>voice</span><strong>{agent.voice_model_cid ? 'yes' : 'no'}</strong></div>
        <div><span>vrm</span><strong>{agent.vrm_avatar_url ? 'url' : 'fallback'}</strong></div>
        <div><span>state</span><strong>{status?.tier_name || status?.tier || 'live'}</strong></div>
      </div>
    </aside>
  );
}
