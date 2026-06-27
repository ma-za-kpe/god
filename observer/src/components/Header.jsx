import { useObserverStore } from '../store';

export function Header({ mode }) {
  const stats = useObserverStore((s) => s.stats);
  const agents = useObserverStore((s) => s.agents);
  const living = agents.filter((a) => a && a.is_alive !== false);

  return (
    <header className="header">
      <div className="brand">
        <div className="brand-mark">G</div>
        <div>
          <div className="brand-title">GOD Observer</div>
          <div className="brand-subtitle">{mode === 'one' ? 'solo rig test' : 'live ensemble stage'}</div>
        </div>
      </div>
      <div className="header-metrics">
        <span>{living.length} alive</span>
        <span>{stats.events_total ?? stats.event_count ?? 0} events</span>
        <span>{stats.world_id || 'world'}</span>
      </div>
    </header>
  );
}
