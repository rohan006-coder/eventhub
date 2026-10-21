from tests.helpers import err, iso, future


def test_org_isolation_reads(w):
    ev = w.event(publish=True)
    res = w.resource()
    o = w.outsider
    assert o.get(f"/api/organizations/{w.org}").status_code == 403
    assert err(o.get(f"/api/organizations/{w.org}")) == "ORGANIZATION_ACCESS_DENIED"
    assert o.get(f"/api/events/{ev['id']}").status_code == 403
    assert o.get(f"/api/resources/{res['id']}").status_code == 403
    assert o.get(f"/api/organizations/{w.org}/members").status_code == 403
    # list endpoints silently exclude foreign data
    assert o.get("/api/events").json()["total"] == 0
    assert o.get(f"/api/events?organization_id={w.org}").status_code == 403


def test_org_isolation_writes(w):
    ev = w.event(publish=True)
    o = w.outsider
    assert o.patch(f"/api/events/{ev['id']}", {"name": "hacked"}).status_code == 403
    assert o.post(f"/api/events/{ev['id']}/register").status_code == 403
    assert o.post(f"/api/organizations/{w.org}/members", {"email": "olga@test.io", "role": "org_admin"}).status_code == 403
    r = o.post("/api/events", {"organization_id": w.org, "name": "Evil", "start_time": iso(future(1)), "end_time": iso(future(2))})
    assert r.status_code == 403
    r = o.post("/api/resources", {"organization_id": w.org, "name": "X", "type": "camera"})
    assert r.status_code == 403


def test_cannot_manage_member_of_other_org(w):
    mem = w.admin.get(f"/api/organizations/{w.org}/members").json()["items"][1]
    # org B's admin addresses org A's member through org B's URL
    r = w.outsider.patch(f"/api/organizations/{w.org_b}/members/{mem['id']}/role", {"role": "org_admin"})
    assert r.status_code == 404


def test_role_permissions_matrix(w):
    body = {"organization_id": w.org, "name": "Evt", "start_time": iso(future(3)), "end_time": iso(future(4))}
    assert w.p1.post("/api/events", body).status_code == 403
    assert w.staff.post("/api/events", body).status_code == 403
    assert w.manager.post("/api/events", body).status_code == 201
    assert w.admin.post("/api/events", body).status_code == 201
    # member management is admin-only
    for actor in (w.manager, w.staff, w.p1):
        assert actor.post(f"/api/organizations/{w.org}/members", {"email": "olga@test.io"}).status_code == 403
    assert w.manager.patch(f"/api/organizations/{w.org}", {"description": "x"}).status_code == 403
    assert w.admin.patch(f"/api/organizations/{w.org}", {"description": "x"}).status_code == 200
    # resources: members read, admin writes
    assert w.manager.post("/api/resources", {"organization_id": w.org, "name": "R", "type": "camera"}).status_code == 403


def test_event_level_authorization(w):
    ev = w.event()
    other_mgr_email = "mgr2"
    from tests.helpers import Actor
    m2 = Actor(w.client, other_mgr_email)
    w.admin.post(f"/api/organizations/{w.org}/members", {"email": "mgr2@test.io", "role": "event_manager"})
    assert m2.patch(f"/api/events/{ev['id']}", {"name": "Taken over"}).status_code == 403
    assert err(m2.patch(f"/api/events/{ev['id']}", {"name": "x"})) == "EVENT_ACCESS_DENIED"
    assert w.admin.patch(f"/api/events/{ev['id']}", {"name": "Admin edit"}).status_code == 200


def test_participant_cannot_see_draft(w):
    ev = w.event()
    assert w.p1.get(f"/api/events/{ev['id']}").status_code == 404
    assert w.p1.get("/api/events").json()["total"] == 0
    assert w.staff.get(f"/api/events/{ev['id']}").status_code == 200


def test_deactivated_member_loses_access(w):
    members = w.admin.get(f"/api/organizations/{w.org}/members").json()["items"]
    pat = next(m for m in members if m["user"]["username"] == "pat")
    assert w.admin.post(f"/api/organizations/{w.org}/members/{pat['id']}/deactivate").status_code == 200
    assert w.p1.get(f"/api/organizations/{w.org}").status_code == 403
    assert w.admin.post(f"/api/organizations/{w.org}/members/{pat['id']}/activate").status_code == 200
    assert w.p1.get(f"/api/organizations/{w.org}").status_code == 200


def test_cannot_remove_last_admin(w):
    members = w.admin.get(f"/api/organizations/{w.org}/members").json()["items"]
    me = next(m for m in members if m["user"]["username"] == "alice")
    r = w.admin.delete(f"/api/organizations/{w.org}/members/{me['id']}")
    assert r.status_code == 400 and err(r) == "LAST_ADMIN"
    r = w.admin.patch(f"/api/organizations/{w.org}/members/{me['id']}/role", {"role": "participant"})
    assert err(r) == "LAST_ADMIN"
