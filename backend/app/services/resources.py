from sqlalchemy.exc import IntegrityError

from app.core.database import locked, utcnow
from app.core.errors import AppError, conflict, forbidden, not_found
from app.models.models import BookingStatus as B, NotificationType as N, Resource, ResourceBooking, ResourceStatus
from app.repositories import BookingRepo, EventRepo, MemberRepo, ResourceRepo
from app.services import notifications as notif
from app.services.audit import audit
from app.services.permissions import RANK, org_ids_with_role, require_role


# ------------------------------------------------------------------ resources
def create_resource(db, user, data):
    require_role(db, user, data.organization_id, "org_admin")
    res = ResourceRepo(db).add(Resource(**data.model_dump()))
    audit(db, user, "resource.create", "resource", res.id, res.organization_id)
    db.commit()
    return res


def create(db, user, data):
    """Compatibility wrapper: route handlers call the explicit resource/booking functions."""
    if hasattr(data, "resource_id"):
        return create_booking(db, user, data)
    return create_resource(db, user, data)


def get_resource(db, user, rid):
    res = ResourceRepo(db).get(rid)
    if not res:
        raise not_found("Resource")
    require_role(db, user, res.organization_id)
    return res


def search_resources(db, user, *, organization_id=None, page=1, size=20, **filters):
    if organization_id:
        require_role(db, user, organization_id)
        org_ids = [organization_id]
    else:
        org_ids = org_ids_with_role(db, user)
    return ResourceRepo(db).search(org_ids, page=page, size=size, **filters)


def update_resource(db, user, rid, data):
    res = get_resource(db, user, rid)
    require_role(db, user, res.organization_id, "org_admin")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(res, k, v)
    audit(db, user, "resource.update", "resource", res.id, res.organization_id)
    db.commit()
    return res


def set_status(db, user, rid, active: bool):
    res = get_resource(db, user, rid)
    require_role(db, user, res.organization_id, "org_admin")
    res.status = ResourceStatus.active if active else ResourceStatus.inactive
    audit(db, user, "resource.activate" if active else "resource.deactivate", "resource", res.id, res.organization_id)
    db.commit()
    return res


# ------------------------------------------------------------------ bookings
def _times(start, end):
    if end <= start:
        raise AppError(422, "INVALID_BOOKING_TIME", "Booking end time must be after its start time.")


def _already_booked():
    return conflict("RESOURCE_ALREADY_BOOKED", "The selected resource is already booked for this time period.")


def create_booking(db, user, data):
    res = ResourceRepo(db).get(data.resource_id)
    if not res:
        raise not_found("Resource")
    role = require_role(db, user, res.organization_id, "event_manager")
    _times(data.start_time, data.end_time)
    if data.event_id:
        ev = EventRepo(db).get(data.event_id)
        if not ev or ev.organization_id != res.organization_id:
            raise not_found("Event")
    with locked(db, f"resource:{res.id}"):
        db.refresh(res)
        if res.status != ResourceStatus.active:
            raise conflict("RESOURCE_INACTIVE", "This resource is not available for booking.")
        if BookingRepo(db).conflicts(res.id, data.start_time, data.end_time):
            raise _already_booked()
        status = B.approved if role == "org_admin" else B.requested
        try:
            booking = BookingRepo(db).add(ResourceBooking(requested_by=user.id, status=status, **data.model_dump()))
            audit(db, user, "booking.create", "booking", booking.id, res.organization_id, {"status": status.value})
            db.commit()  # PostgreSQL also has an exclusion constraint as a last line of defence
        except IntegrityError:
            db.rollback()
            raise _already_booked()
    admins = [i for i in MemberRepo(db).user_ids(res.organization_id, ["org_admin"]) if i != user.id]
    notif.broadcast(admins, "booking.requested", {"booking_id": booking.id})
    return booking


def _load(db, user, bid):
    b = BookingRepo(db).get(bid)
    if not b:
        raise not_found("Booking")
    org = b.resource.organization_id
    role = require_role(db, user, org)
    if RANK[role] < RANK["staff"] and b.requested_by != user.id:
        raise forbidden("FORBIDDEN", "You can only access your own bookings.")
    return b, org, role


def get_booking(db, user, bid):
    return _load(db, user, bid)[0]


def search_bookings(db, user, *, organization_id=None, page=1, size=20, **filters):
    if organization_id:
        require_role(db, user, organization_id, "staff")
        org_ids = [organization_id]
    else:
        org_ids = org_ids_with_role(db, user, "staff")
    return BookingRepo(db).search(org_ids, page=page, size=size, **filters)


def update_booking(db, user, bid, data):
    b, org, role = _load(db, user, bid)
    if b.requested_by != user.id and role != "org_admin":
        raise forbidden("FORBIDDEN", "Only the requester or an organization admin can change this booking.")
    if b.status not in (B.requested, B.approved):
        raise conflict("INVALID_BOOKING_STATUS", f"A {b.status.value} booking cannot be changed.")
    patch = data.model_dump(exclude_unset=True)
    start, end = patch.get("start_time", b.start_time), patch.get("end_time", b.end_time)
    _times(start, end)
    with locked(db, f"resource:{b.resource_id}"):
        db.refresh(b)
        if BookingRepo(db).conflicts(b.resource_id, start, end, exclude_id=b.id):
            raise _already_booked()
        time_changed = (start, end) != (b.start_time, b.end_time)
        for k, v in patch.items():
            setattr(b, k, v)
        if time_changed and role != "org_admin" and b.status == B.approved:
            b.status = B.requested  # re-approval needed after a non-admin reschedule
        audit(db, user, "booking.update", "booking", b.id, org)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise _already_booked()
    return b


def cancel(db, user, bid):
    b, org, role = _load(db, user, bid)
    if b.requested_by != user.id and role != "org_admin":
        raise forbidden("FORBIDDEN", "Only the requester or an organization admin can cancel this booking.")
    if b.status not in (B.requested, B.approved):
        raise conflict("INVALID_BOOKING_STATUS", f"A {b.status.value} booking cannot be cancelled.")
    b.status = B.cancelled
    audit(db, user, "booking.cancel", "booking", b.id, org)
    db.commit()
    return b


def decide(db, user, bid, approve: bool):
    b, org, _ = _load(db, user, bid)
    require_role(db, user, org, "org_admin")
    with locked(db, f"resource:{b.resource_id}"):
        db.refresh(b)
        if b.status != B.requested:
            raise conflict("INVALID_BOOKING_STATUS", "Only requested bookings can be approved or rejected.")
        b.status, b.decided_by = (B.approved if approve else B.rejected), user.id
        label = "approved" if approve else "rejected"
        pushes = notif.notify(db, [b.requested_by], N.booking_approved if approve else N.booking_rejected,
                              f"Booking {label}: {b.resource.name}", f"{b.start_time:%Y-%m-%d %H:%M} UTC", org_id=org, data={"booking_id": b.id})
        audit(db, user, f"booking.{label}", "booking", b.id, org)
        db.commit()
    notif.push(pushes)
    notif.broadcast([b.requested_by], f"booking.{label}", {"booking_id": b.id})
    return b
