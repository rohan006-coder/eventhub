import csv
import io

from app.core.database import utcnow
from app.core.errors import conflict, forbidden, not_found
from app.models.models import Attendance, AttendanceStatus as A, EventStatus as S, RegistrationStatus as R
from app.repositories import AttendanceRepo, EventRepo, MemberRepo, RegistrationRepo
from app.services import notifications as notif
from app.services.audit import audit
from app.services.permissions import RANK, get_event_visible, require_role

CHECKIN_STATUSES = (S.published, S.ongoing, S.completed)
REG_FOR = {A.registered: R.confirmed, A.attended: R.attended, A.no_show: R.no_show}


def _apply(db, user, ev, reg, status: A):
    if reg.status not in (R.confirmed, R.attended, R.no_show):
        raise conflict("INVALID_REGISTRATION_STATUS", "Only confirmed registrations can be checked in.")
    att = AttendanceRepo(db).by_registration(reg.id)
    if not att:
        att = AttendanceRepo(db).add(Attendance(event_id=ev.id, registration_id=reg.id, user_id=reg.user_id))
    att.status, att.marked_by = status, user.id
    att.checked_in_at = utcnow() if status == A.attended else None
    reg.status = REG_FOR[status]
    audit(db, user, "attendance.mark", "attendance", att.id, ev.organization_id, {"status": status.value})
    db.commit()
    staff = MemberRepo(db).user_ids(ev.organization_id, ["staff", "event_manager", "org_admin"])
    notif.broadcast(staff + [reg.user_id], "attendance.updated", {"event_id": ev.id, "attendance_id": att.id, "status": status.value})
    return att


def mark(db, user, event_id, data):
    ev, _ = get_event_visible(db, user, event_id, "staff")
    if ev.status not in CHECKIN_STATUSES:
        raise conflict("INVALID_EVENT_STATUS", "Attendance can only be recorded for published, ongoing or completed events.")
    reg = RegistrationRepo(db).get(data.registration_id)
    if not reg or reg.event_id != ev.id:
        raise not_found("Registration")
    return _apply(db, user, ev, reg, data.status)


def update(db, user, att_id, status: A):
    att = AttendanceRepo(db).get(att_id)
    if not att:
        raise not_found("Attendance record")
    ev = EventRepo(db).get(att.event_id)
    require_role(db, user, ev.organization_id, "staff")
    return _apply(db, user, ev, RegistrationRepo(db).get(att.registration_id), status)


def list_for_event(db, user, event_id, page, size):
    ev, role = get_event_visible(db, user, event_id)
    own_only = None if RANK[role] >= RANK["staff"] else user.id
    return AttendanceRepo(db).for_event(ev.id, own_only, page, size)


def report_csv(db, user, event_id) -> str:
    ev, _ = get_event_visible(db, user, event_id, "staff")
    regs, _t = RegistrationRepo(db).search(event_id=ev.id, size=100000, sort="id")
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["registration_id", "name", "email", "status", "checked_in_at"])
    for r in regs:
        att = AttendanceRepo(db).by_registration(r.id)
        w.writerow([r.id, r.user.full_name, r.user.email, r.status.value, att.checked_in_at.isoformat() if att and att.checked_in_at else ""])
    return out.getvalue()
