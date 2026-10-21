import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (JSON, Boolean, CheckConstraint, Column, Enum, ForeignKey, Index, Integer, String,
                        Table, Text, UniqueConstraint, func, text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, UTCDateTime, utcnow


# ---------------------------------------------------------------- enums
class RoleName(str, enum.Enum):
    org_admin = "org_admin"
    event_manager = "event_manager"
    staff = "staff"
    participant = "participant"


class EventStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    ongoing = "ongoing"
    completed = "completed"
    cancelled = "cancelled"
    archived = "archived"


class RegistrationStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    waitlisted = "waitlisted"
    cancelled = "cancelled"
    rejected = "rejected"
    attended = "attended"
    no_show = "no_show"


class ResourceType(str, enum.Enum):
    meeting_room = "meeting_room"
    conference_hall = "conference_hall"
    projector = "projector"
    camera = "camera"
    vehicle = "vehicle"
    equipment = "equipment"


class ResourceStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class BookingStatus(str, enum.Enum):
    requested = "requested"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"
    completed = "completed"


class AttendanceStatus(str, enum.Enum):
    registered = "registered"
    attended = "attended"
    no_show = "no_show"


class NotificationType(str, enum.Enum):
    event_published = "event_published"
    registration_confirmed = "registration_confirmed"
    registration_waitlisted = "registration_waitlisted"
    registration_rejected = "registration_rejected"
    registration_cancelled = "registration_cancelled"
    booking_approved = "booking_approved"
    booking_rejected = "booking_rejected"
    event_cancelled = "event_cancelled"
    session_updated = "session_updated"
    user_mentioned = "user_mentioned"
    event_starting_soon = "event_starting_soon"
    new_registration = "new_registration"


def E(cls):
    return Enum(cls, native_enum=False, length=30, validate_strings=True, create_constraint=True,
                values_callable=lambda e: [m.value for m in e])


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow,
                                                 server_default=func.now(), nullable=False)


# ---------------------------------------------------------------- identity
class Role(Base):
    __tablename__ = "roles"
    name: Mapped[str] = mapped_column(String(30), primary_key=True)
    description: Mapped[str] = mapped_column(String(255), default="")


class User(Timestamps, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_super_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Organization(Timestamps, Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class OrganizationMember(Timestamps, Base):
    __tablename__ = "organization_members"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_org_member"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(ForeignKey("roles.name"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    user: Mapped[User] = relationship(lazy="joined")


# ---------------------------------------------------------------- resources
class Resource(Timestamps, Base):
    __tablename__ = "resources"
    __table_args__ = (CheckConstraint("capacity IS NULL OR capacity >= 0", name="ck_resource_capacity"),
                      Index("ix_resource_org_status", "organization_id", "status"))
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    type: Mapped[ResourceType] = mapped_column(E(ResourceType))
    description: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str] = mapped_column(String(255), default="")
    capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[ResourceStatus] = mapped_column(E(ResourceStatus), default=ResourceStatus.active)


# ---------------------------------------------------------------- events
class Event(Timestamps, Base):
    __tablename__ = "events"
    __table_args__ = (CheckConstraint("end_time > start_time", name="ck_event_time"),
                      CheckConstraint("capacity > 0", name="ck_event_capacity"),
                      Index("ix_event_org_status", "organization_id", "status"),
                      Index("ix_event_org_start", "organization_id", "start_time"))
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    organizer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str] = mapped_column(String(255), default="")
    start_time: Mapped[datetime] = mapped_column(UTCDateTime)
    end_time: Mapped[datetime] = mapped_column(UTCDateTime)
    registration_deadline: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, default=100)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[EventStatus] = mapped_column(E(EventStatus), default=EventStatus.draft)
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    organizer: Mapped[Optional[User]] = relationship(lazy="joined")

    @property
    def organizer_name(self):
        return self.organizer.full_name if self.organizer else None


