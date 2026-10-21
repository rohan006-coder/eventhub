from sqlalchemy.exc import IntegrityError

from app.core.database import locked, utcnow
from app.core.errors import conflict, forbidden, not_found
from app.models.models import EventStatus as S, NotificationType as N, Registration, RegistrationStatus as R, WaitlistEntry
from app.repositories import EventRepo, MemberRepo, RegistrationRepo
from app.services import notifications as notif
from app.services.audit import audit
from app.services.permissions import RANK, get_event_visible, require_role

TERMINAL = (R.cancelled, R.rejected, R.attended, R.no_show)


def _initial_status(ev):
    return R.pending if ev.requires_approval else R.confirmed


def _staff_ids(db, ev):
    return MemberRepo(db).user_ids(ev.organization_id, ["staff", "event_manager", "org_admin"])


def promote_waitlist(db, ev):
    """Fill free seats from the waitlist in FIFO order. Caller holds the event lock and commits.
    Returns the promoted registrations, each carrying `_notes` (notifications to push after commit)."""
    repo, promoted = RegistrationRepo(db), []
    free = ev.capacity - repo.seat_count(ev.id)
    for entry in repo.waitlist(ev.id):
        if free <= 0:
            break
        reg = repo.get(entry.registration_id)
        reg.status = _initial_status(ev)
        repo.delete(entry)
        free -= 1
        ntype = N.registration_confirmed if reg.status == R.confirmed else N.registration_confirmed
        msg = "A seat opened up and you were moved off the waitlist."
        reg._notes = notif.notify(db, [reg.user_id], ntype, f"You're in: {ev.name}",
                                  msg if reg.status == R.confirmed else msg + " Your registration awaits approval.",
                                  org_id=ev.organization_id, data={"event_id": ev.id, "registration_id": reg.id})
        promoted.append(reg)
    return promoted


def register(db, user, event_id, notes=""):
    ev, _ = get_event_visible(db, user, event_id, "participant")
    with locked(db, f"event:{ev.id}"):
        db.refresh(ev)
        if ev.status == S.cancelled:
            raise conflict("EVENT_CANCELLED", "This event has been cancelled.")
        if ev.status in (S.ongoing, S.completed):
            raise conflict("REGISTRATION_CLOSED", "Registration for this event is closed.")
        if ev.status != S.published:
            raise conflict("INVALID_EVENT_STATUS", "Only published events accept registrations.")
        if utcnow() > (ev.registration_deadline or ev.start_time):
            raise conflict("REGISTRATION_CLOSED", "Registration for this event is closed.")
        repo = RegistrationRepo(db)
        if repo.active_for(ev.id, user.id):
            raise conflict("DUPLICATE_REGISTRATION", "You are already registered for this event.")
        full = repo.seat_count(ev.id) >= ev.capacity
        reg = Registration(event_id=ev.id, user_id=user.id, status=R.waitlisted if full else _initial_status(ev), notes=notes)
        try:
            repo.add(reg)
            if full:
                repo.add(WaitlistEntry(event_id=ev.id, registration_id=reg.id))
            ntype = {R.waitlisted: N.registration_waitlisted, R.confirmed: N.registration_confirmed}.get(reg.status, N.registration_confirmed)
            title = {R.waitlisted: f"Waitlisted: {ev.name}", R.confirmed: f"Registration confirmed: {ev.name}"}.get(reg.status, f"Registration received: {ev.name}")
            pushes = notif.notify(db, [user.id], ntype, title, org_id=ev.organization_id, data={"event_id": ev.id, "registration_id": reg.id})
            staff = notif.notify(db, [i for i in _staff_ids(db, ev) if i != user.id], N.new_registration,
                                 f"New registration for {ev.name}", f"{user.full_name} registered ({reg.status.value}).",
                                 org_id=ev.organization_id, data={"event_id": ev.id, "registration_id": reg.id})
            audit(db, user, "registration.create", "registration", reg.id, ev.organization_id, {"status": reg.status.value})
            db.commit()
        except IntegrityError:
            db.rollback()
            raise conflict("DUPLICATE_REGISTRATION", "You are already registered for this event.")
    notif.push(pushes + staff)
    notif.broadcast([n.user_id for n in staff], "registration.created", {"event_id": ev.id, "registration_id": reg.id})
    notif.send_email(user.id, title)
    reg.waitlist_position = repo.waitlist_position(reg) if full else None
    return reg


