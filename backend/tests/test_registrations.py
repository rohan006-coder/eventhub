from concurrent.futures import ThreadPoolExecutor

from app.core.database import SessionLocal
from app.core.errors import AppError
from app.models.models import Event, User
from app.services import registrations as reg_svc
from tests.helpers import Actor, err, future, iso


def reg(actor, ev):
    return actor.post(f"/api/events/{ev['id']}/register")


def test_register_and_duplicate(w):
    ev = w.event(publish=True)
    r = reg(w.p1, ev)
    assert r.status_code == 201 and r.json()["status"] == "confirmed"
    r = reg(w.p1, ev)
    assert r.status_code == 409 and err(r) == "DUPLICATE_REGISTRATION"


def test_capacity_waitlist_and_automatic_promotion(w):
    ev = w.event(publish=True, capacity=2)
    a, b, c = reg(w.p1, ev).json(), reg(w.p2, ev).json(), reg(w.p3, ev).json()
    assert [a["status"], b["status"], c["status"]] == ["confirmed", "confirmed", "waitlisted"]
    assert c["waitlist_position"] == 1
    # A cancels -> C promoted automatically
    r = w.p1.post(f"/api/registrations/{a['id']}/cancel")
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert w.p3.get(f"/api/registrations/{c['id']}").json()["status"] == "confirmed"
    types = [n["type"] for n in w.p3.get("/api/notifications").json()["items"]]
    assert "registration_waitlisted" in types and "registration_confirmed" in types
    # cancelled registration releases capacity & can re-register (goes to waitlist now, event is full)
    assert reg(w.p1, ev).json()["status"] == "waitlisted"


def test_waitlist_is_fifo(w):
    ev = w.event(publish=True, capacity=1)
    reg(w.p1, ev)
    b, c = reg(w.p2, ev).json(), reg(w.p3, ev).json()
    first = w.p1.get("/api/registrations", params={"event_id": ev["id"]}).json()["items"][0]
    w.p1.post(f"/api/registrations/{first['id']}/cancel")
    assert w.p2.get(f"/api/registrations/{b['id']}").json()["status"] == "confirmed"
    assert w.p3.get(f"/api/registrations/{c['id']}").json()["status"] == "waitlisted"


def test_cancel_twice_rejected(w):
    ev = w.event(publish=True)
    r = reg(w.p1, ev).json()
    assert w.p1.post(f"/api/registrations/{r['id']}/cancel").status_code == 200
    r2 = w.p1.post(f"/api/registrations/{r['id']}/cancel")
    assert r2.status_code == 409 and err(r2) == "INVALID_REGISTRATION_STATUS"


def test_cannot_register_for_cancelled_draft_or_closed(w):
    draft = w.event()
    assert reg(w.p1, draft).status_code == 404
    ev = w.event(publish=True)
    w.manager.post(f"/api/events/{ev['id']}/cancel")
    r = reg(w.p1, ev)
    assert r.status_code == 409 and err(r) == "EVENT_CANCELLED"
    # deadline in the past
    ev2 = w.event(publish=True, registration_deadline=iso(future(10, -1)))
    from datetime import datetime, timedelta, timezone
    db = SessionLocal()
    e = db.get(Event, ev2["id"])
    e.registration_deadline = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()
    db.close()
    r = reg(w.p1, ev2)
    assert r.status_code == 409 and err(r) == "REGISTRATION_CLOSED"


def test_non_member_cannot_register(w):
    ev = w.event(publish=True)
    assert reg(w.outsider, ev).status_code == 403


def test_approval_flow(w):
    ev = w.event(publish=True, requires_approval=True)
    r = reg(w.p1, ev).json()
    assert r["status"] == "pending"
    assert w.p1.post(f"/api/registrations/{r['id']}/approve").status_code == 403  # participants can't approve
    assert w.p2.post(f"/api/registrations/{r['id']}/approve").status_code == 403
    assert w.staff.post(f"/api/registrations/{r['id']}/approve").json()["status"] == "confirmed"
    assert err(w.staff.post(f"/api/registrations/{r['id']}/approve")) == "INVALID_REGISTRATION_STATUS"
    r2 = reg(w.p2, ev).json()
    assert w.staff.post(f"/api/registrations/{r2['id']}/reject").json()["status"] == "rejected"
    assert "registration_rejected" in [n["type"] for n in w.p2.get("/api/notifications").json()["items"]]


def test_reject_releases_capacity_to_waitlist(w):
    ev = w.event(publish=True, capacity=1, requires_approval=True)
    a = reg(w.p1, ev).json()
    b = reg(w.p2, ev).json()
    assert (a["status"], b["status"]) == ("pending", "waitlisted")
    w.staff.post(f"/api/registrations/{a['id']}/reject")
    assert w.p2.get(f"/api/registrations/{b['id']}").json()["status"] == "pending"


def test_registration_visibility(w):
    ev = w.event(publish=True)
    r = reg(w.p1, ev).json()
    assert w.p2.get(f"/api/registrations/{r['id']}").status_code == 403
    assert w.p2.post(f"/api/registrations/{r['id']}/cancel").status_code == 403
    assert w.outsider.get(f"/api/registrations/{r['id']}").status_code == 403
    assert w.p1.get(f"/api/events/{ev['id']}/registrations").status_code == 403
    assert w.staff.get(f"/api/events/{ev['id']}/registrations").json()["total"] == 1
    assert w.p2.get("/api/registrations").json()["total"] == 0
    assert w.p1.get("/api/registrations?status=waitlisted").json()["total"] == 0
    assert w.staff.get(f"/api/registrations?organization_id={w.org}&status=confirmed").json()["total"] == 1


def test_raising_capacity_promotes_waitlist(w):
    ev = w.event(publish=True, capacity=1)
    reg(w.p1, ev)
    c = reg(w.p2, ev).json()
    w.manager.patch(f"/api/events/{ev['id']}", {"capacity": 2})
    assert w.p2.get(f"/api/registrations/{c['id']}").json()["status"] == "confirmed"


def test_concurrent_registrations_never_exceed_capacity(w):
    ev = w.event(publish=True, capacity=3)
    users = [Actor(w.client, f"racer{i}") for i in range(8)]
    for u in users:
        w.admin.post(f"/api/organizations/{w.org}/members", {"email": f"{u.name}@test.io", "role": "participant"})

    def go(uid):
        db = SessionLocal()
        try:
            return reg_svc.register(db, db.get(User, uid), ev["id"]).status.value
        except AppError as e:
            return e.code
        finally:
            db.close()

    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(go, [u.id for u in users]))
    assert results.count("confirmed") == 3, results
    assert results.count("waitlisted") == 5, results
    regs = w.manager.get(f"/api/events/{ev['id']}/registrations?page_size=100").json()["items"]
    assert sum(r["status"] == "confirmed" for r in regs) == 3
