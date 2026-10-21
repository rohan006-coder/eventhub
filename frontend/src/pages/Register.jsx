import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth.jsx';
import { Field, useForm } from '../ui.jsx';

export default function Register() {
  const { register } = useAuth();
  const nav = useNavigate();
  const f = useForm({ full_name: '', username: '', email: '', password: '' }, (v) => ({
    ...(!v.full_name.trim() && { full_name: 'Enter your name.' }),
    ...(!/^[A-Za-z0-9_.-]{3,50}$/.test(v.username) && { username: '3–50 characters: letters, digits, _ . -' }),
    ...(!/^\S+@\S+\.\S+$/.test(v.email) && { email: 'Enter a valid email address.' }),
    ...((v.password.length < 8 || !/[A-Za-z]/.test(v.password) || !/\d/.test(v.password)) && { password: 'At least 8 characters with letters and digits.' }),
  }), async (v) => { await register(v); nav('/organizations', { replace: true }); });
  return (
    <div className="auth-wrap">
      <form className="card auth-card" onSubmit={f.submit} noValidate>
        <h1>Create account</h1>
        {f.serverError && <div className="alert" role="alert">{f.serverError}</div>}
        <Field label="Full name" error={f.errors.full_name}><input value={f.values.full_name} onChange={f.set('full_name')} /></Field>
        <Field label="Username (used for @mentions)" error={f.errors.username}><input value={f.values.username} onChange={f.set('username')} /></Field>
        <Field label="Email" error={f.errors.email}><input type="email" value={f.values.email} onChange={f.set('email')} /></Field>
        <Field label="Password" error={f.errors.password}><input type="password" autoComplete="new-password" value={f.values.password} onChange={f.set('password')} /></Field>
        <button className="primary" disabled={f.busy} style={{ width: '100%' }}>{f.busy ? 'Creating…' : 'Create account'}</button>
        <p className="muted">Already registered? <Link to="/login">Sign in</Link></p>
      </form>
    </div>
  );
}
