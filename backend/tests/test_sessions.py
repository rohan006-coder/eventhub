from tests.helpers import err, future, iso


def sess(actor, ev, h1, h2, **kw):
    body = {"title": "Talk", "start_time": iso(future(10, h1)), "end_time": iso(future(10, h2))}
    body.update(kw)
    return actor.post(f"/api/events/{ev['id']}/sessions", body)


def speaker(w, name="Dr. X"):
    r = w.manager.post("/api/speakers", {"organization_id": w.org, "name": name, "email": "x@y.io"})
    assert r.status_code == 201, r.text
    return r.json()


def test_session_creation(w):
    ev = w.event(publish=True)
    sp, room = speaker(w), w.resource(capacity=50)
    r = sess(w.manager, ev, 1, 2, room_id=room["id"], capacity=30, speaker_ids=[sp["id"]])
    assert r.status_code == 201 and r.json()["speakers"][0]["name"] == "Dr. X"
    assert len(w.p1.get(f"/api/events/{ev['id']}/sessions").json()) == 1  # participants can read the schedule
    assert w.p1.post(f"/api/events/{ev['id']}/sessions", json={"title": "x", "start_time": iso(future(10, 1)), "end_time": iso(future(10, 2))}).status_code == 403


def test_invalid_session_timing(w):
    ev = w.event(publish=True)   # event runs +0h .. +8h
    r = sess(w.manager, ev, 3, 2)
    assert r.status_code == 422 and err(r) == "INVALID_SESSION_TIME"
    r = sess(w.manager, ev, -1, 2)
    assert r.status_code == 422 and err(r) == "SESSION_OUTSIDE_EVENT"
    r = sess(w.manager, ev, 7, 9)
    assert r.status_code == 422 and err(r) == "SESSION_OUTSIDE_EVENT"


def test_room_conflict(w):
    ev = w.event(publish=True)
    room = w.resource(capacity=50)
    assert sess(w.manager, ev, 1, 3, room_id=room["id"]).status_code == 201
    r = sess(w.manager, ev, 2, 4, room_id=room["id"])
    assert r.status_code == 409 and err(r) == "SESSION_TIME_CONFLICT"
    assert sess(w.manager, ev, 3, 4, room_id=room["id"]).status_code == 201     # adjacent ok
    assert sess(w.manager, ev, 2, 4).status_code == 201                          # no room => no conflict
    other = w.resource(name="Room B")
    assert sess(w.manager, ev, 1, 3, room_id=other["id"]).status_code == 201     # other room ok


def test_speaker_conflict(w):
    ev = w.event(publish=True)
    sp = speaker(w)
    assert sess(w.manager, ev, 1, 3, speaker_ids=[sp["id"]]).status_code == 201
    r = sess(w.manager, ev, 2, 4, speaker_ids=[sp["id"]])
    assert r.status_code == 409 and err(r) == "SPEAKER_TIME_CONFLICT"
    assert sess(w.manager, ev, 3, 4, speaker_ids=[sp["id"]]).status_code == 201


def test_session_capacity_cannot_exceed_room(w):
    ev = w.event(publish=True)
    room = w.resource(capacity=10)
    r = sess(w.manager, ev, 1, 2, room_id=room["id"], capacity=11)
    assert r.status_code == 422 and err(r) == "SESSION_CAPACITY_EXCEEDED"
    assert sess(w.manager, ev, 1, 2, room_id=room["id"], capacity=10).status_code == 201


def test_cancelled_event_rejects_sessions(w):
    ev = w.event(publish=True)
    w.manager.post(f"/api/events/{ev['id']}/cancel")
    r = sess(w.manager, ev, 1, 2)
    assert r.status_code == 409 and err(r) == "EVENT_CANCELLED"


def test_update_session_revalidates_and_notifies(w):
    ev = w.event(publish=True)
    room = w.resource(capacity=50)
    a = sess(w.manager, ev, 1, 2, room_id=room["id"]).json()
    b = sess(w.manager, ev, 3, 4, room_id=room["id"]).json()
    w.p1.post(f"/api/events/{ev['id']}/register")
    r = w.manager.patch(f"/api/sessions/{b['id']}", {"start_time": iso(future(10, 1)), "end_time": iso(future(10, 2))})
    assert r.status_code == 409 and err(r) == "SESSION_TIME_CONFLICT"
    r = w.manager.patch(f"/api/sessions/{b['id']}", {"title": "Renamed", "start_time": iso(future(10, 5)), "end_time": iso(future(10, 6))})
    assert r.status_code == 200
    assert "session_updated" in [n["type"] for n in w.p1.get("/api/notifications").json()["items"]]
    assert w.p1.patch(f"/api/sessions/{b['id']}", {"title": "x"}).status_code == 403


def test_speaker_crud_and_isolation(w):
    sp = speaker(w)
    assert w.manager.patch(f"/api/speakers/{sp['id']}", {"bio": "bio"}).json()["bio"] == "bio"
    assert w.outsider.get(f"/api/speakers/{sp['id']}").status_code == 403
    assert w.p1.delete(f"/api/speakers/{sp['id']}").status_code == 403
    assert w.manager.delete(f"/api/speakers/{sp['id']}").status_code == 204
    assert w.manager.get(f"/api/speakers/{sp['id']}").status_code == 404


def test_event_time_change_cannot_orphan_sessions(w):
    ev = w.event(publish=True)
    sess(w.manager, ev, 1, 7)
    r = w.manager.patch(f"/api/events/{ev['id']}", {"end_time": iso(future(10, 4))})
    assert r.status_code == 422 and err(r) == "SESSION_OUT_OF_EVENT_RANGE"
