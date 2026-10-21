import { Navigate, NavLink, Outlet, Route, Routes, useLocation } from 'react-router-dom';
import { useAuth } from './auth.jsx';
import { Loading } from './ui.jsx';
import Login from './pages/Login.jsx';
import Register from './pages/Register.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Organizations from './pages/Organizations.jsx';
import Members from './pages/Members.jsx';
import Events from './pages/Events.jsx';
import EventDetail from './pages/EventDetail.jsx';
import CalendarPage from './pages/CalendarPage.jsx';
import SessionsPage from './pages/SessionsPage.jsx';
import Resources from './pages/Resources.jsx';
import Bookings from './pages/Bookings.jsx';
import Registrations from './pages/Registrations.jsx';
import AttendancePage from './pages/AttendancePage.jsx';
import Notifications from './pages/Notifications.jsx';
import Profile from './pages/Profile.jsx';
import Settings from './pages/Settings.jsx';

function Protected({ min }) {
  const { user, booting, can, org } = useAuth();
  const loc = useLocation();
  if (booting) return <Loading />;
  if (!user) return <Navigate to="/login" state={{ from: loc.pathname }} replace />;
  if (min && org && !can(min)) return <div className="content"><div className="alert">You don't have permission to view this page.</div></div>;
  return <Outlet />;
}

function Shell() {
  const { user, orgs, orgId, setOrgId, org, role, can, unread, logout } = useAuth();
  const links = [
    ['/', 'Dashboard'], ['/calendar', 'Calendar'], ['/events', 'Events'], ['/sessions', 'Sessions'], ['/registrations', 'Registrations'],
    ...(can('staff') ? [['/attendance', 'Attendance']] : []),
    ['/resources', 'Resources'], ['/bookings', 'Bookings'], ['/organizations', 'Organizations'], ['/members', 'Members'],
    ['/notifications', `Notifications${unread ? ` (${unread})` : ''}`], ['/profile', 'Profile'], ['/settings', 'Settings'],
  ];
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">EventHub</div>
        <nav className="nav" aria-label="Main">
          {links.map(([to, text]) => <NavLink key={to} to={to} end={to === '/'}>{text}</NavLink>)}
        </nav>
      </aside>
      <div className="main">
        <header className="topbar">
          <div className="row">
            <label htmlFor="org" style={{ margin: 0 }}>Organization</label>
            <select id="org" style={{ width: 'auto' }} value={orgId || ''} onChange={(e) => setOrgId(Number(e.target.value))} disabled={!orgs.length}>
              {!orgs.length && <option value="">None yet</option>}
              {orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
            </select>
            {role && <span className="badge">{org?.my_role?.replace('_', ' ')}</span>}
          </div>
          <div className="row"><span className="muted">{user.full_name}</span><button className="small" onClick={logout}>Sign out</button></div>
        </header>
        <main className="content"><Outlet /></main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route element={<Protected />}>
        <Route element={<Shell />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/organizations" element={<Organizations />} />
          <Route path="/members" element={<Members />} />
          <Route path="/events" element={<Events />} />
          <Route path="/events/:id" element={<EventDetail />} />
          <Route path="/calendar" element={<CalendarPage />} />
          <Route path="/sessions" element={<SessionsPage />} />
          <Route path="/resources" element={<Resources />} />
          <Route path="/bookings" element={<Bookings />} />
          <Route path="/registrations" element={<Registrations />} />
          <Route element={<Protected min="staff" />}><Route path="/attendance" element={<AttendancePage />} /></Route>
          <Route path="/notifications" element={<Notifications />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
