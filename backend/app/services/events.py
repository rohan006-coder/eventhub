from app.core.database import utcnow
from app.core.errors import AppError, bad_request, conflict, not_found
from app.models.models import Event, EventStatus as S, NotificationType as N, RegistrationStatus as R
from app.repositories import ACTIVE_REG, EventRepo, MemberRepo, RegistrationRepo, SessionRepo
from app.services import notifications as notif
from app.services.audit import audit
from app.services.permissions import RANK, get_event_managed, get_event_visible, require_role
from app.core.database import locked

TRANSITIONS = {
    S.draft: {S.published, S.cancelled, S.archived},
    S.published: {S.ongoing, S.completed, S.cancelled},
    S.ongoing: {S.completed, S.cancelled},
    S.completed: {S.archived},
    S.cancelled: {S.archived},
    S.archived: set(),
}


def _check_times(start, end, deadline):
    if end <= start:
        raise AppError(422, "INVALID_EVENT_TIME", "Event end time must be after its start time.")
    if deadline and deadline > start:
        raise AppError(422, "INVALID_REGISTRATION_DEADLINE", "Registration deadline cannot be after the event starts.")


def decorate(db, ev):
    r = RegistrationRepo(db)
    ev.confirmed_count = r.seat_count(ev.id)
    ev.waitlist_count = r.count_status(ev.id, R.waitlisted)
    return ev


def create(db, user, data):
    require_role(db, user, data.organization_id, "event_manager")
    _check_times(data.start_time, data.end_time, data.registration_deadline)
    ev = EventRepo(db).add(Event(organizer_id=user.id, **data.model_dump()))
    audit(db, user, "event.create", "event", ev.id, ev.organization_id)
    db.commit()
    db.refresh(ev)
    return decorate(db, ev)


def get(db, user, event_id):
    ev, _ = get_event_visible(db, user, event_id)
    return decorate(db, ev)


def search(db, user, *, organization_id=None, page=1, size=20, **filters):
    if organization_id:
        role = require_role(db, user, organization_id)
        org_ids, hide = [organization_id], ([organization_id] if role == "participant" else [])
    elif user.is_super_admin:
        from app.repositories import OrgRepo
        org_ids, hide = [o.id for o in OrgRepo(db).all()], []
    else:
        from app.repositories import OrgRepo
        rows = OrgRepo(db).for_user(user.id)
        org_ids = [o.id for o, _ in rows]
        hide = [o.id for o, r in rows if r == "participant"]
    items, total = EventRepo(db).search(org_ids, hide_draft_orgs=hide, page=page, size=size, **filters)
    return [decorate(db, e) for e in items], total


def update(db, user, event_id, data):
    ev, _ = get_event_managed(db, user, event_id)
    if ev.status not in (S.draft, S.published):
        raise conflict("INVALID_EVENT_STATUS", f"A {ev.status.value} event cannot be edited.")
    patch = data.model_dump(exclude_unset=True)
    start, end = patch.get("start_time", ev.start_time), patch.get("end_time", ev.end_time)
    deadline = patch.get("registration_deadline", ev.registration_deadline)
    _check_times(start, end, deadline)
    for s in SessionRepo(db).for_event(ev.id):
        if s.start_time < start or s.end_time > end:
            raise AppError(422, "SESSION_OUT_OF_EVENT_RANGE", "Existing sessions would fall outside the new event time.")
    with locked(db, f"event:{ev.id}"):
        if "capacity" in patch and patch["capacity"] < RegistrationRepo(db).seat_count(ev.id):
            raise conflict("EVENT_CAPACITY_EXCEEDED", "New capacity is lower than the number of current registrations.")
        for k, v in patch.items():
            setattr(ev, k, v)
        from app.services.registrations import promote_waitlist
        promoted = promote_waitlist(db, ev) if ("capacity" in patch or "requires_approval" in patch) else []
        audit(db, user, "event.update", "event", ev.id, ev.organization_id, {k: str(v) for k, v in patch.items()})
        db.commit()
    for r in promoted:
        notif.push(r._notes)
    notif.broadcast([ev.organizer_id] if ev.organizer_id else [], "event.updated", {"event_id": ev.id})
    return decorate(db, ev)


def transition(db, user, event_id, new_status: S):
    ev, _ = get_event_managed(db, user, event_id)
    if new_status not in TRANSITIONS[ev.status]:
        raise conflict("INVALID_EVENT_STATUS", f"Cannot change event status from {ev.status.value} to {new_status.value}.")
    if new_status == S.published and ev.end_time <= utcnow():
        raise conflict("INVALID_EVENT_STATUS", "An event that has already ended cannot be published.")
    pushes = []
    with locked(db, f"event:{ev.id}"):
        ev.status = new_status
        if new_status == S.published:
            ids = [i for i in MemberRepo(db).user_ids(ev.organization_id) if i != user.id]
            pushes = notif.notify(db, ids, N.event_published, f"New event: {ev.name}", ev.description[:200], org_id=ev.organization_id, data={"event_id": ev.id})
        elif new_status == S.cancelled:
            regs, _t = RegistrationRepo(db).search(event_id=ev.id, size=100000)
            ids = [r.user_id for r in regs if r.status in ACTIVE_REG]
            pushes = notif.notify(db, ids, N.event_cancelled, f"Event cancelled: {ev.name}", "This event has been cancelled.", org_id=ev.organization_id, data={"event_id": ev.id})
        audit(db, user, f"event.{new_status.value}", "event", ev.id, ev.organization_id)
        db.commit()
    notif.push(pushes)
    if new_status == S.cancelled:
        notif.broadcast([n.user_id for n in pushes], "event.cancelled", {"event_id": ev.id})
    return decorate(db, ev)


def delete(db, user, event_id):
    ev, role = get_event_managed(db, user, event_id)
    if ev.status not in (S.draft, S.cancelled):
        raise conflict("INVALID_EVENT_STATUS", "Only draft or cancelled events can be deleted. Archive the event instead.")
    audit(db, user, "event.delete", "event", ev.id, ev.organization_id, {"name": ev.name})
    EventRepo(db).delete(ev)
    db.commit()
