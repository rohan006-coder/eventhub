from tests.helpers import err


def test_notification_creation_and_mark_read(w):
    ev = w.event(publish=True)
    w.p1.post(f"/api/events/{ev['id']}/register")
    page = w.p1.get("/api/notifications").json()
    assert page["total"] >= 2
    types = {n["type"] for n in page["items"]}
    assert {"event_published", "registration_confirmed"} <= types
    assert w.p1.get("/api/notifications/unread-count").json()["count"] == page["total"]
    nid = page["items"][0]["id"]
    r = w.p1.patch(f"/api/notifications/{nid}/read")
    assert r.status_code == 200 and r.json()["is_read"] is True
    assert w.p1.get("/api/notifications?unread_only=true").json()["total"] == page["total"] - 1
    assert w.p2.patch(f"/api/notifications/{nid}/read").status_code == 403   # someone else's
    assert w.p1.patch("/api/notifications/read-all").json()["updated"] == page["total"] - 1
    assert w.p1.get("/api/notifications/unread-count").json()["count"] == 0


def test_staff_gets_new_registration_notification(w):
    ev = w.event(publish=True)
    w.p1.post(f"/api/events/{ev['id']}/register")
    assert "new_registration" in [n["type"] for n in w.staff.get("/api/notifications").json()["items"]]


def test_mention_notification(w):
    ev = w.event(publish=True)
    r = w.manager.post("/api/comments", {"event_id": ev["id"], "body": "Hi @pat and @olga and @nobody!"})
    assert r.status_code == 201
    mentions = [n for n in w.p1.get("/api/notifications").json()["items"] if n["type"] == "user_mentioned"]
    assert len(mentions) == 1
    # a user from another org is never notified (no cross-tenant probing)
    assert [n for n in w.outsider.get("/api/notifications").json()["items"] if n["type"] == "user_mentioned"] == []
    # you don't notify yourself
    w.manager.post("/api/comments", {"event_id": ev["id"], "body": "note to @mallory"})
    assert [n for n in w.manager.get("/api/notifications").json()["items"] if n["type"] == "user_mentioned"] == []


def test_event_reminder_job(w):
    from datetime import datetime, timedelta, timezone
    from app.core.database import SessionLocal
    from app.models.models import Event
    from app.services.jobs import send_event_reminders
    from tests.helpers import iso
    soon = datetime.now(timezone.utc) + timedelta(hours=5)
    ev = w.event(publish=True, start_time=iso(soon), end_time=iso(soon + timedelta(hours=2)))
    w.p1.post(f"/api/events/{ev['id']}/register")
    db = SessionLocal()
    try:
        assert send_event_reminders(db) == 1
        assert send_event_reminders(db) == 0   # only once
    finally:
        db.close()
    assert "event_starting_soon" in [n["type"] for n in w.p1.get("/api/notifications").json()["items"]]
