from tests.helpers import err, future, iso


def test_comments_crud_and_ownership(w):
    ev = w.event(publish=True)
    c = w.p1.post("/api/comments", {"event_id": ev["id"], "body": "Looking forward!"}).json()
    assert w.p1.get(f"/api/comments?event_id={ev['id']}").json()["total"] == 1
    assert w.p2.patch(f"/api/comments/{c['id']}", {"body": "hax"}).status_code == 403
    assert w.admin.delete(f"/api/comments/{c['id']}").status_code == 403
    assert w.p1.patch(f"/api/comments/{c['id']}", {"body": "Edited"}).json()["body"] == "Edited"
    assert w.outsider.post("/api/comments", {"event_id": ev["id"], "body": "x"}).status_code == 403
    assert w.p1.delete(f"/api/comments/{c['id']}").status_code == 204
    assert w.p1.post("/api/comments", {"event_id": ev["id"], "body": ""}).status_code == 422


def test_session_comments(w):
    ev = w.event(publish=True)
    s = w.manager.post(f"/api/events/{ev['id']}/sessions", {"title": "T", "start_time": iso(future(10, 1)), "end_time": iso(future(10, 2))}).json()
    assert w.p1.post("/api/comments", {"event_id": ev["id"], "session_id": s["id"], "body": "q"}).status_code == 201
    assert w.p1.get(f"/api/comments?event_id={ev['id']}&session_id={s['id']}").json()["total"] == 1
    assert w.p1.get(f"/api/comments?event_id={ev['id']}").json()["total"] == 0


def test_attendance(w):
    ev = w.event(publish=True, capacity=5)
    reg = w.p1.post(f"/api/events/{ev['id']}/register").json()
    body = {"registration_id": reg["id"], "status": "attended"}
    assert w.p1.post(f"/api/events/{ev['id']}/attendance", body).status_code == 403   # can't self check-in
    r = w.staff.post(f"/api/events/{ev['id']}/attendance", body)
    assert r.status_code == 201 and r.json()["status"] == "attended" and r.json()["checked_in_at"]
    assert w.p1.get(f"/api/registrations/{reg['id']}").json()["status"] == "attended"
    att_id = r.json()["id"]
    assert w.p1.patch(f"/api/attendance/{att_id}", {"status": "no_show"}).status_code == 403
    assert w.outsider.patch(f"/api/attendance/{att_id}", {"status": "no_show"}).status_code == 403
    assert w.staff.patch(f"/api/attendance/{att_id}", {"status": "no_show"}).json()["status"] == "no_show"
    assert w.p1.get(f"/api/events/{ev['id']}/attendance").json()["total"] == 1
    assert w.p2.get(f"/api/events/{ev['id']}/attendance").json()["total"] == 0   # participants only see their own
    assert w.staff.get(f"/api/events/{ev['id']}/attendance-report").text.count("\n") >= 2


def test_attendance_requires_confirmed_registration_and_live_event(w):
    ev = w.event(publish=True, capacity=1, requires_approval=True)
    reg = w.p1.post(f"/api/events/{ev['id']}/register").json()   # pending
    r = w.staff.post(f"/api/events/{ev['id']}/attendance", {"registration_id": reg["id"]})
    assert r.status_code == 409 and err(r) == "INVALID_REGISTRATION_STATUS"
    draft = w.event()
    assert w.staff.post(f"/api/events/{draft['id']}/attendance", {"registration_id": 1}).status_code == 409


def test_dashboards_per_role(w):
    ev = w.event(publish=True)
    w.p1.post(f"/api/events/{ev['id']}/register")
    w.p2.post(f"/api/events/{ev['id']}/register")
    w.p3.post(f"/api/events/{ev['id']}/register")   # waitlisted (capacity 2)
    w.resource()
    a = w.admin.get("/api/dashboard").json()
    assert a["role"] == "org_admin" and a["total_events"] == 1 and a["published_events"] == 1 and a["total_registrations"] == 3 and a["active_resources"] == 1
    m = w.manager.get(f"/api/dashboard?organization_id={w.org}").json()
    assert m["role"] == "event_manager" and m["my_events"] == 1 and m["waitlisted_participants"] == 1
    s = w.staff.get(f"/api/dashboard?organization_id={w.org}").json()
    assert s["role"] == "staff" and len(s["assigned_events"]) == 1
    p = w.p1.get(f"/api/dashboard?organization_id={w.org}").json()
    assert p["role"] == "participant" and len(p["registered_events"]) == 1
    assert [e["name"] for e in w.p3.get(f"/api/dashboard?organization_id={w.org}").json()["waitlisted_events"]] == ["Conference"]
    assert w.outsider.get(f"/api/dashboard?organization_id={w.org}").status_code == 403


def test_calendar(w):
    ev = w.event(publish=True)
    room = w.resource()
    w.manager.post("/api/bookings", {"resource_id": room["id"], "start_time": iso(future(10, 1)), "end_time": iso(future(10, 2)), "purpose": "AV"})
    w.manager.post(f"/api/events/{ev['id']}/sessions", {"title": "Keynote", "start_time": iso(future(10, 1)), "end_time": iso(future(10, 2))})
    params = {"organization_id": w.org, "start": iso(future(9)), "end": iso(future(11))}
    c = w.manager.get("/api/calendar", params=params).json()
    assert len(c["events"]) == 1 and len(c["sessions"]) == 1 and len(c["bookings"]) == 1
    assert w.p1.get("/api/calendar", params=params).json()["bookings"] == []   # bookings hidden from participants
    assert w.outsider.get("/api/calendar", params=params).status_code == 403


def test_error_envelope_and_unknown_ids(w):
    r = w.admin.get("/api/events/99999")
    assert r.status_code == 404 and r.json() == {"success": False, "error": {"code": "NOT_FOUND", "message": "Event not found."}}
    r = w.admin.post("/api/events", {"organization_id": w.org})
    assert r.status_code == 422 and r.json()["success"] is False and r.json()["error"]["details"]
    assert w.admin.get("/api/nope").status_code == 404


def test_audit_log_admin_only(w):
    w.event()
    logs = w.admin.get(f"/api/organizations/{w.org}/audit-logs").json()
    assert logs["total"] > 0 and any(l["action"] == "event.create" for l in logs["items"])
    assert w.manager.get(f"/api/organizations/{w.org}/audit-logs").status_code == 403
