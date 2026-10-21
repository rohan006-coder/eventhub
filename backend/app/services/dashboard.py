from datetime import timedelta

from sqlalchemy import func, select

from app.core.database import utcnow
from app.core.errors import bad_request
from app.models import models as m
from app.repositories import ACTIVE_REG, OrgRepo
from app.services.permissions import require_role

R, S = m.RegistrationStatus, m.EventStatus


def _n(db, stmt):
    return db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0


def _ev_brief(e): return {"id": e.id, "name": e.name, "start_time": e.start_time, "end_time": e.end_time, "status": e.status.value, "location": e.location}
def _ses_brief(s, ev_name=None): return {"id": s.id, "event_id": s.event_id, "event_name": ev_name, "title": s.title, "start_time": s.start_time, "end_time": s.end_time}


def build(db, user, organization_id=None):
    if not organization_id:
        orgs = OrgRepo(db).for_user(user.id) if not user.is_super_admin else [(o, "org_admin") for o in OrgRepo(db).all()]
        if not orgs:
            return {"role": None, "organization_id": None, "message": "Join or create an organization to see your dashboard."}
        organization_id = orgs[0][0].id
    role = require_role(db, user, organization_id)
    now = utcnow()
    Ev, Rg, Se = m.Event, m.Registration, m.EventSession
    org_events = select(Ev).where(Ev.organization_id == organization_id)
    org_regs = select(Rg).join(Ev, Ev.id == Rg.event_id).where(Ev.organization_id == organization_id, Rg.status.in_(ACTIVE_REG))
    out = {"role": role, "organization_id": organization_id}

    if role == "org_admin":
        by_status = dict(db.execute(select(Ev.status, func.count()).where(Ev.organization_id == organization_id).group_by(Ev.status)).all())
        reg_status = dict(db.execute(select(Rg.status, func.count()).join(Ev, Ev.id == Rg.event_id).where(Ev.organization_id == organization_id).group_by(Rg.status)).all())
        out.update(
            total_events=_n(db, org_events),
            published_events=_n(db, org_events.where(Ev.status == S.published)),
            upcoming_events=_n(db, org_events.where(Ev.status == S.published, Ev.start_time > now)),
            completed_events=_n(db, org_events.where(Ev.status == S.completed)),
            total_members=_n(db, select(m.OrganizationMember).where(m.OrganizationMember.organization_id == organization_id)),
            total_registrations=_n(db, org_regs),
            active_resources=_n(db, select(m.Resource).where(m.Resource.organization_id == organization_id, m.Resource.status == m.ResourceStatus.active)),
            current_bookings=_n(db, select(m.ResourceBooking).join(m.Resource, m.Resource.id == m.ResourceBooking.resource_id).where(
                m.Resource.organization_id == organization_id, m.ResourceBooking.status == m.BookingStatus.approved,
                m.ResourceBooking.start_time <= now, m.ResourceBooking.end_time > now)),
            pending_bookings=_n(db, select(m.ResourceBooking).join(m.Resource, m.Resource.id == m.ResourceBooking.resource_id).where(m.Resource.organization_id == organization_id, m.ResourceBooking.status == m.BookingStatus.requested)),
            events_by_status={k.value: v for k, v in by_status.items()},
            registrations_by_status={k.value: v for k, v in reg_status.items()},
        )
    elif role == "event_manager":
        mine = org_events.where(Ev.organizer_id == user.id)
        my_ids = select(Ev.id).where(Ev.organization_id == organization_id, Ev.organizer_id == user.id)
        att = dict(db.execute(select(m.Attendance.status, func.count()).where(m.Attendance.event_id.in_(my_ids)).group_by(m.Attendance.status)).all())
        attended, noshow = att.get(m.AttendanceStatus.attended, 0), att.get(m.AttendanceStatus.no_show, 0)
        sessions = db.execute(select(Se, Ev.name).join(Ev, Ev.id == Se.event_id).where(Se.event_id.in_(my_ids), Se.start_time > now).order_by(Se.start_time).limit(10)).all()
        out.update(
            my_events=_n(db, mine),
            upcoming_sessions=[_ses_brief(s, n) for s, n in sessions],
            total_registrations=_n(db, select(Rg).where(Rg.event_id.in_(my_ids), Rg.status.in_(ACTIVE_REG))),
            waitlisted_participants=_n(db, select(Rg).where(Rg.event_id.in_(my_ids), Rg.status == R.waitlisted)),
            attendance_rate=round(100 * attended / (attended + noshow), 1) if (attended + noshow) else None,
            resource_bookings=_n(db, select(m.ResourceBooking).join(m.Resource, m.Resource.id == m.ResourceBooking.resource_id).where(
                m.Resource.organization_id == organization_id, m.ResourceBooking.requested_by == user.id,
                m.ResourceBooking.status.in_([m.BookingStatus.requested, m.BookingStatus.approved]))),
            events=[_ev_brief(e) for e in db.scalars(mine.order_by(Ev.start_time.desc()).limit(8))],
        )
    elif role == "staff":
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today = db.execute(select(Se, Ev.name).join(Ev, Ev.id == Se.event_id).where(
            Ev.organization_id == organization_id, Se.start_time >= day_start, Se.start_time < day_start + timedelta(days=1)).order_by(Se.start_time)).all()
        assigned = org_events.where(Ev.status.in_([S.published, S.ongoing]), Ev.end_time > now).order_by(Ev.start_time).limit(8)
        pending = _n(db, org_regs.where(Rg.status == R.pending))
        out.update(
            assigned_events=[_ev_brief(e) for e in db.scalars(assigned)],
            todays_sessions=[_ses_brief(s, n) for s, n in today],
            pending_registrations=pending,
            upcoming_tasks=[{"label": f"Review {pending} pending registration(s)", "count": pending}] if pending else [],
            attendance={"attended": _n(db, select(m.Attendance).join(Ev, Ev.id == m.Attendance.event_id).where(Ev.organization_id == organization_id, m.Attendance.status == m.AttendanceStatus.attended)),
                        "no_show": _n(db, select(m.Attendance).join(Ev, Ev.id == m.Attendance.event_id).where(Ev.organization_id == organization_id, m.Attendance.status == m.AttendanceStatus.no_show))},
        )
    else:  # participant
        mine = select(Rg, Ev).join(Ev, Ev.id == Rg.event_id).where(Ev.organization_id == organization_id, Rg.user_id == user.id)
        rows = db.execute(mine.where(Rg.status.in_(ACTIVE_REG)).order_by(Ev.start_time)).all()
        reg_event_ids = [e.id for _, e in rows]
        upcoming = db.scalars(org_events.where(Ev.status == S.published, Ev.start_time > now).order_by(Ev.start_time).limit(8))
        sessions = db.execute(select(Se, Ev.name).join(Ev, Ev.id == Se.event_id).where(Se.event_id.in_(reg_event_ids or [0]), Se.start_time > now).order_by(Se.start_time).limit(10)).all()
        history = db.execute(select(m.Attendance, Ev).join(Ev, Ev.id == m.Attendance.event_id).where(m.Attendance.user_id == user.id, Ev.organization_id == organization_id).order_by(m.Attendance.id.desc()).limit(10)).all()
        out.update(
            registered_events=[{**_ev_brief(e), "registration_status": r.status.value, "registration_id": r.id} for r, e in rows if r.status != R.waitlisted],
            upcoming_events=[_ev_brief(e) for e in upcoming],
            upcoming_sessions=[_ses_brief(s, n) for s, n in sessions],
            waitlisted_events=[_ev_brief(e) for r, e in rows if r.status == R.waitlisted],
            attendance_history=[{"event": e.name, "status": a.status.value, "checked_in_at": a.checked_in_at} for a, e in history],
        )
    return out


