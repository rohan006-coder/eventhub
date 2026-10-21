from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.database import utcnow
from app.core.errors import conflict, unauthorized
from app.core.security import (create_access_token, create_refresh_token, decode_token, hash_password, hash_token, verify_password)
from app.models.models import RefreshToken, Role, RoleName, User
from app.repositories import RefreshTokenRepo, UserRepo


def seed_roles(db):
    descr = {"org_admin": "Full control of an organization", "event_manager": "Creates and runs events",
             "staff": "Approves registrations and runs check-in", "participant": "Registers for events"}
    for r in RoleName:
        if not db.get(Role, r.value):
            db.add(Role(name=r.value, description=descr[r.value]))
    db.commit()


def seed_super_admin(db):
    if settings.SUPERADMIN_EMAIL and settings.SUPERADMIN_PASSWORD and not UserRepo(db).by_email(settings.SUPERADMIN_EMAIL):
        db.add(User(email=settings.SUPERADMIN_EMAIL, username="superadmin", full_name="Super Admin",
                    password_hash=hash_password(settings.SUPERADMIN_PASSWORD), is_super_admin=True))
        db.commit()


def _issue(db, user) -> dict:
    refresh, jti, exp = create_refresh_token(user.id)
    RefreshTokenRepo(db).add(RefreshToken(user_id=user.id, jti=jti, token_hash=hash_token(refresh), expires_at=exp))
    db.commit()
    return {"access_token": create_access_token(user.id), "refresh_token": refresh, "expires_in": settings.ACCESS_TOKEN_MINUTES * 60}


def register(db, data) -> User:
    users = UserRepo(db)
    if users.by_email(data.email):
        raise conflict("EMAIL_TAKEN", "An account with this email already exists.")
    if users.by_username(data.username):
        raise conflict("USERNAME_TAKEN", "This username is already taken.")
    user = User(email=data.email.lower(), username=data.username, full_name=data.full_name, password_hash=hash_password(data.password))
    try:
        users.add(user)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise conflict("EMAIL_TAKEN", "An account with this email or username already exists.")
    return user


def login(db, email, password) -> dict:
    user = UserRepo(db).by_email(email)
    if not user or not verify_password(password, user.password_hash):
        raise unauthorized("INVALID_CREDENTIALS", "Incorrect email or password.")
    if not user.is_active:
        raise unauthorized("ACCOUNT_INACTIVE", "This account has been deactivated.")
    return {**_issue(db, user), "user": user}


def refresh(db, token: str) -> dict:
    payload = decode_token(token, "refresh")
    repo = RefreshTokenRepo(db)
    row = repo.by_hash(hash_token(token))
    if not row:
        raise unauthorized("INVALID_TOKEN", "Unknown refresh token.")
    if row.revoked_at is not None:  # reuse of a rotated token => assume theft, kill every session
        repo.revoke_all(row.user_id, utcnow())
        db.commit()
        raise unauthorized("TOKEN_REUSED", "Refresh token was already used. Please sign in again.")
    user = UserRepo(db).get(int(payload["sub"]))
    if not user or not user.is_active:
        raise unauthorized("ACCOUNT_INACTIVE", "This account has been deactivated.")
    row.revoked_at = utcnow()  # rotation
    return {**_issue(db, user), "user": user}


def logout(db, token: str):
    row = RefreshTokenRepo(db).by_hash(hash_token(token))
    if row and row.revoked_at is None:
        row.revoked_at = utcnow()
        db.commit()


def change_password(db, user, current, new):
    if not verify_password(current, user.password_hash):
        raise unauthorized("INVALID_CREDENTIALS", "Current password is incorrect.")
    user.password_hash = hash_password(new)
    RefreshTokenRepo(db).revoke_all(user.id, utcnow())
    db.commit()
