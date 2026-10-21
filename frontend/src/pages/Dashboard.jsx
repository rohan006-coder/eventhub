import { Link } from 'react-router-dom';
import api from '../api.js';
import { useAuth } from '../auth.jsx';
import { BarChart, Empty, ErrorBox, Loading, Stat, fmtDT, useFetch, useLive, Badge } from '../ui.jsx';

const EventList = ({ items, empty }) => items?.length ? (
  <div className="tablewrap"><table><tbody>{items.map((e) => (
    <tr key={e.id}><td><Link to={`/events/${e.id}`}>{e.name}</Link></td><td>{fmtDT(e.start_time)}</td><td>{e.registration_status ? <Badge v={e.registration_status} /> : <Badge v={e.status} />}</td></tr>
  ))}</tbody></table></div>
) : <Empty title={empty} />;

const SessionList = ({ items }) => items?.length ? (
  <div className="tablewrap"><table><tbody>{items.map((s) => (
    <tr key={s.id}><td>{s.title}<div className="muted">{s.event_name}</div></td><td>{fmtDT(s.start_time)}</td></tr>
  ))}</tbody></table></div>
) : <Empty title="No sessions scheduled" />;

export default function Dashboard() {
  const { orgId, org } = useAuth();
  const { data: d, loading, error, reload } = useFetch(async () => (await api.get('/api/dashboard', { params: { organization_id: orgId || undefined } })).data, [orgId]);
  useLive(['registration.created', 'registration.updated', 'booking.requested', 'attendance.updated', 'event.cancelled'], reload);
  if (loading && !d) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!d?.role) return <Empty title="Welcome to EventHub">Create an organization to get started. <Link to="/organizations">Go to organizations</Link></Empty>;
  return (
    <>
      <div className="pagehead"><div><h1>Dashboard</h1><p className="muted">{org?.name}</p></div></div>
      {d.role === 'org_admin' && (<>
        <div className="grid">
          <Stat n={d.total_events} label="Total events" /><Stat n={d.published_events} label="Published" /><Stat n={d.upcoming_events} label="Upcoming" />
          <Stat n={d.completed_events} label="Completed" /><Stat n={d.total_members} label="Members" /><Stat n={d.total_registrations} label="Registrations" />
          <Stat n={d.active_resources} label="Active resources" /><Stat n={d.current_bookings} label="In use now" /><Stat n={d.pending_bookings} label="Bookings awaiting approval" />
        </div>
        <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(300px,1fr))' }}>
          <div className="card"><h2>Events by status</h2><BarChart data={d.events_by_status} /></div>
          <div className="card"><h2>Registrations by status</h2><BarChart data={d.registrations_by_status} /></div>
        </div>
      </>)}
      {d.role === 'event_manager' && (<>
        <div className="grid">
          <Stat n={d.my_events} label="My events" /><Stat n={d.total_registrations} label="Registrations" /><Stat n={d.waitlisted_participants} label="Waitlisted" />
          <Stat n={d.attendance_rate == null ? '—' : `${d.attendance_rate}%`} label="Attendance rate" /><Stat n={d.resource_bookings} label="My open bookings" />
        </div>
        <div className="card"><h2>My events</h2><EventList items={d.events} empty="You haven't created any events" /></div>
        <div className="card"><h2>Upcoming sessions</h2><SessionList items={d.upcoming_sessions} /></div>
      </>)}
      {d.role === 'staff' && (<>
        <div className="grid"><Stat n={d.pending_registrations} label="Pending registrations" /><Stat n={d.attendance?.attended} label="Attended" /><Stat n={d.attendance?.no_show} label="No-shows" /></div>
        <div className="card"><h2>Today's sessions</h2><SessionList items={d.todays_sessions} /></div>
        <div className="card"><h2>Upcoming tasks</h2>{d.upcoming_tasks?.length ? d.upcoming_tasks.map((t) => <p key={t.label}><Link to="/registrations">{t.label}</Link></p>) : <Empty title="Nothing waiting for you" />}</div>
        <div className="card"><h2>Assigned events</h2><EventList items={d.assigned_events} empty="No active events" /></div>
      </>)}
      {d.role === 'participant' && (<>
        <div className="card"><h2>Registered events</h2><EventList items={d.registered_events} empty="You haven't registered for anything yet" /></div>
        <div className="card"><h2>Upcoming events</h2><EventList items={d.upcoming_events} empty="No upcoming events" /></div>
        <div className="card"><h2>Upcoming sessions</h2><SessionList items={d.upcoming_sessions} /></div>
        <div className="card"><h2>Waitlisted</h2><EventList items={d.waitlisted_events} empty="You're not on any waitlist" /></div>
        <div className="card"><h2>Attendance history</h2>{d.attendance_history?.length ? <div className="tablewrap"><table><tbody>{d.attendance_history.map((a, i) => <tr key={i}><td>{a.event}</td><td><Badge v={a.status} /></td><td>{fmtDT(a.checked_in_at)}</td></tr>)}</tbody></table></div> : <Empty title="No attendance yet" />}</div>
      </>)}
    </>
  );
}
