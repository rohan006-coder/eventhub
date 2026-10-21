from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import Pager, get_current_user, paged
from app.core.database import get_db
from app.repositories import AuditRepo
from app.schemas import MemberIn, MemberOut, MemberRoleIn, OrgIn, OrgOut, OrgUpdate, Page
from app.services import organizations as svc
from app.services.permissions import require_role

router = APIRouter(prefix="/api/organizations", tags=["organizations"])


@router.post("", response_model=OrgOut, status_code=201)
def create(data: OrgIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.create(db, user, data)


@router.get("", response_model=list[OrgOut])
def mine(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.list_for(db, user)


@router.get("/{org_id}", response_model=OrgOut)
def get(org_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.get(db, user, org_id)


@router.patch("/{org_id}", response_model=OrgOut)
def update(org_id: int, data: OrgUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.update(db, user, org_id, data)


@router.get("/{org_id}/members", response_model=Page[MemberOut])
def members(org_id: int, p: Pager = Depends(), user=Depends(get_current_user), db: Session = Depends(get_db)):
    items, total = svc.list_members(db, user, org_id, p.page, p.size)
    return paged(items, total, p)


@router.post("/{org_id}/members", response_model=MemberOut, status_code=201)
def add_member(org_id: int, data: MemberIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.add_member(db, user, org_id, data)


@router.patch("/{org_id}/members/{member_id}/role", response_model=MemberOut)
def change_role(org_id: int, member_id: int, data: MemberRoleIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.change_role(db, user, org_id, member_id, data.role)


@router.post("/{org_id}/members/{member_id}/activate", response_model=MemberOut)
def activate(org_id: int, member_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.set_active(db, user, org_id, member_id, True)


@router.post("/{org_id}/members/{member_id}/deactivate", response_model=MemberOut)
def deactivate(org_id: int, member_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.set_active(db, user, org_id, member_id, False)


@router.delete("/{org_id}/members/{member_id}", status_code=204)
def remove(org_id: int, member_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    svc.remove_member(db, user, org_id, member_id)
    return Response(status_code=204)


@router.get("/{org_id}/audit-logs")
def audit_logs(org_id: int, p: Pager = Depends(), user=Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, org_id, "org_admin")
    items, total = AuditRepo(db).list(org_id, p.page, p.size)
    rows = [{"id": a.id, "user_id": a.user_id, "action": a.action, "entity_type": a.entity_type, "entity_id": a.entity_id,
             "details": a.details, "created_at": a.created_at} for a in items]
    return paged(rows, total, p)
