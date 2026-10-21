import axios from 'axios';

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const api = axios.create({ baseURL: API_URL });

export const tokens = {
  get access() { return localStorage.getItem('access'); },
  get refresh() { return localStorage.getItem('refresh'); },
  set(a, r) { localStorage.setItem('access', a); localStorage.setItem('refresh', r); },
  clear() { localStorage.removeItem('access'); localStorage.removeItem('refresh'); },
};

let onLogout = () => {};
export const setLogoutHandler = (fn) => { onLogout = fn; };

api.interceptors.request.use((cfg) => {
  if (tokens.access) cfg.headers.Authorization = `Bearer ${tokens.access}`;
  return cfg;
});

// On an expired access token: rotate the refresh token once (shared promise) and replay the request.
let refreshing = null;
api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const { response, config } = error;
    const code = response?.data?.error?.code;
    if (response?.status === 401 && code === 'TOKEN_EXPIRED' && !config._retried && tokens.refresh) {
      config._retried = true;
      try {
        refreshing = refreshing || axios.post(`${API_URL}/api/auth/refresh`, { refresh_token: tokens.refresh }).finally(() => { refreshing = null; });
        const { data } = await refreshing;
        tokens.set(data.access_token, data.refresh_token);
        return api(config);
      } catch (e) {
        tokens.clear();
        onLogout();
      }
    } else if (response?.status === 401 && !config.url.includes('/auth/login')) {
      tokens.clear();
      onLogout();
    }
    return Promise.reject(error);
  }
);

export function errMsg(e) {
  const err = e?.response?.data?.error;
  if (err?.details?.length) return `${err.message} ${err.details.map((d) => `${d.field}: ${d.message}`).join('; ')}`;
  return err?.message || e?.message || 'Something went wrong.';
}
export const errCode = (e) => e?.response?.data?.error?.code;

export default api;
