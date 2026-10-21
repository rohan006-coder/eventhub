import { useState } from 'react';
import { Link } from 'react-router-dom';
import api, { errMsg } from '../api.js';
import { useAuth } from '../auth.jsx';
import { Badge, Empty, ErrorBox, Loading, Pager, fmtDT, useFetch, useLive } from '../ui.jsx';

export default function Registrations() {
  const { orgId, can, toast } = useAuth();
  const staff = can('staff');
  const [q, setQ] = useState({ status: '', date_from: '', date_to: '', page: 1 });
  const set = (k) => (e) => setQ((s) => ({ ...s, [k]: e.target.value, page: 1 }));
  const { data, loading, error, reload } = useFetch(async () => (await api.get('/api/registrations', { params: { organization_id: orgId, page: q.page, page_size: 10, status: q.status || undefined,
    date_from: q.date_from ? new Date(q.date_from).toISOString() : undefined, date_to: q.date_to ? new Date(`${q.date_to}T23:59:59`).toISOString() : undefined } })).data, [orgId, JSON.stringify(q)], { skip: !orgId });
  useLive(['registration.created', 'registration.updated', 'registration.approved'], reload);
  const act = async (id, action) => { try { await api.post(`/api/registrations/${id}/${action}`); toast('Registration updated', 'success'); reload(); } catch (e) { toast(errMsg(e), 'error'); } };
  if (!orgId) return <Empty title="Select an organization first" />;
  return (
    <>
      <div className="pagehead"><div><h1>Registrations</h1><p className="muted">{staff ? 'Every registration in this organization.' : 'Your registrations.'}</p></div></div>
      <div className="filters">
        <div><label>Status</label><select value={q.status} onChange={set('status')}><option value="">Any</option>{['pending', 'confirmed', 'waitlisted', 'cancelled', 'rejected', 'attended', 'no_show'].map((s) => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}</select></div>
        <div><label>Registered from</label><input type="date" value={q.date_from} onChange={set('date_from')} /></div>
        <div><label>Registered to</label><input type="date" value={q.date_to} onChange={set('date_to')} /></div>
      </div>
      <ErrorBox error={error} onRetry={reload} />
      {loading && !data ? <Loading /> : !data?.items.length ? <div className="card"><Empty title="No registrations found">{staff ? 'Nothing matches these filters.' : 'Browse events and register to see them here.'} <Link to="/events">View events</Link></Empty></div> : (<>
        <div className="tablewrap"><table><thead><tr><th>Event</th>{staff && <th>Participant</th>}<th>Registered</th><th>Status</th><th /></tr></thead><tbody>
          {data.items.map((r) => <tr key={r.id}><td><Link to={`/events/${r.event_id}`}>{r.event_name}</Link></td>{staff && <td>{r.user.full_name}</td>}<td>{fmtDT(r.created_at)}</td><td><Badge v={r.status} /></td>
            <td className="row">{staff && r.status === 'pending' && <button className="small primary" onClick={() => act(r.id, 'approve')}>Approve</button>}
              {staff && ['pending', 'waitlisted'].includes(r.status) && <button className="small danger" onClick={() => act(r.id, 'reject')}>Reject</button>}
              {['pending', 'confirmed', 'waitlisted'].includes(r.status) && <button className="small" onClick={() => act(r.id, 'cancel')}>Cancel</button>}</td></tr>)}
        </tbody></table></div><Pager data={data} onPage={(p) => setQ((s) => ({ ...s, page: p }))} /></>)}
    </>
  );
}
