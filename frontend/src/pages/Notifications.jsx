import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api, { errMsg } from '../api.js';
import { useAuth } from '../auth.jsx';
import { Empty, ErrorBox, Loading, Pager, fmtDT, label, useFetch, useLive } from '../ui.jsx';

export default function Notifications() {
  const { refreshUnread, toast } = useAuth();
  const nav = useNavigate();
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [page, setPage] = useState(1);
  const { data, loading, error, reload } = useFetch(async () => (await api.get('/api/notifications', { params: { page, page_size: 15, unread_only: unreadOnly } })).data, [page, unreadOnly]);
  useLive(['notification'], () => reload());
  const read = async (n) => {
    try { if (!n.is_read) { await api.patch(`/api/notifications/${n.id}/read`); refreshUnread(); reload(); } if (n.data?.event_id) nav(`/events/${n.data.event_id}`); } catch (e) { toast(errMsg(e), 'error'); }
  };
  const readAll = async () => { try { await api.patch('/api/notifications/read-all'); refreshUnread(); reload(); } catch (e) { toast(errMsg(e), 'error'); } };
  return (
    <>
      <div className="pagehead"><div><h1>Notifications</h1></div>
        <div className="row"><label className="row" style={{ margin: 0 }}><input type="checkbox" checked={unreadOnly} onChange={(e) => { setUnreadOnly(e.target.checked); setPage(1); }} /> Unread only</label><button onClick={readAll}>Mark all as read</button></div></div>
      <ErrorBox error={error} onRetry={reload} />
      {loading && !data ? <Loading /> : !data?.items.length ? <div className="card"><Empty title={unreadOnly ? "You're all caught up" : 'No notifications yet'}>Updates about events, registrations and bookings appear here.</Empty></div> : (<>
        <div className="card" style={{ padding: 0 }}>{data.items.map((n) => (
          <button key={n.id} onClick={() => read(n)} style={{ display: 'block', width: '100%', textAlign: 'left', border: 0, borderBottom: '1px solid var(--line)', borderRadius: 0, background: n.is_read ? 'transparent' : 'var(--primary-soft)', padding: '.75rem 1rem' }}>
            <div className="spread"><b>{n.title}</b><span className="muted">{fmtDT(n.created_at)}</span></div>
            <div className="muted">{label(n.type)}{n.message ? ` — ${n.message}` : ''}</div></button>))}</div>
        <Pager data={data} onPage={setPage} /></>)}
    </>
  );
}
