import { useObserverStore } from '../store';

export function MilestoneBar() {
  const events = useObserverStore((s) => s.events);
  const firsts = events.filter((ev) => String(ev.event_type || '').startsWith('timeline.world.first'));

  return (
    <div className="milestone-bar">
      {firsts.slice(0, 10).map((ev) => (
        <span key={ev.event_id} className="milestone-pill">
          {ev.narrative || ev.event_type}
        </span>
      ))}
      {firsts.length === 0 ? <span className="muted">no world firsts yet</span> : null}
    </div>
  );
}
