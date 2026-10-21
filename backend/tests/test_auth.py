from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.models import User
from tests.helpers import PW, Actor, err


def test_register_login_me(client):
    a = Actor(client, "bob")
    r = a.get("/api/auth/me")
    assert r.status_code == 200 and r.json()["email"] == "bob@test.io"
    assert "password" not in r.text


def test_register_duplicate_and_weak_password(client):
    Actor(client, "bob")
    r = client.post("/api/auth/register", json={"email": "bob@test.io", "username": "other", "full_name": "B", "password": PW})
    assert r.status_code == 409 and err(r) == "EMAIL_TAKEN"
    r = client.post("/api/auth/register", json={"email": "x@test.io", "username": "xx1", "full_name": "B", "password": "short"})
    assert r.status_code == 422 and err(r) == "VALIDATION_ERROR"


def test_invalid_credentials(client):
    Actor(client, "bob")
    r = client.post("/api/auth/login", json={"email": "bob@test.io", "password": "WrongPass1"})
    assert r.status_code == 401 and err(r) == "INVALID_CREDENTIALS"
    r = client.post("/api/auth/login", json={"email": "nobody@test.io", "password": PW})
    assert r.status_code == 401 and err(r) == "INVALID_CREDENTIALS"


def test_protected_route_requires_token(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401 and err(r) == "NOT_AUTHENTICATED"
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401 and err(r) == "INVALID_TOKEN"


def test_expired_access_token(client):
    a = Actor(client, "bob")
    expired = jwt.encode({"sub": str(a.id), "type": "access", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
                         settings.SECRET_KEY, algorithm="HS256")
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401 and err(r) == "TOKEN_EXPIRED"


def test_refresh_token_is_rotated_and_reuse_is_detected(client):
    a = Actor(client, "bob")
    old = a.tokens["refresh_token"]
    r = client.post("/api/auth/refresh", json={"refresh_token": old})
    assert r.status_code == 200
    new = r.json()["refresh_token"]
    assert new != old
    # old token reuse -> rejected and the whole family is revoked
    r = client.post("/api/auth/refresh", json={"refresh_token": old})
    assert r.status_code == 401 and err(r) == "TOKEN_REUSED"
    r = client.post("/api/auth/refresh", json={"refresh_token": new})
    assert r.status_code == 401


def test_access_token_cannot_be_used_as_refresh(client):
    a = Actor(client, "bob")
    r = client.post("/api/auth/refresh", json={"refresh_token": a.tokens["access_token"]})
    assert r.status_code == 401 and err(r) == "INVALID_TOKEN"


def test_logout_revokes_refresh_token(client):
    a = Actor(client, "bob")
    assert client.post("/api/auth/logout", json={"refresh_token": a.tokens["refresh_token"]}).status_code == 204
    r = client.post("/api/auth/refresh", json={"refresh_token": a.tokens["refresh_token"]})
    assert r.status_code == 401


def test_inactive_user_cannot_authenticate(client):
    a = Actor(client, "bob")
    db = SessionLocal()
    db.get(User, a.id).is_active = False
    db.commit()
    db.close()
    r = client.post("/api/auth/login", json={"email": "bob@test.io", "password": PW})
    assert r.status_code == 401 and err(r) == "ACCOUNT_INACTIVE"
    assert a.get("/api/auth/me").status_code == 401  # existing access token stops working too
    r = client.post("/api/auth/refresh", json={"refresh_token": a.tokens["refresh_token"]})
    assert r.status_code == 401


def test_change_password(client):
    a = Actor(client, "bob")
    assert a.post("/api/auth/change-password", {"current_password": "bad", "new_password": "NewPassw0rd"}).status_code == 401
    assert a.post("/api/auth/change-password", {"current_password": PW, "new_password": "NewPassw0rd"}).status_code == 204
    assert client.post("/api/auth/login", json={"email": "bob@test.io", "password": PW}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "bob@test.io", "password": "NewPassw0rd"}).status_code == 200
    # sessions were revoked
    assert client.post("/api/auth/refresh", json={"refresh_token": a.tokens["refresh_token"]}).status_code == 401
