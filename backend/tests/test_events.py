from tests.helpers import err, future, iso


def test_event_crud(w):
    ev = w.event()
    assert ev["status"] == "draft" and ev["organizer_name"] == "Mallory"
    r = w.manager.patch(f"/api/events/{ev['id']}", {"name": "Renamed", "capacity": 50})
    assert r.status_code == 200 and r.json()["name"] == "Renamed" and r.json()["capacity"] == 50
    assert w.manager.get(f"/api/events/{ev['id']}").json()["name"] == "Renamed"
    assert w.manager.delete(f"/api/events/{ev['id']}").status_code == 204
    assert w.manager.get(f"/api/events/{ev['id']}").status_code == 404


def test_event_validation(w):
    base = {"organization_id": w.org, "name": "E", "start_time": iso(future(5)), "end_time": iso(future(4))}
    r = w.manager.post("/api/events", base)
    assert r.status_code == 422 and err(r) == "INVALID_EVENT_TIME"
    r = w.manager.post("/api/events", {**base, "end_time": iso(future(6)), "capacity": 0})
    assert r.status_code == 422 and err(r) == "VALIDATION_ERROR"
    r = w.manager.post("/api/events", {**base, "end_time": iso(future(6)), "registration_deadline": iso(future(7))})
    assert err(r) == "INVALID_REGISTRATION_DEADLINE"


def test_status_transitions(w):
    ev = w.event()
    i = ev["id"]
    assert err(w.manager.post(f"/api/events/{i}/transition", {"status": "completed"})) == "INVALID_EVENT_STATUS"
    assert w.manager.post(f"/api/events/{i}/publish").status_code == 200
    assert err(w.manager.post(f"/api/events/{i}/publish")) == "INVALID_EVENT_STATUS"  # published -> published
    assert err(w.manager.post(f"/api/events/{i}/archive")) == "INVALID_EVENT_STATUS"  # published -> archived
    assert w.manager.post(f"/api/events/{i}/cancel").json()["status"] == "cancelled"
    assert err(w.manager.post(f"/api/events/{i}/publish")) == "INVALID_EVENT_STATUS"  # cancelled is final-ish
    assert w.manager.post(f"/api/events/{i}/archive").json()["status"] == "archived"
    assert err(w.manager.patch(f"/api/events/{i}", {"name": "x"})) == "INVALID_EVENT_STATUS"


def test_delete_only_draft_or_cancelled(w):
    ev = w.event(publish=True)
    r = w.manager.delete(f"/api/events/{ev['id']}")
    assert r.status_code == 409 and err(r) == "INVALID_EVENT_STATUS"
    w.manager.post(f"/api/events/{ev['id']}/cancel")
    assert w.manager.delete(f"/api/events/{ev['id']}").status_code == 204


def test_capacity_cannot_drop_below_registrations(w):
    ev = w.event(publish=True, capacity=2)
    w.p1.post(f"/api/events/{ev['id']}/register")
    w.p2.post(f"/api/events/{ev['id']}/register")
    r = w.manager.patch(f"/api/events/{ev['id']}", {"capacity": 1})
    assert r.status_code == 409 and err(r) == "EVENT_CAPACITY_EXCEEDED"


def test_cancellation_notifies_registrants(w):
    ev = w.event(publish=True)
    w.p1.post(f"/api/events/{ev['id']}/register")
    w.manager.post(f"/api/events/{ev['id']}/cancel")
    types = [n["type"] for n in w.p1.get("/api/notifications").json()["items"]]
    assert "event_cancelled" in types and "event_published" in types


def test_list_filters_search_sort_pagination(w):
    w.event(name="Alpha Conference", location="Berlin", publish=True)
    w.event(name="Beta Workshop", location="Paris", publish=True)
    w.event(name="Gamma Summit", location="Berlin")
    a = w.admin
    assert a.get("/api/events").json()["total"] == 3
    assert a.get("/api/events?status=published").json()["total"] == 2
    assert a.get("/api/events?search=conference").json()["total"] == 1
    assert a.get("/api/events?location=berlin").json()["total"] == 2
    r = a.get("/api/events?page=1&page_size=2&sort=-name").json()
    assert len(r["items"]) == 2 and r["pages"] == 2 and r["items"][0]["name"] == "Gamma Summit"
    assert a.get("/api/events", params={"date_from": iso(future(30))}).json()["total"] == 0
    assert a.get(f"/api/events?organizer_id={w.manager.id}").json()["total"] == 3
    assert a.get("/api/events?page_size=1000").status_code == 422
