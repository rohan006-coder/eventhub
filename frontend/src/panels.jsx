import { useState } from 'react';
import api, { errMsg } from './api.js';
import { RANK, useAuth } from './auth.jsx';
import { Badge, Empty, ErrorBox, Field, Loading, Modal, Pager, download, fmtDT, toISO, toLocalInput, useFetch, useForm, useLive } from './ui.jsx';

/* ------------------------------------------------------------- registrations (staff view of one event) */
export function RegistrationsPanel({ event }) {
  const { toast } = useAuth();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState('');
  const { data, loading, error, reload } = useFetch(async () => (await api.get(`/api/events/${event.id}/registrations`, { params: { page, page_size: 15, status: status || undefined } })).data, [event.id, page, status]);
  useLive(['registration.created', 'registration.updated'], reload);
  const act = async (id, action) => { try { await api.post(`/api/registrations/${id}/${action}`); toast(`Registration ${action}d`, 'success'); reload(); } catch (e) { toast(errMsg(e), 'error'); } };
  return (
    <>
      <div className="filters"><div><label>Status</label><select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
        <option value="">All</option>{['pending', 'confirmed', 'waitlisted', 'cancelled', 'rejected', 'attended', 'no_show'].map((s) => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}</select></div></div>
      <ErrorBox error={error} onRetry={reload} />
      {loading && !data ? <Loading /> : !data?.items.length ? <Empty title="No registrations">Nobody matches this filter yet.</Empty> : (<>
        <div className="tablewrap"><table><thead><tr><th>Participant</th><th>Registered</th><th>Status</th><th /></tr></thead><tbody>
          {data.items.map((r) => <tr key={r.id}><td>{r.user.full_name}<div className="muted">{r.user.email}</div></td><td>{fmtDT(r.created_at)}</td><td><Badge v={r.status} /></td>
            <td className="row">{r.status === 'pending' && <button className="small primary" onClick={() => act(r.id, 'approve')}>Approve</button>}
              {['pending', 'waitlisted'].includes(r.status) && <button className="small danger" onClick={() => act(r.id, 'reject')}>Reject</button>}
              {['pending', 'confirmed', 'waitlisted'].includes(r.status) && <button className="small" onClick={() => act(r.id, 'cancel')}>Cancel</button>}</td></tr>)}
        </tbody></table></div><Pager data={data} onPage={setPage} /></>)}
    </>
  );
}

/* ------------------------------------------------------------- sessions */
function SessionForm({ event, session, rooms, speakers, onDone }) {
  const f = useForm({
    title: session?.title || '', description: session?.description || '', start_time: toLocalInput(session?.start_time || event.start_time), end_time: toLocalInput(session?.end_time || event.end_time),
    room_id: session?.room_id || '', capacity: session?.capacity || '', speaker_ids: session?.speakers?.map((s) => s.id) || [],
  }, (v) => ({
    ...(!v.title.trim() && { title: 'Enter a title.' }),
    ...(v.start_time && v.end_time && new Date(v.end_time) <= new Date(v.start_time) && { end_time: 'End must be after start.' }),
    ...(v.start_time && new Date(v.start_time) < new Date(event.start_time) && { start_time: 'Starts before the event.' }),
    ...(v.end_time && new Date(v.end_time) > new Date(event.end_time) && { end_time: 'Ends after the event.' }),
  }), async (v) => {
    const body = { title: v.title, description: v.description, start_time: toISO(v.start_time), end_time: toISO(v.end_time), room_id: v.room_id ? Number(v.room_id) : null, capacity: v.capacity ? Number(v.capacity) : null, speaker_ids: v.speaker_ids };
    if (session) await api.patch(`/api/sessions/${session.id}`, body); else await api.post(`/api/events/${event.id}/sessions`, body);
    onDone();
  });
  return (
    <form onSubmit={f.submit} noValidate>
      {f.serverError && <div className="alert" role="alert">{f.serverError}</div>}
      <div className="form-grid">
        <Field label="Title" error={f.errors.title}><input value={f.values.title} onChange={f.set('title')} /></Field>
        <Field label="Room"><select value={f.values.room_id} onChange={f.set('room_id')}><option value="">No room</option>{rooms.map((r) => <option key={r.id} value={r.id}>{r.name}{r.capacity ? ` (${r.capacity})` : ''}</option>)}</select></Field>
        <Field label="Starts" error={f.errors.start_time}><input type="datetime-local" value={f.values.start_time} onChange={f.set('start_time')} /></Field>
        <Field label="Ends" error={f.errors.end_time}><input type="datetime-local" value={f.values.end_time} onChange={f.set('end_time')} /></Field>
        <Field label="Capacity"><input type="number" min="1" value={f.values.capacity} onChange={f.set('capacity')} /></Field>
        <Field label="Speakers (hold Ctrl/Cmd for several)"><select multiple value={f.values.speaker_ids.map(String)} onChange={(e) => f.set('speaker_ids')([...e.target.selectedOptions].map((o) => Number(o.value)))}>
          {speakers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></Field>
      </div>
      <Field label="Description"><textarea rows={2} value={f.values.description} onChange={f.set('description')} /></Field>
      <button className="primary" disabled={f.busy}>{session ? 'Save session' : 'Add session'}</button>
    </form>
  );
}

function SpeakerForm({ orgId, onDone }) {
  const f = useForm({ name: '', email: '', company: '' }, (v) => (!v.name.trim() ? { name: 'Enter a name.' } : {}),
    async (v) => { await api.post('/api/speakers', { organization_id: orgId, name: v.name, email: v.email || null, company: v.company }); onDone(); });
  return (
    <form onSubmit={f.submit} noValidate>
      {f.serverError && <div className="alert">{f.serverError}</div>}
      <div className="form-grid"><Field label="Name" error={f.errors.name}><input value={f.values.name} onChange={f.set('name')} /></Field>
        <Field label="Email"><input type="email" value={f.values.email} onChange={f.set('email')} /></Field>
        <Field label="Company"><input value={f.values.company} onChange={f.set('company')} /></Field></div>
      <button className="primary" disabled={f.busy}>Add speaker</button>
    </form>
  );
}

export function SessionsPanel({ event }) {
  const { orgId, role, toast } = useAuth();
  const manage = RANK[role] >= RANK.event_manager && !['cancelled', 'completed', 'archived'].includes(event.status);
  const { data: sessions, loading, error, reload } = useFetch(async () => (await api.get(`/api/events/${event.id}/sessions`)).data, [event.id]);
  const meta = useFetch(async () => ({
    rooms: (await api.get('/api/resources', { params: { organization_id: orgId, status: 'active', page_size: 100 } })).data.items,
    speakers: (await api.get('/api/speakers', { params: { organization_id: orgId, page_size: 100 } })).data.items,
  }), [orgId, event.id], { skip: !manage });
  const [modal, setModal] = useState(null); // {session?} | 'speaker'
  const del = async (s) => { if (!window.confirm(`Delete "${s.title}"?`)) return; try { await api.delete(`/api/sessions/${s.id}`); toast('Session deleted', 'success'); reload(); } catch (e) { toast(errMsg(e), 'error'); } };
  const roomName = (id) => meta.data?.rooms.find((r) => r.id === id)?.name;
  return (
    <>
      {manage && <div className="row" style={{ marginBottom: '.75rem' }}><button className="primary" onClick={() => setModal({})} disabled={!meta.data}>Add session</button><button onClick={() => setModal('speaker')}>Add speaker</button></div>}
      <ErrorBox error={error} onRetry={reload} />
      {loading && !sessions ? <Loading /> : !sessions?.length ? <Empty title="No sessions yet">{manage ? 'Add the first session to build the schedule.' : 'The schedule will appear here once it is published.'}</Empty> : (
        <div className="tablewrap"><table><thead><tr><th>Session</th><th>When</th><th>Room</th><th>Speakers</th>{manage && <th />}</tr></thead><tbody>
          {sessions.map((s) => <tr key={s.id}><td><b>{s.title}</b><div className="muted">{s.description}</div></td><td>{fmtDT(s.start_time)} – {new Date(s.end_time).toLocaleTimeString([], { timeStyle: 'short' })}</td>
            <td>{s.room_id ? roomName(s.room_id) || `#${s.room_id}` : '—'}{s.capacity ? <div className="muted">cap. {s.capacity}</div> : null}</td><td>{s.speakers.map((x) => x.name).join(', ') || '—'}</td>
            {manage && <td className="row"><button className="small" onClick={() => setModal({ session: s })}>Edit</button><button className="small danger" onClick={() => del(s)}>Delete</button></td>}</tr>)}
        </tbody></table></div>)}
      {modal === 'speaker' && <Modal title="Add speaker" onClose={() => setModal(null)}><SpeakerForm orgId={orgId} onDone={() => { setModal(null); meta.reload(); toast('Speaker added', 'success'); }} /></Modal>}
      {modal && modal !== 'speaker' && meta.data && <Modal title={modal.session ? 'Edit session' : 'Add session'} onClose={() => setModal(null)}>
        <SessionForm event={event} session={modal.session} rooms={meta.data.rooms} speakers={meta.data.speakers} onDone={() => { setModal(null); reload(); toast('Session saved', 'success'); }} /></Modal>}
    </>
  );
}

/* ------------------------------------------------------------- attendance */
export function AttendancePanel({ event }) {
  const { toast } = useAuth();
  const regs = useFetch(async () => (await api.get(`/api/events/${event.id}/registrations`, { params: { page_size: 100 } })).data.items.filter((r) => ['confirmed', 'attended', 'no_show'].includes(r.status)), [event.id]);
  const att = useFetch(async () => (await api.get(`/api/events/${event.id}/attendance`, { params: { page_size: 100 } })).data.items, [event.id]);
  useLive(['attendance.updated'], () => { att.reload(); regs.reload(); });
  const byReg = Object.fromEntries((att.data || []).map((a) => [a.registration_id, a]));
  const mark = async (r, status) => {
    try { await api.post(`/api/events/${event.id}/attendance`, { registration_id: r.id, status }); toast('Attendance updated', 'success'); att.reload(); regs.reload(); } catch (e) { toast(errMsg(e), 'error'); }
  };
  const csv = async () => { try { download((await api.get(`/api/events/${event.id}/attendance-report`, { responseType: 'blob' })).data, `attendance-${event.id}.csv`); } catch (e) { toast(errMsg(e), 'error'); } };
  if (regs.loading && !regs.data) return <Loading />;
  const present = (regs.data || []).filter((r) => r.status === 'attended').length;
  return (
    <>
      <div className="spread" style={{ marginBottom: '.75rem' }}><span className="muted">{present} of {regs.data?.length || 0} checked in</span><button onClick={csv}>Download CSV report</button></div>
      <ErrorBox error={regs.error || att.error} />
      {!regs.data?.length ? <Empty title="No confirmed participants">Attendance can be recorded once registrations are confirmed.</Empty> : (
        <div className="tablewrap"><table><thead><tr><th>Participant</th><th>Status</th><th>Checked in</th><th /></tr></thead><tbody>
          {regs.data.map((r) => <tr key={r.id}><td>{r.user.full_name}</td><td><Badge v={r.status} /></td><td>{fmtDT(byReg[r.id]?.checked_in_at)}</td>
            <td className="row"><button className="small primary" disabled={r.status === 'attended'} onClick={() => mark(r, 'attended')}>Check in</button>
              <button className="small" disabled={r.status === 'no_show'} onClick={() => mark(r, 'no_show')}>No-show</button>
              <button className="small" disabled={r.status === 'confirmed'} onClick={() => mark(r, 'registered')}>Reset</button></td></tr>)}
        </tbody></table></div>)}
    </>
  );
}

/* ------------------------------------------------------------- comments */
export function CommentsPanel({ event }) {
  const { user, toast } = useAuth();
  const { data, loading, error, reload } = useFetch(async () => (await api.get('/api/comments', { params: { event_id: event.id, page_size: 100 } })).data, [event.id]);
  useLive(['comment.created'], reload);
  const f = useForm({ body: '' }, (v) => (!v.body.trim() ? { body: 'Write something first.' } : {}), async (v) => { await api.post('/api/comments', { event_id: event.id, body: v.body }); f.setValues({ body: '' }); reload(); });
  const [editing, setEditing] = useState(null);
  const save = async () => { try { await api.patch(`/api/comments/${editing.id}`, { body: editing.body }); setEditing(null); reload(); } catch (e) { toast(errMsg(e), 'error'); } };
  const del = async (c) => { try { await api.delete(`/api/comments/${c.id}`); reload(); } catch (e) { toast(errMsg(e), 'error'); } };
  return (
    <>
      <form onSubmit={f.submit} noValidate className="card">
        <Field label="Add a comment — mention people with @username" error={f.errors.body}><textarea rows={2} value={f.values.body} onChange={f.set('body')} /></Field>
        {f.serverError && <div className="alert">{f.serverError}</div>}
        <button className="primary" disabled={f.busy}>Post comment</button>
      </form>
      <ErrorBox error={error} onRetry={reload} />
      {loading && !data ? <Loading /> : !data?.items.length ? <Empty title="No comments yet">Start the discussion above.</Empty> : data.items.map((c) => (
        <div className="comment" key={c.id}>
          <div className="spread"><b>{c.author_name}</b><span className="muted">{fmtDT(c.created_at)}</span></div>
          {editing?.id === c.id ? (<><textarea rows={2} value={editing.body} onChange={(e) => setEditing({ ...editing, body: e.target.value })} /><div className="row"><button className="small primary" onClick={save}>Save</button><button className="small" onClick={() => setEditing(null)}>Cancel</button></div></>)
            : <p style={{ margin: '.25rem 0', whiteSpace: 'pre-wrap' }}>{c.body}</p>}
          {c.user_id === user.id && editing?.id !== c.id && <div className="row"><button className="small" onClick={() => setEditing({ id: c.id, body: c.body })}>Edit</button><button className="small danger" onClick={() => del(c)}>Delete</button></div>}
        </div>))}
    </>
  );
}

/* ------------------------------------------------------------- files */
export function FilesPanel({ event }) {
  const { can, toast } = useAuth();
  const { data, loading, error, reload } = useFetch(async () => (await api.get(`/api/events/${event.id}/attachments`)).data, [event.id]);
  const [busy, setBusy] = useState(false);
  const upload = async (e) => {
    const file = e.target.files[0]; e.target.value = '';
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { toast('File is larger than 10 MB.', 'error'); return; }
    const fd = new FormData(); fd.append('file', file); fd.append('entity_type', 'event'); fd.append('entity_id', event.id);
    setBusy(true);
    try { await api.post(`/api/events/${event.id}/attachments`, fd); toast('File uploaded', 'success'); reload(); } catch (er) { toast(errMsg(er), 'error'); } finally { setBusy(false); }
  };
  const get = async (f) => { try { download((await api.get(`/api/attachments/${f.id}/download`, { responseType: 'blob' })).data, f.file_name); } catch (e) { toast(errMsg(e), 'error'); } };
  const del = async (f) => { try { await api.delete(`/api/attachments/${f.id}`); reload(); } catch (e) { toast(errMsg(e), 'error'); } };
  return (
    <>
      {can('staff') && <div className="card"><label htmlFor="up">Upload a file (PDF, image, text/CSV, Word, Excel, PowerPoint — max 10 MB)</label>
        <input id="up" type="file" onChange={upload} disabled={busy} accept=".pdf,.png,.jpg,.jpeg,.gif,.txt,.md,.csv,.docx,.xlsx,.pptx" />{busy && <span className="spinner" />}</div>}
      <ErrorBox error={error} onRetry={reload} />
      {loading && !data ? <Loading /> : !data?.length ? <Empty title="No files">Documents shared for this event will show up here.</Empty> : (
        <div className="tablewrap"><table><thead><tr><th>Name</th><th>Type</th><th>Size</th><th>Uploaded</th><th /></tr></thead><tbody>
          {data.map((f) => <tr key={f.id}><td>{f.file_name}<div className="muted">{f.entity_type}</div></td><td>{f.mime_type.split('/').pop()}</td><td>{(f.file_size / 1024).toFixed(1)} KB</td><td>{fmtDT(f.created_at)}</td>
            <td className="row"><button className="small" onClick={() => get(f)}>Download</button>{can('event_manager') && <button className="small danger" onClick={() => del(f)}>Delete</button>}</td></tr>)}
        </tbody></table></div>)}
    </>
  );
}
