import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth.jsx';
import { Field, useForm } from '../ui.jsx';

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const f = useForm({ email: '', password: '' },
    (v) => ({ ...(!/^\S+@\S+\.\S+$/.test(v.email) && { email: 'Enter a valid email address.' }), ...(!v.password && { password: 'Enter your password.' }) }),
    async (v) => { await login(v.email, v.password); nav(loc.state?.from || '/', { replace: true }); });
  return (
    <div className="auth-wrap">
      <form className="card auth-card" onSubmit={f.submit} noValidate>
        <h1>Sign in</h1>
        <p className="muted">Manage events, rooms and registrations.</p>
        {f.serverError && <div className="alert" role="alert">{f.serverError}</div>}
        <Field label="Email" error={f.errors.email}><input type="email" autoComplete="email" value={f.values.email} onChange={f.set('email')} /></Field>
        <Field label="Password" error={f.errors.password}><input type="password" autoComplete="current-password" value={f.values.password} onChange={f.set('password')} /></Field>
        <button className="primary" disabled={f.busy} style={{ width: '100%' }}>{f.busy ? 'Signing in…' : 'Sign in'}</button>
        <p className="muted">New here? <Link to="/register">Create an account</Link></p>
      </form>
    </div>
  );
}