def _load(db, user, reg_id, staff_only=False):
    reg = RegistrationRepo(db).get(reg_id)
    if not reg:
        raise not_found("Registration")
    role = require_role(db, user, reg.event.organization_id)
    is_staff = RANK[role] >= RANK["staff"]
    if staff_only and not is_staff:
        raise forbidden("INSUFFICIENT_PERMISSIONS", "Only staff can perform this action.")
    if not is_staff and reg.user_id != user.id:
        raise forbidden("FORBIDDEN", "You can only access your own registrations.")
    return reg, is_staff


def get(db, user, reg_id):
    reg, _ = _load(db, user, reg_id)
    reg.waitlist_position = RegistrationRepo(db).waitlist_position(reg)
    return reg


def list_for_event(db, user, event_id, page, size, status=None, participant_id=None, date_from=None, date_to=None, sort=None):
    ev, _ = get_event_visible(db, user, event_id, "staff")
    return RegistrationRepo(db).search(event_id=ev.id, status=status, participant_id=participant_id, date_from=date_from, date_to=date_to,
                                       sort=sort, page=page, size=size)


def search(db, user, *, organization_id=None, event_id=None, status=None, participant_id=None, date_from=None, date_to=None, sort=None, page=1, size=20):
    """Staff+ see every registration in the org; everyone else only their own."""
    kw = dict(event_id=event_id, status=status, date_from=date_from, date_to=date_to, sort=sort, page=page, size=size)
    if organization_id:
        role = require_role(db, user, organization_id)
        if RANK[role] >= RANK["staff"]:
            return RegistrationRepo(db).search(org_ids=[organization_id], participant_id=participant_id, **kw)
        return RegistrationRepo(db).search(org_ids=[organization_id], user_id=user.id, **kw)
    return RegistrationRepo(db).search(user_id=user.id, **kw)


def _release(db, reg, new_status, actor, note_type, title):
    ev = reg.event
    with locked(db, f"event:{ev.id}"):
        db.refresh(reg)
        if reg.status in TERMINAL:
            raise conflict("INVALID_REGISTRATION_STATUS", f"A {reg.status.value} registration cannot be changed this way.")
        entry = RegistrationRepo(db).waitlist_entry(reg.id)
        if entry:
            RegistrationRepo(db).delete(entry)
        reg.status, reg.decided_by = new_status, actor.id
        pushes = notif.notify(db, [reg.user_id], note_type, title, org_id=ev.organization_id, data={"event_id": ev.id, "registration_id": reg.id})
        promoted = promote_waitlist(db, ev)  # freed capacity goes straight to the next person in line
        audit(db, actor, f"registration.{new_status.value}", "registration", reg.id, ev.organization_id)
        db.commit()
    notif.push(pushes + [n for r in promoted for n in r._notes])
    notif.broadcast([reg.user_id] + [r.user_id for r in promoted], "registration.updated", {"event_id": ev.id})
    return reg


def cancel(db, user, reg_id):
    reg, _ = _load(db, user, reg_id)
    return _release(db, reg, R.cancelled, user, N.registration_cancelled, f"Registration cancelled: {reg.event.name}")


def reject(db, user, reg_id):
    reg, _ = _load(db, user, reg_id, staff_only=True)
    if reg.status not in (R.pending, R.waitlisted):
        raise conflict("INVALID_REGISTRATION_STATUS", "Only pending or waitlisted registrations can be rejected.")
    return _release(db, reg, R.rejected, user, N.registration_rejected, f"Registration rejected: {reg.event.name}")


def approve(db, user, reg_id):
    reg, _ = _load(db, user, reg_id, staff_only=True)
    ev = reg.event
    with locked(db, f"event:{ev.id}"):
        db.refresh(reg)
        if reg.status != R.pending:
            raise conflict("INVALID_REGISTRATION_STATUS", "Only pending registrations can be approved.")
        reg.status, reg.decided_by = R.confirmed, user.id
        pushes = notif.notify(db, [reg.user_id], N.registration_confirmed, f"Registration confirmed: {ev.name}",
                              org_id=ev.organization_id, data={"event_id": ev.id, "registration_id": reg.id})
        audit(db, user, "registration.approve", "registration", reg.id, ev.organization_id)
        db.commit()
    notif.push(pushes)
    notif.broadcast([reg.user_id], "registration.approved", {"event_id": ev.id, "registration_id": reg.id})
    notif.send_email(reg.user_id, f"Registration confirmed: {ev.name}")
    return reg
