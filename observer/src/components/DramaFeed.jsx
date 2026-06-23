import { useObserverStore } from '../store';

function clean(text) {
  return String(text || '').replace(/\s+/g, ' ').trim();
}

export function DramaFeed() {
  const events = useObserverStore((s) => s.events);
  const recent = events
    .filter((ev) => String(ev.event_type || '').startsWith('social.') || String(ev.event_type || '').startsWith('narrative.'))
    .slice(0, 8);

  return (
    <aside className="drama-feed">
      <div className="panel-title">Live Feed</div>
      <div className="drama-list">
        {recent.map((ev) => (
          <article key={ev.event_id} className="drama-item">
            <div className="drama-kind">{ev.event_type}</div>
            <div className="drama-text">{clean(ev.narrative || ev.payload?.content || ev.payload?.body)}</div>
          </article>
        ))}
        {recent.length === 0 ? <div className="muted">waiting for motion</div> : null}
      </div>
    </aside>
  );
}
