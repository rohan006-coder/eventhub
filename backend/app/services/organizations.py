from app.core.errors import bad_request, conflict, forbidden, not_found
from app.models.models import Organization, OrganizationMember
from app.repositories import MemberRepo, OrgRepo, UserRepo
from app.services.audit import audit
from app.services.permissions import require_role


def create(db, user, data) -> Organization:
    orgs = OrgRepo(db)
    if orgs.by_name(data.name):
        raise conflict("ORGANIZATION_EXISTS", "An organization with this name already exists.")
    org = orgs.add(Organization(name=data.name, description=data.description, created_by=user.id))
    MemberRepo(db).add(OrganizationMember(organization_id=org.id, user_id=user.id, role="org_admin"))
    audit(db, user, "organization.create", "organization", org.id, org.id)
    db.commit()
    org.my_role = "org_admin"
    return org


def list_for(db, user):
    if user.is_super_admin:
        rows = [(o, "org_admin") for o in OrgRepo(db).all()]
    else:
        rows = OrgRepo(db).for_user(user.id)
    out = []
    for org, role in rows:
        org.my_role = role
        out.append(org)
    return out


def get(db, user, org_id):
    org = OrgRepo(db).get(org_id)
    if not org:
        raise not_found("Organization")
    org.my_role = require_role(db, user, org_id)
    return org


def update(db, user, org_id, data):
    org = get(db, user, org_id)
    require_role(db, user, org_id, "org_admin")
    patch = data.model_dump(exclude_unset=True)
    if "name" in patch:
        other = OrgRepo(db).by_name(patch["name"])
        if other and other.id != org.id:
            raise conflict("ORGANIZATION_EXISTS", "An organization with this name already exists.")
    for k, v in patch.items():
        setattr(org, k, v)
    audit(db, user, "organization.update", "organization", org.id, org.id, patch)
    db.commit()
    return org


# ---- members
def list_members(db, user, org_id, page, size):
    require_role(db, user, org_id, "staff")
    return MemberRepo(db).list(org_id, page, size)


def _member(db, org_id, member_id):
    mem = MemberRepo(db).get(member_id)
    if not mem or mem.organization_id != org_id:  # never leak members of other orgs
        raise not_found("Member")
    return mem


def _guard_last_admin(db, mem):
    if mem.role == "org_admin" and mem.is_active and MemberRepo(db).count_active_admins(mem.organization_id) <= 1:
        raise bad_request("LAST_ADMIN", "An organization must keep at least one active admin.")


def add_member(db, user, org_id, data):
    require_role(db, user, org_id, "org_admin")
    target = UserRepo(db).by_email(data.email)
    if not target:
        raise not_found("User")
    repo = MemberRepo(db)
    if repo.get_for(org_id, target.id):
        raise conflict("ALREADY_MEMBER", "This user is already a member of the organization.")
    mem = repo.add(OrganizationMember(organization_id=org_id, user_id=target.id, role=data.role.value))
    audit(db, user, "member.add", "member", mem.id, org_id, {"user_id": target.id, "role": data.role.value})
    db.commit()
    return mem


def change_role(db, user, org_id, member_id, role):
    require_role(db, user, org_id, "org_admin")
    mem = _member(db, org_id, member_id)
    if mem.role == "org_admin" and role.value != "org_admin":
        _guard_last_admin(db, mem)
    mem.role = role.value
    audit(db, user, "member.role", "member", mem.id, org_id, {"role": role.value})
    db.commit()
    return mem


def set_active(db, user, org_id, member_id, active: bool):
    require_role(db, user, org_id, "org_admin")
    mem = _member(db, org_id, member_id)
    if not active:
        _guard_last_admin(db, mem)
    mem.is_active = active
    audit(db, user, "member.activate" if active else "member.deactivate", "member", mem.id, org_id)
    db.commit()
    return mem


def remove_member(db, user, org_id, member_id):
    require_role(db, user, org_id, "org_admin")
    mem = _member(db, org_id, member_id)
    _guard_last_admin(db, mem)
    MemberRepo(db).delete(mem)
    audit(db, user, "member.remove", "member", member_id, org_id)
    db.commit()
