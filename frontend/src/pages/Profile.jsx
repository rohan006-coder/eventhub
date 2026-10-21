import api from '../api.js';
import { ROLE_LABEL, useAuth } from '../auth.jsx';
import { Field, useForm } from '../ui.jsx';

export default function Profile() {
  const { user, setUser, orgs, toast } = useAuth();
  const prof = useForm({ full_name: user.full_name }, (v) => (!v.full_name.trim() ? { full_name: 'Enter your name.' } : {}),
    async (v) => { const { data } = await api.patch('/api/auth/me', v); setUser(data); toast('Profile updated', 'success'); });
  const pw = useForm({ current_password: '', new_password: '', confirm: '' }, (v) => ({
    ...(!v.current_password && { current_password: 'Enter your current password.' }),
    ...((v.new_password.length < 8 || !/\d/.test(v.new_password) || !/[A-Za-z]/.test(v.new_password)) && { new_password: 'At least 8 characters with letters and digits.' }),
    ...(v.confirm !== v.new_password && { confirm: 'Passwords do not match.' }),
  }), async (v) => { await api.post('/api/auth/change-password', { current_password: v.current_password, new_password: v.new_password }); toast('Password changed. Please sign in again.', 'success'); window.setTimeout(() => { localStorage.clear(); window.location.assign('/login'); }, 1200); });
  return (
    <>
      <div className="pagehead"><div><h1>Profile</h1><p className="muted">@{user.username} · {user.email}{user.is_super_admin ? ' · Super admin' : ''}</p></div></div>
      <form className="card" onSubmit={prof.submit} noValidate style={{ maxWidth: 520 }}>
        <h2>Your details</h2>{prof.serverError && <div className="alert">{prof.serverError}</div>}
        <Field label="Full name" error={prof.errors.full_name}><input value={prof.values.full_name} onChange={prof.set('full_name')} /></Field>
        <button className="primary" disabled={prof.busy}>Save changes</button>
      </form>
      <form className="card" onSubmit={pw.submit} noValidate style={{ maxWidth: 520 }}>
        <h2>Change password</h2>{pw.serverError && <div className="alert">{pw.serverError}</div>}
        <Field label="Current password" error={pw.errors.current_password}><input type="password" autoComplete="current-password" value={pw.values.current_password} onChange={pw.set('current_password')} /></Field>
        <Field label="New password" error={pw.errors.new_password}><input type="password" autoComplete="new-password" value={pw.values.new_password} onChange={pw.set('new_password')} /></Field>
        <Field label="Confirm new password" error={pw.errors.confirm}><input type="password" autoComplete="new-password" value={pw.values.confirm} onChange={pw.set('confirm')} /></Field>
        <button className="primary" disabled={pw.busy}>Change password</button>
      </form>
      <div className="card" style={{ maxWidth: 520 }}><h2>Your organizations</h2>{orgs.length ? orgs.map((o) => <p key={o.id}>{o.name} — <span className="muted">{ROLE_LABEL[o.my_role]}</span></p>) : <p className="muted">None yet.</p>}</div>
    </>
  );
}