speaker_sessions = Table(
    "speaker_sessions", Base.metadata,
    Column("session_id", ForeignKey("event_sessions.id", ondelete="CASCADE"), primary_key=True),
    Column("speaker_id", ForeignKey("speakers.id", ondelete="CASCADE"), primary_key=True),
)


class Speaker(Timestamps, Base):
    __tablename__ = "speakers"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    bio: Mapped[str] = mapped_column(Text, default="")
    company: Mapped[str] = mapped_column(String(150), default="")


class EventSession(Timestamps, Base):
    __tablename__ = "event_sessions"
    __table_args__ = (CheckConstraint("end_time > start_time", name="ck_session_time"),
                      CheckConstraint("capacity IS NULL OR capacity > 0", name="ck_session_capacity"),
                      Index("ix_session_room_time", "room_id", "start_time", "end_time"))
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    start_time: Mapped[datetime] = mapped_column(UTCDateTime)
    end_time: Mapped[datetime] = mapped_column(UTCDateTime)
    room_id: Mapped[Optional[int]] = mapped_column(ForeignKey("resources.id", ondelete="SET NULL"), nullable=True)
    capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    speakers: Mapped[list[Speaker]] = relationship(secondary=speaker_sessions, lazy="selectin")


class Registration(Timestamps, Base):
    __tablename__ = "registrations"
    __table_args__ = (
        Index("uq_active_registration", "event_id", "user_id", unique=True,
              postgresql_where=text("status NOT IN ('cancelled','rejected')"),
              sqlite_where=text("status NOT IN ('cancelled','rejected')")),
        Index("ix_reg_event_status", "event_id", "status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[RegistrationStatus] = mapped_column(E(RegistrationStatus))
    notes: Mapped[str] = mapped_column(Text, default="")
    decided_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    user: Mapped[User] = relationship(foreign_keys=[user_id], lazy="joined")
    event: Mapped[Event] = relationship(lazy="joined")

    @property
    def event_name(self):
        return self.event.name


class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    registration_id: Mapped[int] = mapped_column(ForeignKey("registrations.id", ondelete="CASCADE"), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Attendance(Timestamps, Base):
    __tablename__ = "attendance"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    registration_id: Mapped[int] = mapped_column(ForeignKey("registrations.id", ondelete="CASCADE"), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[AttendanceStatus] = mapped_column(E(AttendanceStatus), default=AttendanceStatus.registered)
    checked_in_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    marked_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


# ---------------------------------------------------------------- bookings
class ResourceBooking(Timestamps, Base):
    __tablename__ = "resource_bookings"
    __table_args__ = (CheckConstraint("end_time > start_time", name="ck_booking_time"),
                      Index("ix_booking_resource_time", "resource_id", "start_time", "end_time"))
    id: Mapped[int] = mapped_column(primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"))
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"), nullable=True)
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    start_time: Mapped[datetime] = mapped_column(UTCDateTime)
    end_time: Mapped[datetime] = mapped_column(UTCDateTime)
    status: Mapped[BookingStatus] = mapped_column(E(BookingStatus), default=BookingStatus.requested)
    purpose: Mapped[str] = mapped_column(Text, default="")
    decided_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resource: Mapped[Resource] = relationship(lazy="joined")


# ---------------------------------------------------------------- collaboration
class Comment(Timestamps, Base):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[Optional[int]] = mapped_column(ForeignKey("event_sessions.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text)
    user: Mapped[User] = relationship(lazy="joined")

    @property
    def author_name(self):
        return self.user.full_name


class Attachment(Base):
    __tablename__ = "attachments"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    entity_type: Mapped[str] = mapped_column(String(20))  # event | session | speaker | registration
    entity_id: Mapped[int] = mapped_column(Integer)
    file_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(String(500))
    uploaded_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    __table_args__ = (Index("ix_attachment_entity", "entity_type", "entity_id"),)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notif_user_read", "user_id", "is_read"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    organization_id: Mapped[Optional[int]] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    type: Mapped[NotificationType] = mapped_column(E(NotificationType))
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[Optional[int]] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
