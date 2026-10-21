from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.schemas import AuthOut, ChangePasswordIn, LoginIn, RefreshIn, RegisterIn, UpdateProfileIn, UserOut
from app.services import auth as svc

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    return svc.register(db, data)


@router.post("/login", response_model=AuthOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    return svc.login(db, data.email, data.password)


@router.post("/refresh", response_model=AuthOut)
def refresh(data: RefreshIn, db: Session = Depends(get_db)):
    return svc.refresh(db, data.refresh_token)


@router.post("/logout", status_code=204)
def logout(data: RefreshIn, db: Session = Depends(get_db)):
    svc.logout(db, data.refresh_token)
    return Response(status_code=204)


@router.get("/me", response_model=UserOut)
def me(user=Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(data: UpdateProfileIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    user.full_name = data.full_name
    db.commit()
    return user


@router.post("/change-password", status_code=204)
def change_password(data: ChangePasswordIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    svc.change_password(db, user, data.current_password, data.new_password)
    return Response(status_code=204)
