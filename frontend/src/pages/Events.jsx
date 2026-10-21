import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import api from '../api.js';
import { useAuth } from '../auth.jsx';
import { Badge, Empty, ErrorBox, Field, Loading, Modal, Pager, fmtDT, toISO, toLocalInput, useFetch, useForm } from '../ui.jsx';

export const EventForm = ({ orgId, event, onDone }) => {
  const f = useForm({
    name: event?.name || '', description: event?.description || '', location: event?.location || '', capacity: event?.capacity || 100, requires_approval: event?.requires_approval || false,
    start_time: event ? toLocalInput(event.start_time) : '', end_time: event ? toLocalInput(event.end_time) : '', registration_deadline: '',
  }, (v) => ({
    ...(v.name.trim().length < 2 && { name: 'Name must be at least 2 characters.' }),
    ...(!v.start_time && { start_time: 'Choose a start.' }), ...(!v.end_time && { end_time: 'Choose an end.' }),
    ...(v.start_time && v.end_time && new Date(v.end_time) <= new Date(v.start_time) && { end_time: 'End must be after start.' }),
    ...(!(Number(v.capacity) > 0) && { capacity: 'Capacity must be at least 1.' }),
    ...(v.registration_deadline && v.start_time && new Date(v.registration_deadline) > new Date(v.start_time) && { registration_deadline: 'Deadline must be before the event starts.' }),
  }), async (v) => {
    const body = { name: v.name, description: v.description, location: v.location, capacity: Number(v.capacity), requires_approval: v.requires_approval,
      start_time: toISO(v.start_time), end_time: toISO(v.end_time), ...(v.registration_deadline && { registration_deadline: toISO(v.registration_deadline) }) };
    const { data } = event ? await api.patch(`/api/events/${event.id}`, body) : await api.post('/api/events', { ...body, organization_id: orgId });
    onDone(data);
  });
  return (
    <form onSubmit={f.submit} noValidate>
      {f.serverError && <div className="alert" role="alert">{f.serverError}</div>}
      <div className="form-grid">
        <Field label="Name" error={f.errors.name}><input value={f.values.name} onChange={f.set('name')} /></Field>
        <Field label="Location"><input value={f.values.location} onChange={f.set('location')} /></Field>
        <Field label="Starts" error={f.errors.start_time}><input type="datetime-local" value={f.values.start_time} onChange={f.set('start_time')} /></Field>
        <Field label="Ends" error={f.errors.end_time}><input type="datetime-local" value={f.values.end_time} onChange={f.set('end_time')} /></Field>
        <Field label="Capacity" error={f.errors.capacity}><input type="number" min="1" value={f.values.capacity} onChange={f.set('capacity')} /></Field>
        <Field label="Registration closes (optional)" error={f.errors.registration_deadline}><input type="datetime-local" value={f.values.registration_deadline} onChange={f.set('registration_deadline')} /></Field>
      </div>
      <Field label="Description"><textarea rows={3} value={f.values.description} onChange={f.set('description')} /></Field>
      <label className="row"><input type="checkbox" checked={f.values.requires_approval} onChange={f.set('requires_approval')} /> Staff must approve each registration</label>
      <p><button className="primary" disabled={f.busy}>{event ? 'Save changes' : 'Create event (as draft)'}</button></p>
    </form>
  );
};

export default function Events() {
  const { orgId, can } = useAuth();
  const nav = useNavigate();
  const [q, setQ] = useState({ search: '', status: '', location: '', date_from: '', date_to: '', sort: 'start_time', page: 1 });
  const [open, setOpen] = useState(false);
  const set = (k) => (e) => setQ((s) => ({ ...s, [k]: e.target.value, page: 1 }));
  const { data, loading, error, reload } = useFetch(async () => (await api.get('/api/events', { params: {
    organization_id: orgId, page: q.page, page_size: 10, sort: q.sort, search: q.search || undefined, status: q.status || undefined, location: q.location || undefined,
    date_from: q.date_from ? new Date(q.date_from).toISOString() : undefined, date_to: q.date_to ? new Date(`${q.date_to}T23:59:59`).toISOString() : undefined } })).data, [orgId, JSON.stringify(q)], { skip: !orgId });
  if (!orgId) return <Empty title="Select or create an organization first" />;
  return (
    <>
      <div className="pagehead"><div><h1>Events</h1></div>{can('event_manager') && <button className="primary" onClick={() => setOpen(true)}>New event</button>}</div>
      <div className="filters">
        <div><label>Search</label><input placeholder="Name or description" value={q.search} onChange={set('search')} /></div>
        <div><label>Status</label><select value={q.status} onChange={set('status')}><option value="">Any</option>{['draft', 'published', 'ongoing', 'completed', 'cancelled', 'archived'].map((s) => <option key={s}>{s}</option>)}</select></div>
        <div><label>Location</label><input value={q.location} onChange={set('location')} /></div>
        <div><label>From</label><input type="date" value={q.date_from} onChange={set('date_from')} /></div>
        <div><label>To</label><input type="date" value={q.date_to} onChange={set('date_to')} /></div>
        <div><label>Sort</label><select value={q.sort} onChange={set('sort')}><option value="start_time">Soonest first</option><option value="-start_time">Latest first</option><option value="name">Name A–Z</option><option value="-created_at">Newest created</option></select></div>
      </div>
      <ErrorBox error={error} onRetry={reload} />
      {loading && !data ? <Loading /> : !data?.items.length ? <div className="card"><Empty title="No events found">{can('event_manager') ? 'Create your first event, or adjust the filters.' : 'Try different filters, or check back soon.'}</Empty></div> : (<>
        <div className="tablewrap"><table><thead><tr><th>Event</th><th>When</th><th>Location</th><th>Seats</th><th>Status</th></tr></thead><tbody>
          {data.items.map((e) => <tr key={e.id}><td><Link to={`/events/${e.id}`}><b>{e.name}</b></Link><div className="muted">by {e.organizer_name || 'unknown'}</div></td><td>{fmtDT(e.start_time)}</td><td>{e.location || '—'}</td>
            <td>{e.confirmed_count}/{e.capacity}{e.waitlist_count ? <div className="muted">{e.waitlist_count} waitlisted</div> : null}</td><td><Badge v={e.status} /></td></tr>)}
        </tbody></table></div><Pager data={data} onPage={(p) => setQ((s) => ({ ...s, page: p }))} /></>)}
      {open && <Modal title="New event" onClose={() => setOpen(false)}><EventForm orgId={orgId} onDone={(ev) => nav(`/events/${ev.id}`)} /></Modal>}
    </>
  );
}
