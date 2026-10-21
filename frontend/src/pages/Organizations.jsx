import { useState } from 'react';
import api from '../api.js';
import { useAuth } from '../auth.jsx';
import { Empty, Field, Modal, useForm, fmtD } from '../ui.jsx';

export default function Organizations() {
  const { orgs, orgId, setOrgId, loadOrgs, toast, can, org } = useAuth();
  const [open, setOpen] = useState(false);
  const [edit, setEdit] = useState(false);
  const create = useForm({ name: '', description: '' }, (v) => (v.name.trim().length < 2 ? { name: 'Name must be at least 2 characters.' } : {}),
    async (v) => { const { data } = await api.post('/api/organizations', v); await loadOrgs(); setOrgId(data.id); setOpen(false); toast('Organization created', 'success'); });
  const upd = useForm({ name: org?.name || '', description: org?.description || '' }, (v) => (v.name.trim().length < 2 ? { name: 'Name must be at least 2 characters.' } : {}),
    async (v) => { await api.patch(`/api/organizations/${orgId}`, v); await loadOrgs(); setEdit(false); toast('Organization updated', 'success'); });
  return (
    <>
      <div className="pagehead"><div><h1>Organizations</h1><p className="muted">Each organization has its own events, resources and members.</p></div>
        <button className="primary" onClick={() => setOpen(true)}>New organization</button></div>
      {!orgs.length ? <div className="card"><Empty title="You're not in an organization yet">Create one to start planning events, or ask an admin to add you.</Empty></div> : (
        <div className="tablewrap"><table><thead><tr><th>Name</th><th>Your role</th><th>Created</th><th /></tr></thead><tbody>
          {orgs.map((o) => <tr key={o.id}><td><b>{o.name}</b><div className="muted">{o.description}</div></td><td>{o.my_role.replace('_', ' ')}</td><td>{fmtD(o.created_at)}</td>
            <td>{o.id === orgId ? <div className="row"><span className="badge active">Current</span>{can('org_admin') && <button className="small" onClick={() => setEdit(true)}>Edit</button>}</div> : <button className="small" onClick={() => setOrgId(o.id)}>Switch to</button>}</td></tr>)}
        </tbody></table></div>)}
      {open && <Modal title="New organization" onClose={() => setOpen(false)}>
        <form onSubmit={create.submit} noValidate>
          {create.serverError && <div className="alert">{create.serverError}</div>}
          <Field label="Name" error={create.errors.name}><input value={create.values.name} onChange={create.set('name')} /></Field>
          <Field label="Description"><textarea rows={3} value={create.values.description} onChange={create.set('description')} /></Field>
          <button className="primary" disabled={create.busy}>Create organization</button>
        </form></Modal>}
      {edit && <Modal title="Edit organization" onClose={() => setEdit(false)}>
        <form onSubmit={upd.submit} noValidate>
          {upd.serverError && <div className="alert">{upd.serverError}</div>}
          <Field label="Name" error={upd.errors.name}><input value={upd.values.name} onChange={upd.set('name')} /></Field>
          <Field label="Description"><textarea rows={3} value={upd.values.description} onChange={upd.set('description')} /></Field>
          <button className="primary" disabled={upd.busy}>Save changes</button>
        </form></Modal>}
    </>
  );
}
