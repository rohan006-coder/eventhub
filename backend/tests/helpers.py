from datetime import datetime, timedelta, timezone

PW = "Passw0rdX"


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def future(days=10, hours=0):
    base = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return base + timedelta(days=days, hours=hours)


class Actor:
    def __init__(self, client, name):
        self.client, self.name = client, name
        r = client.post("/api/auth/register", json={"email": f"{name}@test.io", "username": name, "full_name": name.title(), "password": PW})
        assert r.status_code == 201, r.text
        self.id = r.json()["id"]
        r = client.post("/api/auth/login", json={"email": f"{name}@test.io", "password": PW})
        assert r.status_code == 200, r.text
        self.tokens = r.json()
        self.h = {"Authorization": f"Bearer {self.tokens['access_token']}"}

    def req(self, method, url, **kw):
        return self.client.request(method, url, headers=self.h, **kw)

    def get(self, url, **kw): return self.req("GET", url, **kw)
    def post(self, url, json=None, **kw): return self.req("POST", url, json=json, **kw)
    def patch(self, url, json=None, **kw): return self.req("PATCH", url, json=json, **kw)
    def delete(self, url, **kw): return self.req("DELETE", url, **kw)


class World:
    def __init__(self, client):
        self.client = client
        self.admin = Actor(client, "alice")
        self.manager = Actor(client, "mallory")
        self.staff = Actor(client, "sam")
        self.p1, self.p2, self.p3 = Actor(client, "pat"), Actor(client, "paula"), Actor(client, "pete")
        self.outsider = Actor(client, "olga")  # admin of org B
        self.org = self.admin.post("/api/organizations", {"name": "Org A"}).json()["id"]
        self.org_b = self.outsider.post("/api/organizations", {"name": "Org B"}).json()["id"]
        for actor, role in ((self.manager, "event_manager"), (self.staff, "staff"), (self.p1, "participant"), (self.p2, "participant"), (self.p3, "participant")):
            r = self.admin.post(f"/api/organizations/{self.org}/members", {"email": f"{actor.name}@test.io", "role": role})
            assert r.status_code == 201, r.text

    def event(self, actor=None, *, publish=False, org=None, **over):
        actor = actor or self.manager
        body = {"organization_id": org or self.org, "name": "Conference", "description": "d", "location": "Hall 1",
                "start_time": iso(future(10)), "end_time": iso(future(10, 8)), "capacity": 2}
        body.update(over)
        r = actor.post("/api/events", body)
        assert r.status_code == 201, r.text
        ev = r.json()
        if publish:
            r = actor.post(f"/api/events/{ev['id']}/publish")
            assert r.status_code == 200, r.text
            ev = r.json()
        return ev

    def resource(self, **over):
        body = {"organization_id": self.org, "name": "Room A", "type": "meeting_room", "capacity": 20}
        body.update(over)
        r = self.admin.post("/api/resources", body)
        assert r.status_code == 201, r.text
        return r.json()


def err(resp):
    return resp.json()["error"]["code"]
