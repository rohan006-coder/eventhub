import { useCallback, useEffect, useRef, useState } from 'react';
import { errMsg } from './api.js';

export const fmtDT = (s) => (s ? new Date(s).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '—');
export const fmtD = (s) => (s ? new Date(s).toLocaleDateString([], { dateStyle: 'medium' }) : '—');
export const fmtT = (s) => new Date(s).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
export const label = (s) => (s || '').replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());
// <input type="datetime-local"> <-> ISO (UTC)
export const toLocalInput = (iso) => { if (!iso) return ''; const d = new Date(iso); const p = (n) => String(n).padStart(2, '0'); return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`; };
export const toISO = (local) => (local ? new Date(local).toISOString() : null);

/** Data fetching with loading / error / reload. `fn` is re-run whenever `deps` change. */
export function useFetch(fn, deps = [], { skip = false } = {}) {
  const [state, setState] = useState({ data: null, loading: !skip, error: null });
  const seq = useRef(0);
  const run = useCallback(async () => {
    const id = ++seq.current;
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await fn();
      if (id === seq.current) setState({ data, loading: false, error: null });
    } catch (e) {
      if (id === seq.current) setState({ data: null, loading: false, error: errMsg(e) });
    }
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (!skip) run(); }, [run, skip]);
  return { ...state, reload: run };
}

/** Reload when a websocket push of one of `events` arrives. */
export function useLive(events, cb) {
  useEffect(() => {
    const h = (e) => { if (events.includes(e.detail.event)) cb(); };
    window.addEventListener('eventhub:ws', h);
    return () => window.removeEventListener('eventhub:ws', h);
  }, [cb]); // eslint-disable-line react-hooks/exhaustive-deps
}

export const Loading = () => <div className="loading"><span className="spinner" role="status" aria-label="Loading" /></div>;
export const ErrorBox = ({ error, onRetry }) => error ? (
  <div className="alert" role="alert">{error} {onRetry && <button className="linklike" onClick={onRetry}>Retry</button>}</div>
) : null;
export const Empty = ({ title, children }) => <div className="empty"><b>{title}</b>{children}</div>;
export const Badge = ({ v }) => <span className={`badge ${v}`}>{label(v)}</span>;

export function Stat({ n, label: l }) { return <div className="stat"><b>{n ?? '—'}</b><span>{l}</span></div>; }

export function Pager({ data, onPage }) {
  if (!data || data.pages <= 1) return null;
  return (
    <div className="pager">
      <span className="muted">Page {data.page} of {data.pages} · {data.total} total</span>
      <button disabled={data.page <= 1} onClick={() => onPage(data.page - 1)}>Previous</button>
      <button disabled={data.page >= data.pages} onClick={() => onPage(data.page + 1)}>Next</button>
    </div>
  );
}

export function Modal({ title, onClose, children }) {
  useEffect(() => { const h = (e) => e.key === 'Escape' && onClose(); window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h); }, [onClose]);
  return (
    <div className="modal-back" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
        <div className="spread"><h2>{title}</h2><button className="small" onClick={onClose} aria-label="Close">Close</button></div>
        {children}
      </div>
    </div>
  );
}

export function Field({ label: l, error, children }) {
  return <div className="field"><label>{l}</label>{children}{error && <div className="err" role="alert">{error}</div>}</div>;
}

/** Tiny form helper: values, change handlers, validation rules, submit with busy + server error state. */
export function useForm(initial, validate, onSubmit) {
  const [values, setValues] = useState(initial);
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const [serverError, setServerError] = useState(null);
  const set = (k) => (e) => setValues((v) => ({ ...v, [k]: e?.target ? (e.target.type === 'checkbox' ? e.target.checked : e.target.value) : e }));
  const submit = async (e) => {
    e?.preventDefault();
    const errs = validate ? validate(values) : {};
    setErrors(errs); setServerError(null);
    if (Object.keys(errs).length) return;
    setBusy(true);
    try { await onSubmit(values); } catch (er) { setServerError(errMsg(er)); } finally { setBusy(false); }
  };
  return { values, set, setValues, errors, busy, serverError, submit };
}

export function BarChart({ data }) {
  const entries = Object.entries(data || {});
  if (!entries.length) return <Empty title="No data yet" />;
  const max = Math.max(...entries.map(([, v]) => v), 1);
  return (
    <div className="bars" role="img" aria-label="Bar chart">
      {entries.map(([k, v]) => (
        <div className="bar" key={k}><span>{label(k)}</span><i style={{ width: `${(v / max) * 100}%` }} /><b>{v}</b></div>
      ))}
    </div>
  );
}

export function download(blob, name) {
  const url = URL.createObjectURL(blob); const a = document.createElement('a');
  a.href = url; a.download = name; a.click(); URL.revokeObjectURL(url);
}
