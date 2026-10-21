import { useState } from 'react';
import api from '../api.js';
import { useAuth } from '../auth.jsx';
import { SessionsPanel } from '../panels.jsx';
import { Empty, Loading, useFetch } from '../ui.jsx';

export default function SessionsPage() {
  const { orgId } = useAuth();
  const [eventId, setEventId] = useState('');
  const { data, loading } = useFetch(async () => (await api.get('/api/events', { params: { organization_id: orgId, page_size: 100, sort: 'start_time' } })).data.items.filter((e) => e.status !== 'archived'), [orgId], { skip: !orgId });
  if (!orgId) return <Empty title="Select an organization first" />;
  const ev = data?.find((e) => String(e.id) === String(eventId));
  return (
    <>
      <div className="pagehead"><div><h1>Sessions</h1><p className="muted">Build and review the schedule for an event.</p></div></div>
      <div className="filters"><div style={{ maxWidth: 380 }}><label>Event</label><select value={eventId} onChange={(e) => setEventId(e.target.value)}><option value="">Choose an event…</option>{data?.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}</select></div></div>
      {loading && !data ? <Loading /> : ev ? <SessionsPanel key={ev.id} event={ev} /> : <div className="card"><Empty title="Pick an event">Its sessions will appear here.</Empty></div>}
    </>
  );
}
