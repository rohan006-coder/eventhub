import { useAuth } from '../auth.jsx';

export default function Settings() {
  const { theme, setTheme, logout, org } = useAuth();
  return (
    <>
      <div className="pagehead"><div><h1>Settings</h1></div></div>
      <div className="card" style={{ maxWidth: 520 }}>
        <h2>Appearance</h2>
        <label htmlFor="theme">Theme</label>
        <select id="theme" value={theme} onChange={(e) => setTheme(e.target.value)}><option value="light">Light</option><option value="dark">Dark</option></select>
      </div>
      <div className="card" style={{ maxWidth: 520 }}>
        <h2>Session</h2><p className="muted">Signing out revokes your refresh token on the server.</p>
        {org && <p className="muted">Working in <b>{org.name}</b>. Use the selector in the top bar to switch organizations.</p>}
        <button className="danger" onClick={logout}>Sign out</button>
      </div>
    </>
  );
}
