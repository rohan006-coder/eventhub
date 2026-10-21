import { useState } from 'react';
import api from '../api.js';
import { useAuth } from '../auth.jsx';
import { AttendancePanel } from '../panels.jsx';
import { Empty, Loading, useFetch } from '../ui.jsx';

export default function AttendancePage() {
  const { orgId } = useAuth();
  const [eventId, setEventId] = useState('');
  const { data, loading } = useFetch(async () => (await api.get('/api/events', { params: { organization_id: orgId, page_size: 100, sort: '-start_time' } })).data.items.filter((e) => ['published', 'ongoing', 'completed'].includes(e.status)), [orgId], { skip: !orgId });
  const ev = data?.find((e) => String(e.id) === String(eventId));
  return (
    <>
      <div className="pagehead"><div><h1>Attendance</h1><p className="muted">Check participants in and export a report.</p></div></div>
      <div className="filters"><div style={{ maxWidth: 380 }}><label>Event</label><select value={eventId} onChange={(e) => setEventId(e.target.value)}><option value="">Choose an event…</option>{data?.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}</select></div></div>
      {loading && !data ? <Loading /> : ev ? <AttendancePanel key={ev.id} event={ev} /> : <div className="card"><Empty title="Pick an event">Published, ongoing and completed events can record attendance.</Empty></div>}
    </>
  );
}
