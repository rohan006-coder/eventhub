from app.models.models import AuditLog


def audit(db, user, action: str, entity_type: str, entity_id=None, org_id=None, details=None):
    """Adds an audit row to the current transaction (committed with the business change)."""
    db.add(AuditLog(organization_id=org_id, user_id=getattr(user, "id", None), action=action,
                    entity_type=entity_type, entity_id=entity_id, details=details or {}))
