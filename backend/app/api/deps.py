from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import unauthorized
from app.core.security import decode_token
from app.models.models import User
from app.repositories import UserRepo

bearer = HTTPBearer(auto_error=False)


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if creds is None:
        raise unauthorized("NOT_AUTHENTICATED", "Authentication required.")
    payload = decode_token(creds.credentials, "access")
    user = UserRepo(db).get(int(payload["sub"]))
    if not user:
        raise unauthorized("INVALID_TOKEN", "The token is invalid.")
    if not user.is_active:
        raise unauthorized("ACCOUNT_INACTIVE", "This account has been deactivated.")
    return user


class Pager:
    def __init__(self, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
        self.page, self.size = page, page_size


def paged(items, total, p: Pager) -> dict:
    return {"items": items, "total": total, "page": p.page, "page_size": p.size, "pages": max(1, -(-total // p.size))}
