import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api, { API_URL, setLogoutHandler, tokens } from './api.js';

const Ctx = createContext(null);
export const useAuth = () => useContext(Ctx);
export const RANK = { participant: 1, staff: 2, event_manager: 3, org_admin: 4 };
export const ROLE_LABEL = { participant: 'Participant', staff: 'Staff', event_manager: 'Event manager', org_admin: 'Organization admin' };

export function AuthProvider({ children }) {
  const nav = useNavigate();
  const [user, setUser] = useState(null);
  const [orgs, setOrgs] = useState([]);
  const [orgId, setOrgId] = useState(() => Number(localStorage.getItem('orgId')) || null);
  const [booting, setBooting] = useState(!!tokens.access);
  const [unread, setUnread] = useState(0);
  const [toasts, setToasts] = useState([]);
  const [theme, setThemeState] = useState(() => localStorage.getItem('theme') || 'light');
  const wsRef = useRef(null);

  useEffect(() => { document.documentElement.dataset.theme = theme; localStorage.setItem('theme', theme); }, [theme]);

  const toast = useCallback((msg, kind = 'info') => {
    const id = Math.random();
    setToasts((t) => [...t, { id, msg, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500);
  }, []);

  const logout = useCallback(() => {
    tokens.clear(); wsRef.current?.close(); setUser(null); setOrgs([]); nav('/login');
  }, [nav]);
  useEffect(() => { setLogoutHandler(logout); }, [logout]);

  const loadOrgs = useCallback(async () => {
    const { data } = await api.get('/api/organizations');
    setOrgs(data);
    setOrgId((cur) => (data.find((o) => o.id === cur) ? cur : data[0]?.id ?? null));
    return data;
  }, []);

  const refreshUnread = useCallback(async () => {
    try { setUnread((await api.get('/api/notifications/unread-count')).data.count); } catch { /* ignore */ }
  }, []);

  const bootstrap = useCallback(async () => {
    const { data } = await api.get('/api/auth/me');
    setUser(data);
    await loadOrgs();
    refreshUnread();
  }, [loadOrgs, refreshUnread]);

  useEffect(() => {
    if (!tokens.access) return;
    bootstrap().catch(() => tokens.clear()).finally(() => setBooting(false));
  }, [bootstrap]);

  useEffect(() => { if (orgId) localStorage.setItem('orgId', orgId); }, [orgId]);

  // Real-time channel: pushes notifications and "something changed" signals; REST endpoints remain the fallback.
  useEffect(() => {
    if (!user) return undefined;
    let closed = false; let retry;
    const connect = () => {
      const ws = new WebSocket(`${API_URL.replace(/^http/, 'ws')}/ws?token=${tokens.access}`);
      wsRef.current = ws;
      ws.onmessage = (m) => {
        try {
          const msg = JSON.parse(m.data);
          if (msg.event === 'notification') { setUnread((n) => n + 1); toast(msg.data.title, 'info'); }
          window.dispatchEvent(new CustomEvent('eventhub:ws', { detail: msg }));
        } catch { /* pong */ }
      };
      ws.onclose = () => { if (!closed) retry = setTimeout(connect, 5000); };
    };
    connect();
    const ping = setInterval(() => wsRef.current?.readyState === 1 && wsRef.current.send('ping'), 25000);
    return () => { closed = true; clearTimeout(retry); clearInterval(ping); wsRef.current?.close(); };
  }, [user, toast]);

  const login = async (email, password) => {
    const { data } = await api.post('/api/auth/login', { email, password });
    tokens.set(data.access_token, data.refresh_token);
    setUser(data.user);
    await loadOrgs();
    refreshUnread();
  };

  const register = async (form) => { await api.post('/api/auth/register', form); await login(form.email, form.password); };

  const doLogout = async () => {
    try { if (tokens.refresh) await api.post('/api/auth/logout', { refresh_token: tokens.refresh }); } catch { /* ignore */ }
    logout();
  };

  const org = orgs.find((o) => o.id === orgId) || null;
  const role = org?.my_role || null;
  const can = (min) => !!role && RANK[role] >= RANK[min];

  return (
    <Ctx.Provider value={{ user, setUser, orgs, org, orgId, setOrgId, role, can, loadOrgs, booting, login, register, logout: doLogout,
                          unread, refreshUnread, setUnread, toast, theme, setTheme: setThemeState }}>
      {children}
      <div className="toasts" aria-live="polite">{toasts.map((t) => <div key={t.id} className={`toast ${t.kind}`}>{t.msg}</div>)}</div>
    </Ctx.Provider>
  );
}
