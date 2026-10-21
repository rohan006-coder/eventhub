from concurrent.futures import ThreadPoolExecutor

from app.core.database import SessionLocal
from app.core.errors import AppError
from app.models.models import User
from app.services import resources as svc
from app.schemas import BookingIn
from tests.helpers import Actor, err, future, iso


def book(actor, rid, start_h, end_h, **kw):
    return actor.post("/api/bookings", {"resource_id": rid, "start_time": iso(future(5, start_h)), "end_time": iso(future(5, end_h)), "purpose": "x", **kw})


def test_booking_lifecycle(w):
    room = w.resource()
    r = book(w.manager, room["id"], 10, 11)
    assert r.status_code == 201 and r.json()["status"] == "requested"
    bid = r.json()["id"]
    assert w.manager.post(f"/api/bookings/{bid}/approve").status_code == 403  # only admins decide
    assert w.admin.post(f"/api/bookings/{bid}/approve").json()["status"] == "approved"
    assert err(w.admin.post(f"/api/bookings/{bid}/approve")) == "INVALID_BOOKING_STATUS"
    assert "booking_approved" in [n["type"] for n in w.manager.get("/api/notifications").json()["items"]]
    assert w.manager.post(f"/api/bookings/{bid}/cancel").json()["status"] == "cancelled"
    assert err(w.manager.post(f"/api/bookings/{bid}/cancel")) == "INVALID_BOOKING_STATUS"


def test_rejection_notifies_and_frees_slot(w):
    room = w.resource()
    bid = book(w.manager, room["id"], 10, 11).json()["id"]
    assert w.admin.post(f"/api/bookings/{bid}/reject").json()["status"] == "rejected"
    assert "booking_rejected" in [n["type"] for n in w.manager.get("/api/notifications").json()["items"]]
    assert book(w.manager, room["id"], 10, 11).status_code == 201


def test_overlapping_booking_is_rejected(w):
    room = w.resource()
    assert book(w.manager, room["id"], 10, 11).status_code == 201
    r = book(w.admin, room["id"], 10.5, 11.5)
    assert r.status_code == 409 and err(r) == "RESOURCE_ALREADY_BOOKED"
    assert err(book(w.admin, room["id"], 9, 12)) == "RESOURCE_ALREADY_BOOKED"   # fully contains
    assert err(book(w.admin, room["id"], 10.25, 10.75)) == "RESOURCE_ALREADY_BOOKED"  # fully inside
    assert book(w.admin, room["id"], 11, 12).status_code == 201  # back-to-back is fine
    other = w.resource(name="Room B")
    assert book(w.admin, other["id"], 10, 11).status_code == 201  # different resource


def test_cancelled_booking_frees_slot(w):
    room = w.resource()
    bid = book(w.manager, room["id"], 10, 11).json()["id"]
    w.manager.post(f"/api/bookings/{bid}/cancel")
    assert book(w.admin, room["id"], 10, 11).status_code == 201


def test_invalid_booking_time_and_inactive_resource(w):
    room = w.resource()
    r = book(w.manager, room["id"], 11, 10)
    assert r.status_code == 422 and err(r) == "INVALID_BOOKING_TIME"
    w.admin.post(f"/api/resources/{room['id']}/deactivate")
    r = book(w.manager, room["id"], 10, 11)
    assert r.status_code == 409 and err(r) == "RESOURCE_INACTIVE"


def test_booking_authorization(w):
    room = w.resource()
    assert book(w.p1, room["id"], 10, 11).status_code == 403          # participants cannot book
    assert book(w.outsider, room["id"], 10, 11).status_code == 403    # other tenant
    bid = book(w.manager, room["id"], 10, 11).json()["id"]
    assert w.outsider.get(f"/api/bookings/{bid}").status_code == 403
    assert w.p1.get(f"/api/bookings/{bid}").status_code == 403
    assert w.staff.get(f"/api/bookings/{bid}").status_code == 200
    assert w.staff.post(f"/api/bookings/{bid}/cancel").status_code == 403
    assert w.outsider.post(f"/api/bookings/{bid}/cancel").status_code == 403
    assert w.outsider.get("/api/bookings").json()["total"] == 0


def test_booking_event_must_belong_to_same_org(w):
    room = w.resource()
    foreign = w.event(w.outsider, org=w.org_b)
    assert book(w.admin, room["id"], 10, 11, event_id=foreign["id"]).status_code == 404


def test_patch_booking_rechecks_conflicts(w):
    room = w.resource()
    a = book(w.manager, room["id"], 10, 11).json()
    book(w.admin, room["id"], 12, 13)
    r = w.manager.patch(f"/api/bookings/{a['id']}", {"start_time": iso(future(5, 12)), "end_time": iso(future(5, 14))})
    assert r.status_code == 409 and err(r) == "RESOURCE_ALREADY_BOOKED"
    r = w.manager.patch(f"/api/bookings/{a['id']}", {"purpose": "new purpose"})
    assert r.status_code == 200 and r.json()["purpose"] == "new purpose"
    # a non-admin rescheduling an approved booking needs re-approval
    w.admin.post(f"/api/bookings/{a['id']}/approve")
    r = w.manager.patch(f"/api/bookings/{a['id']}", {"start_time": iso(future(5, 14)), "end_time": iso(future(5, 15))})
    assert r.json()["status"] == "requested"


def test_booking_filters(w):
    r1, r2 = w.resource(), w.resource(name="Room B")
    book(w.manager, r1["id"], 10, 11)
    book(w.admin, r2["id"], 10, 11)
    assert w.admin.get(f"/api/bookings?resource_id={r1['id']}").json()["total"] == 1
    assert w.admin.get("/api/bookings?status=approved").json()["total"] == 1   # admin's booking is auto-approved
    assert w.admin.get(f"/api/bookings?requested_by={w.manager.id}").json()["total"] == 1
    assert w.admin.get("/api/bookings", params={"date_from": iso(future(30))}).json()["total"] == 0


def test_concurrent_booking_requests_create_only_one_reservation(w):
    room = w.resource()
    managers = [Actor(w.client, f"mgr{i}") for i in range(8)]
    for m in managers:
        w.admin.post(f"/api/organizations/{w.org}/members", {"email": f"{m.name}@test.io", "role": "event_manager"})
    data = BookingIn(resource_id=room["id"], start_time=future(7, 10), end_time=future(7, 11), purpose="race")

    def go(uid):
        db = SessionLocal()
        try:
            return svc.create(db, db.get(User, uid), data).status.value
        except AppError as e:
            return e.code
        finally:
            db.close()

    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(go, [m.id for m in managers]))
    assert results.count("requested") == 1, results
    assert results.count("RESOURCE_ALREADY_BOOKED") == 7, results
    assert w.admin.get(f"/api/bookings?resource_id={room['id']}").json()["total"] == 1
