import { useState } from 'react';
import api, { errMsg } from '../api.js';
import { useAuth } from '../auth.jsx';
import { Badge, Empty, ErrorBox, Field, Loading, Modal, Pager, fmtDT, toISO, useFetch, useForm, useLive } from '../ui.jsx';

function BookingForm({ resources, events, onDone }) {
  const f = useForm({ resource_id: resources[0]?.id || '', event_id: '', start_time: '', end_time: '', purpose: '' },
    (v) => ({ ...(!v.resource_id && { resource_id: 'Choose a resource.' }), ...(!v.start_time && { start_time: 'Choose a start.' }), ...(!v.end_time && { end_time: 'Choose an end.' }),
      ...(v.start_time && v.end_time && new Date(v.end_time) <= new Date(v.start_time) && { end_time: 'End must be after start.' }) }),
    async (v) => { await api.post('/api/bookings', { resource_id: Number(v.resource_id), event_id: v.event_id ? Number(v.event_id) : null, start_time: toISO(v.start_time), end_time: toISO(v.end_time), purpose: v.purpose }); onDone(); });
  return (
    <form onSubmit={f.submit} noValidate>
      {f.serverError && <div className="alert" role="alert">{f.serverError}</div>}
      <div className="form-grid">
        <Field label="Resource" error={f.errors.resource_id}><select value={f.values.resource_id} onChange={f.set('resource_id')}>{resources.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</select></Field>
        <Field label="For event (optional)"><select value={f.values.event_id} onChange={f.set('event_id')}><option value="">None</option>{events.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}</select></Field>
        <Field label="Starts" error={f.errors.start_time}><input type="datetime-local" value={f.values.start_time} onChange={f.set('start_time')} /></Field>
        <Field label="Ends" error={f.errors.end_time}><input type="datetime-local" value={f.values.end_time} onChange={f.set('end_time')} /></Field>
      </div>
      <Field label="Purpose"><input value={f.values.purpose} onChange={f.set('purpose')} /></Field>
      <button className="primary" disabled={f.busy}>Request booking</button>
    </form>
  );
}

export default function Bookings() {
  const { orgId, can, user, toast } = useAuth();
  const [q, setQ] = useState({ resource_id: '', status: '', date_from: '', date_to: '', page: 1 });
  const [open, setOpen] = useState(false);
  const set = (k) => (e) => setQ((s) => ({ ...s, [k]: e.target.value, page: 1 }));
  const meta = useFetch(async () => ({
    resources: (await api.get('/api/resources', { params: { organization_id: orgId, page_size: 100 } })).data.items,
    events: can('event_manager') ? (await api.get('/api/events', { params: { organization_id: orgId, page_size: 100 } })).data.items : [],
  }), [orgId], { skip: !orgId });
  const { data, loading, error, reload } = useFetch(async () => (await api.get('/api/bookings', { params: { organization_id: orgId, page: q.page, page_size: 10, resource_id: q.resource_id || undefined, status: q.status || undefined,
    date_from: q.date_from ? new Date(q.date_from).toISOString() : undefined, date_to: q.date_to ? new Date(`${q.date_to}T23:59:59`).toISOString() : undefined } })).data, [orgId, JSON.stringify(q)], { skip: !orgId || !can('staff') });
  useLive(['booking.requested'], reload);
  const act = async (id, action) => { try { await api.post(`/api/bookings/${id}/${action}`); toast(`Booking ${action}${action.endsWith('e') ? 'd' : 'ed'}`, 'success'); reload(); } catch (e) { toast(errMsg(e), 'error'); } };
  if (!orgId) return <Empty title="Select an organization first" />;
  if (!can('staff')) return <div className="alert">Bookings are visible to staff, event managers and admins.</div>;
  const rname = Object.fromEntries((meta.data?.resources || []).map((r) => [r.id, r.name]));
  return (
    <>
      <div className="pagehead"><div><h1>Bookings</h1><p className="muted">Overlapping bookings for the same resource are rejected automatically.</p></div>{can('event_manager') && <button className="primary" disabled={!meta.data?.resources.length} onClick={() => setOpen(true)}>New booking</button>}</div>
      <div className="filters">
        <div><label>Resource</label><select value={q.resource_id} onChange={set('resource_id')}><option value="">Any</option>{meta.data?.resources.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</select></div>
        <div><label>Status</label><select value={q.status} onChange={set('status')}><option value="">Any</option>{['requested', 'approved', 'rejected', 'cancelled', 'completed'].map((s) => <option key={s}>{s}</option>)}</select></div>
        <div><label>From</label><input type="date" value={q.date_from} onChange={set('date_from')} /></div>
        <div><label>To</label><input type="date" value={q.date_to} onChange={set('date_to')} /></div>
      </div>
      <ErrorBox error={error} onRetry={reload} />
      {loading && !data ? <Loading /> : !data?.items.length ? <div className="card"><Empty title="No bookings found">Adjust the filters or request a booking.</Empty></div> : (<>
        <div className="tablewrap"><table><thead><tr><th>Resource</th><th>When</th><th>Purpose</th><th>Status</th><th /></tr></thead><tbody>
          {data.items.map((b) => <tr key={b.id}><td><b>{b.resource?.name || rname[b.resource_id]}</b></td><td>{fmtDT(b.start_time)}<div className="muted">to {fmtDT(b.end_time)}</div></td><td>{b.purpose || '—'}</td><td><Badge v={b.status} /></td>
            <td className="row">{can('org_admin') && b.status === 'requested' && <><button className="small primary" onClick={() => act(b.id, 'approve')}>Approve</button><button className="small danger" onClick={() => act(b.id, 'reject')}>Reject</button></>}
              {['requested', 'approved'].includes(b.status) && (b.requested_by === user.id || can('org_admin')) && <button className="small" onClick={() => act(b.id, 'cancel')}>Cancel</button>}</td></tr>)}
        </tbody></table></div><Pager data={data} onPage={(p) => setQ((s) => ({ ...s, page: p }))} /></>)}
      {open && meta.data && <Modal title="New booking" onClose={() => setOpen(false)}><BookingForm resources={meta.data.resources.filter((r) => r.status === 'active')} events={meta.data.events} onDone={() => { setOpen(false); reload(); toast('Booking submitted', 'success'); }} /></Modal>}
    </>
  );
}
