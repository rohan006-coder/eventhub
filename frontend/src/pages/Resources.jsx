import { useState } from 'react';
import api, { errMsg } from '../api.js';
import { useAuth } from '../auth.jsx';
import { Badge, Empty, ErrorBox, Field, Loading, Modal, Pager, label, useFetch, useForm } from '../ui.jsx';

const TYPES = ['meeting_room', 'conference_hall', 'projector', 'camera', 'vehicle', 'equipment'];

function ResourceForm({ orgId, resource, onDone }) {
  const f = useForm({ name: resource?.name || '', type: resource?.type || 'meeting_room', location: resource?.location || '', capacity: resource?.capacity ?? '', description: resource?.description || '' },
    (v) => ({ ...(!v.name.trim() && { name: 'Enter a name.' }), ...(v.capacity !== '' && Number(v.capacity) < 0 && { capacity: 'Capacity cannot be negative.' }) }),
    async (v) => {
      const body = { name: v.name, type: v.type, location: v.location, description: v.description, capacity: v.capacity === '' ? null : Number(v.capacity) };
      if (resource) await api.patch(`/api/resources/${resource.id}`, body); else await api.post('/api/resources', { ...body, organization_id: orgId });
      onDone();
    });
  return (
    <form onSubmit={f.submit} noValidate>
      {f.serverError && <div className="alert">{f.serverError}</div>}
      <div className="form-grid">
        <Field label="Name" error={f.errors.name}><input value={f.values.name} onChange={f.set('name')} /></Field>
        <Field label="Type"><select value={f.values.type} onChange={f.set('type')}>{TYPES.map((t) => <option key={t} value={t}>{label(t)}</option>)}</select></Field>
        <Field label="Location"><input value={f.values.location} onChange={f.set('location')} /></Field>
        <Field label="Capacity" error={f.errors.capacity}><input type="number" min="0" value={f.values.capacity} onChange={f.set('capacity')} /></Field>
      </div>
      <Field label="Description"><textarea rows={2} value={f.values.description} onChange={f.set('description')} /></Field>
      <button className="primary" disabled={f.busy}>{resource ? 'Save changes' : 'Create resource'}</button>
    </form>
  );
}

export default function Resources() {
  const { orgId, can, toast } = useAuth();
  const [q, setQ] = useState({ search: '', type: '', status: '', page: 1 });
  const [modal, setModal] = useState(null);
  const set = (k) => (e) => setQ((s) => ({ ...s, [k]: e.target.value, page: 1 }));
  const { data, loading, error, reload } = useFetch(async () => (await api.get('/api/resources', { params: { organization_id: orgId, page: q.page, page_size: 10, search: q.search || undefined, type: q.type || undefined, status: q.status || undefined } })).data, [orgId, JSON.stringify(q)], { skip: !orgId });
  const toggle = async (r) => { try { await api.post(`/api/resources/${r.id}/${r.status === 'active' ? 'deactivate' : 'activate'}`); toast('Resource updated', 'success'); reload(); } catch (e) { toast(errMsg(e), 'error'); } };
  if (!orgId) return <Empty title="Select an organization first" />;
  const admin = can('org_admin');
  return (
    <>
      <div className="pagehead"><div><h1>Resources</h1><p className="muted">Rooms and equipment that can be booked.</p></div>{admin && <button className="primary" onClick={() => setModal({})}>New resource</button>}</div>
      <div className="filters">
        <div><label>Search</label><input value={q.search} onChange={set('search')} placeholder="Name or location" /></div>
        <div><label>Type</label><select value={q.type} onChange={set('type')}><option value="">Any</option>{TYPES.map((t) => <option key={t} value={t}>{label(t)}</option>)}</select></div>
        <div><label>Status</label><select value={q.status} onChange={set('status')}><option value="">Any</option><option value="active">Active</option><option value="inactive">Inactive</option></select></div>
      </div>
      <ErrorBox error={error} onRetry={reload} />
      {loading && !data ? <Loading /> : !data?.items.length ? <div className="card"><Empty title="No resources">{admin ? 'Add a room or piece of equipment to start taking bookings.' : 'Your organization admin has not added any resources yet.'}</Empty></div> : (<>
        <div className="tablewrap"><table><thead><tr><th>Name</th><th>Type</th><th>Location</th><th>Capacity</th><th>Status</th>{admin && <th />}</tr></thead><tbody>
          {data.items.map((r) => <tr key={r.id}><td><b>{r.name}</b><div className="muted">{r.description}</div></td><td>{label(r.type)}</td><td>{r.location || '—'}</td><td>{r.capacity ?? '—'}</td><td><Badge v={r.status} /></td>
            {admin && <td className="row"><button className="small" onClick={() => setModal({ resource: r })}>Edit</button><button className="small" onClick={() => toggle(r)}>{r.status === 'active' ? 'Deactivate' : 'Activate'}</button></td>}</tr>)}
        </tbody></table></div><Pager data={data} onPage={(p) => setQ((s) => ({ ...s, page: p }))} /></>)}
      {modal && <Modal title={modal.resource ? 'Edit resource' : 'New resource'} onClose={() => setModal(null)}><ResourceForm orgId={orgId} resource={modal.resource} onDone={() => { setModal(null); reload(); toast('Resource saved', 'success'); }} /></Modal>}
    </>
  );
}
