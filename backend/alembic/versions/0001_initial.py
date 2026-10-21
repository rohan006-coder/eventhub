"""Initial schema: all tables, seed roles, PostgreSQL overlap-exclusion constraints.

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Baseline migration: creates the schema straight from the model metadata so models and DB can never drift
    # at revision 0001. Every later change should be a regular `alembic revision --autogenerate` migration.
    from app.core.database import Base
    import app.models  # noqa: F401

    bind = op.get_bind()
    Base.metadata.create_all(bind)

    roles = sa.table("roles", sa.column("name", sa.String), sa.column("description", sa.String))
    op.bulk_insert(roles, [
        {"name": "org_admin", "description": "Full control of an organization"},
        {"name": "event_manager", "description": "Creates and runs events"},
        {"name": "staff", "description": "Approves registrations and runs check-in"},
        {"name": "participant", "description": "Registers for events"},
    ])

    if bind.dialect.name == "postgresql":
        # Database-level guarantee against double booking, independent of application locking.
        op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
        op.execute("""
            ALTER TABLE resource_bookings ADD CONSTRAINT ex_booking_no_overlap
            EXCLUDE USING gist (resource_id WITH =, tstzrange(start_time, end_time, '[)') WITH &&)
            WHERE (status IN ('requested', 'approved'))
        """)
        op.execute("""
            ALTER TABLE event_sessions ADD CONSTRAINT ex_session_room_no_overlap
            EXCLUDE USING gist (room_id WITH =, tstzrange(start_time, end_time, '[)') WITH &&)
            WHERE (room_id IS NOT NULL)
        """)


def downgrade():
    from app.core.database import Base
    import app.models  # noqa: F401

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE resource_bookings DROP CONSTRAINT IF EXISTS ex_booking_no_overlap")
        op.execute("ALTER TABLE event_sessions DROP CONSTRAINT IF EXISTS ex_session_room_no_overlap")
    Base.metadata.drop_all(bind)
