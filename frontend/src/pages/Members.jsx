import { useState } from 'react';
import api, { errMsg } from '../api.js';
import { ROLE_LABEL, useAuth } from '../auth.jsx';
import { Badge, Empty, ErrorBox, Field, Loading, Pager, useFetch, useForm } from '../ui.jsx';

export default function Members() {
  const { orgId, can, toast } = useAuth();
  const [page, setPage] = useState(1);
  const admin = can('org_admin');
  const { data, loading, error, reload } = useFetch(async () => (await api.get(`/api/organizations/${orgId}/members`, { params: { page, page_size: 15 } })).data, [orgId, page], { skip: !orgId || !can('staff') });
  const add = useForm({ email: '', role: 'participant' }, (v) => (!/^\S+@\S+\.\S+$/.test(v.email) ? { email: 'Enter the email of a registered user.' } : {}),
    async (v) => { await api.post(`/api/organizations/${orgId}/members`, v); toast('Member added', 'success'); add.setValues({ email: '', role: 'participant' }); reload(); });
  const act = async (fn, msg) => { try { await fn(); toast(msg, 'success'); reload(); } catch (e) { toast(errMsg(e), 'error'); } };
  if (!orgId) return <Empty title="Select an organization first" />;
  if (!can('staff')) return <div className="alert">Only staff and admins can view the member list.</div>;
  return (
    <>
      <div className="pagehead"><div><h1>Members</h1><p className="muted">People with access to this organization.</p></div></div>
      {admin && (
        <form className="card" onSubmit={add.submit} noValidate>
          <h2>Add a member</h2>{add.serverError && <div className="alert">{add.serverError}</div>}
          <div className="form-grid">
            <Field label="Email (must already have an account)" error={add.errors.email}><input value={add.values.email} onChange={add.set('email')} /></Field>
            <Field label="Role"><select value={add.values.role} onChange={add.set('role')}>{Object.entries(ROLE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
          </div>
          <button className="primary" disabled={add.busy}>Add member</button>
        </form>)}
      <ErrorBox error={error} onRetry={reload} />
      {loading && !data ? <Loading /> : !data?.items.length ? <Empty title="No members" /> : (<>
        <div className="tablewrap"><table><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th>{admin && <th>Actions</th>}</tr></thead><tbody>
          {data.items.map((m) => (
            <tr key={m.id}><td>{m.user.full_name}<div className="muted">@{m.user.username}</div></td><td>{m.user.email}</td>
              <td>{admin ? <select style={{ width: 'auto' }} value={m.role} aria-label={`Role for ${m.user.full_name}`} onChange={(e) => act(() => api.patch(`/api/organizations/${orgId}/members/${m.id}/role`, { role: e.target.value }), 'Role updated')}>
                {Object.entries(ROLE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select> : ROLE_LABEL[m.role]}</td>
              <td><Badge v={m.is_active ? 'active' : 'inactive'} /></td>
              {admin && <td className="row">
                <button className="small" onClick={() => act(() => api.post(`/api/organizations/${orgId}/members/${m.id}/${m.is_active ? 'deactivate' : 'activate'}`), m.is_active ? 'Member deactivated' : 'Member activated')}>{m.is_active ? 'Deactivate' : 'Activate'}</button>
                <button className="small danger" onClick={() => window.confirm(`Remove ${m.user.full_name}?`) && act(() => api.delete(`/api/organizations/${orgId}/members/${m.id}`), 'Member removed')}>Remove</button></td>}
            </tr>))}
        </tbody></table></div><Pager data={data} onPage={setPage} /></>)}
    </>
  );
}
