import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api, { errMsg } from '../api.js';
import { RANK, useAuth } from '../auth.jsx';
import { AttendancePanel, CommentsPanel, FilesPanel, RegistrationsPanel, SessionsPanel } from '../panels.jsx';
import { Badge, ErrorBox, Loading, Modal, fmtDT, useFetch, useLive } from '../ui.jsx';
import { EventForm } from './Events.jsx';

export default function EventDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { user, role, toast } = useAuth();
  const [tab, setTab] = useState('overview');
  const [edit, setEdit] = useState(false);
  const [busy, setBusy] = useState(false);
  const { data: ev, loading, error, reload } = useFetch(async () => (await api.get(`/api/events/${id}`)).data, [id]);
  const mine = useFetch(async () => (await api.get('/api/registrations', { params: { event_id: id, page_size: 20 } })).data.items.find((r) => ['pending', 'confirmed', 'waitlisted', 'attended', 'no_show'].includes(r.status)) || null, [id]);
  useLive(['event.updated', 'event.cancelled', 'registration.updated', 'registration.created'], () => { reload(); mine.reload(); });
  if (loading && !ev) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  const isStaff = RANK[role] >= RANK.staff;
  const canManage = role === 'org_admin' || (role === 'event_manager' && ev.organizer_id === user.id);
  const run = async (fn, msg, after) => { setBusy(true); try { await fn(); toast(msg, 'success'); after ? after() : (reload(), mine.reload()); } catch (e) { toast(errMsg(e), 'error'); } finally { setBusy(false); } };
  const r = mine.data;
  const next = { published: ['ongoing', 'completed'], ongoing: ['completed'] }[ev.status] || [];
  const tabs = [['overview', 'Overview'], ['sessions', 'Sessions'], ...(isStaff ? [['registrations', 'Registrations'], ['attendance', 'Attendance']] : []), ['files', 'Files'], ['discussion', 'Discussion']];
  return (
    <>
      <div className="pagehead"><div><h1>{ev.name} <Badge v={ev.status} /></h1><p className="muted">{fmtDT(ev.start_time)} – {fmtDT(ev.end_time)} · {ev.location || 'No location'}</p></div>
        {canManage && <div className="row">
          {ev.status === 'draft' && <button className="primary" disabled={busy} onClick={() => run(() => api.post(`/api/events/${id}/publish`), 'Event published')}>Publish</button>}
          {next.map((s) => <button key={s} disabled={busy} onClick={() => run(() => api.post(`/api/events/${id}/transition`, { status: s }), `Marked ${s}`)}>Mark {s}</button>)}
          {['draft', 'published'].includes(ev.status) && <button disabled={busy} onClick={() => setEdit(true)}>Edit</button>}
          {['draft', 'published', 'ongoing'].includes(ev.status) && <button className="danger" disabled={busy} onClick={() => window.confirm('Cancel this event? Registered participants will be notified.') && run(() => api.post(`/api/events/${id}/cancel`), 'Event cancelled')}>Cancel event</button>}
          {['completed', 'cancelled', 'draft'].includes(ev.status) && <button disabled={busy} onClick={() => run(() => api.post(`/api/events/${id}/archive`), 'Event archived')}>Archive</button>}
          {['draft', 'cancelled'].includes(ev.status) && <button className="danger" disabled={busy} onClick={() => window.confirm('Delete permanently?') && run(() => api.delete(`/api/events/${id}`), 'Event deleted', () => nav('/events'))}>Delete</button>}
        </div>}</div>
      <div className="tabs" role="tablist">{tabs.map(([k, t]) => <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{t}</button>)}</div>
      {tab === 'overview' && (
        <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(300px,1fr))' }}>
          <div className="card"><h2>About</h2><p style={{ whiteSpace: 'pre-wrap' }}>{ev.description || 'No description yet.'}</p>
            <p className="muted">Organizer: {ev.organizer_name || '—'}<br />Registration closes: {fmtDT(ev.registration_deadline || ev.start_time)}<br />{ev.requires_approval ? 'Registrations need staff approval.' : 'Registrations are confirmed automatically.'}</p></div>
          <div className="card"><h2>Seats</h2><p><b style={{ fontSize: '1.6rem' }}>{ev.confirmed_count}</b> / {ev.capacity} taken{ev.waitlist_count ? ` · ${ev.waitlist_count} on the waitlist` : ''}</p>
            <progress value={ev.confirmed_count} max={ev.capacity} style={{ width: '100%' }} />
            <div style={{ marginTop: '1rem' }}>
              {r ? (<><p>Your registration: <Badge v={r.status} />{r.waitlist_position ? ` (position ${r.waitlist_position})` : ''}</p>
                {['pending', 'confirmed', 'waitlisted'].includes(r.status) && <button className="danger" disabled={busy} onClick={() => run(() => api.post(`/api/registrations/${r.id}/cancel`), 'Registration cancelled')}>Cancel my registration</button>}</>)
                : ev.status === 'published' ? <button className="primary" disabled={busy} onClick={() => run(() => api.post(`/api/events/${id}/register`, {}), 'Registration submitted')}>{ev.confirmed_count >= ev.capacity ? 'Join the waitlist' : 'Register'}</button>
                  : <p className="muted">Registration is not open for this event.</p>}
            </div></div>
        </div>)}
      {tab === 'sessions' && <SessionsPanel event={ev} />}
      {tab === 'registrations' && isStaff && <RegistrationsPanel event={ev} />}
      {tab === 'attendance' && isStaff && <AttendancePanel event={ev} />}
      {tab === 'files' && <FilesPanel event={ev} />}
      {tab === 'discussion' && <CommentsPanel event={ev} />}
      {edit && <Modal title="Edit event" onClose={() => setEdit(false)}><EventForm orgId={ev.organization_id} event={ev} onDone={() => { setEdit(false); reload(); toast('Event updated', 'success'); }} /></Modal>}
    </>
  );
}
