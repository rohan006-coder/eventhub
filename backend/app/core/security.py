import hashlib
import hmac
import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings
from app.core.errors import unauthorized


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$")
        dk = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(dk.hex(), digest)
    except Exception:
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _encode(payload: dict) -> str:
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    return _encode({"sub": str(user_id), "type": "access", "iat": now,
                    "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_MINUTES)})


def create_refresh_token(user_id: int):
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=settings.REFRESH_TOKEN_DAYS)
    jti = uuid.uuid4().hex
    return _encode({"sub": str(user_id), "type": "refresh", "jti": jti, "iat": now, "exp": exp}), jti, exp


def decode_token(token: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise unauthorized("TOKEN_EXPIRED", "The token has expired.")
    except jwt.InvalidTokenError:
        raise unauthorized("INVALID_TOKEN", "The token is invalid.")
    if payload.get("type") != expected_type:
        raise unauthorized("INVALID_TOKEN", "Wrong token type.")
    return payload