def calendar(db, user, organization_id, start, end):
    role = require_role(db, user, organization_id)
    Ev, Se = m.Event, m.EventSession
    stmt = select(Ev).where(Ev.organization_id == organization_id, Ev.end_time >= start, Ev.start_time <= end)
    if role == "participant":
        stmt = stmt.where(Ev.status != S.draft)
    events = list(db.scalars(stmt.order_by(Ev.start_time)))
    ids = [e.id for e in events] or [0]
    sessions = list(db.scalars(select(Se).where(Se.event_id.in_(ids), Se.end_time >= start, Se.start_time <= end).order_by(Se.start_time)))
    bookings = []
    if role != "participant":
        bookings = db.execute(select(m.ResourceBooking, m.Resource.name).join(m.Resource, m.Resource.id == m.ResourceBooking.resource_id).where(
            m.Resource.organization_id == organization_id, m.ResourceBooking.status.in_([m.BookingStatus.requested, m.BookingStatus.approved]),
            m.ResourceBooking.end_time >= start, m.ResourceBooking.start_time <= end)).all()
    names = {e.id: e.name for e in events}
    return {
        "events": [{"id": e.id, "kind": "event", "title": e.name, "start": e.start_time, "end": e.end_time, "status": e.status.value, "event_id": e.id} for e in events],
        "sessions": [{"id": s.id, "kind": "session", "title": s.title, "start": s.start_time, "end": s.end_time, "event_id": s.event_id, "event_name": names.get(s.event_id)} for s in sessions],
        "bookings": [{"id": b.id, "kind": "booking", "title": f"{n}: {b.purpose or 'Booking'}", "start": b.start_time, "end": b.end_time, "status": b.status.value, "event_id": b.event_id} for b, n in bookings],
    }
