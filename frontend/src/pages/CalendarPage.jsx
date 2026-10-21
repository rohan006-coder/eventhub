import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api.js';
import { useAuth } from '../auth.jsx';
import { Empty, ErrorBox, Loading, fmtT, useFetch } from '../ui.jsx';

const startOfDay = (d) => { const x = new Date(d); x.setHours(0, 0, 0, 0); return x; };
const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
const sameDay = (a, b) => a.toDateString() === b.toDateString();

function range(view, cur) {
  if (view === 'day') return [startOfDay(cur), addDays(startOfDay(cur), 1)];
  if (view === 'week') { const s = addDays(startOfDay(cur), -cur.getDay()); return [s, addDays(s, 7)]; }
  const first = new Date(cur.getFullYear(), cur.getMonth(), 1);
  const s = addDays(first, -first.getDay());
  return [s, addDays(s, 42)];
}

export default function CalendarPage() {
  const { orgId } = useAuth();
  const nav = useNavigate();
  const [view, setView] = useState('month');
  const [cur, setCur] = useState(new Date());
  const [from, to] = useMemo(() => range(view, cur), [view, cur.toDateString()]); // eslint-disable-line react-hooks/exhaustive-deps
  const { data, loading, error, reload } = useFetch(async () => (await api.get('/api/calendar', { params: { organization_id: orgId, start: from.toISOString(), end: to.toISOString() } })).data, [orgId, from.getTime(), to.getTime()], { skip: !orgId });
  const items = useMemo(() => data ? [...data.events, ...data.sessions, ...data.bookings].map((i) => ({ ...i, s: new Date(i.start), e: new Date(i.end) })).sort((a, b) => a.s - b.s) : [], [data]);
  const open = (i) => i.event_id && nav(`/events/${i.event_id}`);
  const step = (n) => setCur((c) => (view === 'month' ? new Date(c.getFullYear(), c.getMonth() + n, 1) : addDays(c, n * (view === 'week' ? 7 : 1))));
  const forDay = (d) => items.filter((i) => i.s < addDays(startOfDay(d), 1) && i.e >= startOfDay(d));
  const title = view === 'month' ? cur.toLocaleDateString([], { month: 'long', year: 'numeric' }) : view === 'week' ? `Week of ${from.toLocaleDateString([], { dateStyle: 'medium' })}` : cur.toLocaleDateString([], { dateStyle: 'full' });
  if (!orgId) return <Empty title="Select an organization first" />;
  const days = Array.from({ length: view === 'month' ? 42 : 7 }, (_, i) => addDays(from, i));
  const Chip = ({ i }) => <button className={`chip ${i.kind}`} title={`${i.title} (${fmtT(i.s)}–${fmtT(i.e)})`} onClick={() => open(i)}>{view !== 'month' || i.kind !== 'event' ? `${fmtT(i.s)} ` : ''}{i.title}</button>;
  return (
    <>
      <div className="pagehead"><div><h1>Calendar</h1><div className="legend"><span className="chip event" style={{ width: 'auto' }}>Events</span><span className="chip session" style={{ width: 'auto' }}>Sessions</span><span className="chip booking" style={{ width: 'auto' }}>Resource bookings</span></div></div></div>
      <div className="cal-head">
        <div className="row"><button onClick={() => step(-1)} aria-label="Previous">‹</button><button onClick={() => setCur(new Date())}>Today</button><button onClick={() => step(1)} aria-label="Next">›</button><b style={{ marginLeft: '.5rem' }}>{title}</b></div>
        <div className="row">{['month', 'week', 'day'].map((v) => <button key={v} className={view === v ? 'primary' : ''} onClick={() => setView(v)}>{v[0].toUpperCase() + v.slice(1)}</button>)}</div>
      </div>
      <ErrorBox error={error} onRetry={reload} />
      {loading && !data ? <Loading /> : view === 'day' ? (
        <div className="card day-list">{forDay(cur).length ? forDay(cur).map((i) => <div key={`${i.kind}${i.id}`}><time>{fmtT(i.s)}</time><Chip i={i} /></div>) : <Empty title="Nothing scheduled">This day is free.</Empty>}</div>
      ) : (
        <div className="cal-grid">
          {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((d) => <div className="cal-dow" key={d}>{d}</div>)}
          {days.map((d) => <div key={d.toISOString()} className={`cal-cell ${view === 'month' && d.getMonth() !== cur.getMonth() ? 'out' : ''} ${sameDay(d, new Date()) ? 'today' : ''}`}
            style={view === 'week' ? { minHeight: 220 } : undefined}>
            <span className="d">{d.getDate()}</span>{forDay(d).slice(0, view === 'month' ? 4 : 30).map((i) => <Chip key={`${i.kind}${i.id}`} i={i} />)}
            {view === 'month' && forDay(d).length > 4 && <button className="linklike muted" onClick={() => { setCur(d); setView('day'); }}>+{forDay(d).length - 4} more</button>}</div>)}
        </div>)}
    </>
  );
}
