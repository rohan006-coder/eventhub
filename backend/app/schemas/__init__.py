import re
from datetime import datetime, timezone
from typing import Annotated, Generic, Optional, TypeVar

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.models import (AttendanceStatus, BookingStatus, EventStatus, NotificationType, RegistrationStatus,
                               ResourceStatus, ResourceType, RoleName)

T = TypeVar("T")


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


DT = Annotated[datetime, AfterValidator(_utc)]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    model_config = ConfigDict(from_attributes=True)
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


# ------------------------------------------------------------------ auth / users
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,50}$")


class RegisterIn(BaseModel):
    email: EmailStr
    username: str
    full_name: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def _u(cls, v):
        if not USERNAME_RE.match(v):
            raise ValueError("username must be 3-50 chars: letters, digits, _ . -")
        return v.lower()

    @field_validator("password")
    @classmethod
    def _p(cls, v):
        if not (re.search(r"[A-Za-z]", v) and re.search(r"\d", v)):
            raise ValueError("password must contain letters and digits")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(ORM):
    id: int
    email: EmailStr
    username: str
    full_name: str
    is_active: bool
    is_super_admin: bool


class UpdateProfileIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthOut(TokenOut):
    user: UserOut


# ------------------------------------------------------------------ organizations
class OrgIn(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    description: str = ""


class OrgUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class OrgOut(ORM):
    id: int
    name: str
    description: str
    is_active: bool
    created_at: datetime
    my_role: Optional[str] = None


class MemberIn(BaseModel):
    email: EmailStr
    role: RoleName = RoleName.participant


class MemberRoleIn(BaseModel):
    role: RoleName


class MemberOut(ORM):
    id: int
    organization_id: int
    user_id: int
    role: str
    is_active: bool
    user: UserOut


# ------------------------------------------------------------------ events
class EventIn(BaseModel):
    organization_id: int
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    location: str = ""
    start_time: DT
    end_time: DT
    registration_deadline: Optional[DT] = None
    capacity: int = Field(100, gt=0, le=1_000_000)
    requires_approval: bool = False


class EventUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: Optional[DT] = None
    end_time: Optional[DT] = None
    registration_deadline: Optional[DT] = None
    capacity: Optional[int] = Field(None, gt=0, le=1_000_000)
    requires_approval: Optional[bool] = None


class TransitionIn(BaseModel):
    status: EventStatus


class EventOut(ORM):
    id: int
    organization_id: int
    organizer_id: Optional[int]
    organizer_name: Optional[str] = None
    name: str
    description: str
    location: str
    start_time: datetime
    end_time: datetime
    registration_deadline: Optional[datetime]
    capacity: int
    requires_approval: bool
    status: EventStatus
    created_at: datetime
    updated_at: datetime
    confirmed_count: Optional[int] = None
    waitlist_count: Optional[int] = None


# ------------------------------------------------------------------ registrations
class RegisterEventIn(BaseModel):
    notes: str = ""


class RegistrationOut(ORM):
    id: int
    event_id: int
    user_id: int
    status: RegistrationStatus
    notes: str
    created_at: datetime
    updated_at: datetime
    user: UserOut
    event_name: Optional[str] = None
    waitlist_position: Optional[int] = None


# ------------------------------------------------------------------ resources / bookings
class ResourceIn(BaseModel):
    organization_id: int
    name: str = Field(min_length=1, max_length=150)
    type: ResourceType
    description: str = ""
    location: str = ""
    capacity: Optional[int] = Field(None, ge=0)


class ResourceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    type: Optional[ResourceType] = None
    description: Optional[str] = None
    location: Optional[str] = None
    capacity: Optional[int] = Field(None, ge=0)


class ResourceOut(ORM):
    id: int
    organization_id: int
    name: str
    type: ResourceType
    description: str
    location: str
    capacity: Optional[int]
    status: ResourceStatus


class BookingIn(BaseModel):
    resource_id: int
    event_id: Optional[int] = None
    start_time: DT
    end_time: DT
    purpose: str = ""


class BookingUpdate(BaseModel):
    start_time: Optional[DT] = None
    end_time: Optional[DT] = None
    purpose: Optional[str] = None


class BookingOut(ORM):
    id: int
    resource_id: int
    resource: ResourceOut
    event_id: Optional[int]
    requested_by: int
    start_time: datetime
    end_time: datetime
    status: BookingStatus
    purpose: str
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------ speakers / sessions
class SpeakerIn(BaseModel):
    organization_id: int
    name: str = Field(min_length=1, max_length=150)
    email: Optional[EmailStr] = None
    bio: str = ""
    company: str = ""


class SpeakerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    email: Optional[EmailStr] = None
    bio: Optional[str] = None
    company: Optional[str] = None


class SpeakerOut(ORM):
    id: int
    organization_id: int
    name: str
    email: Optional[str]
    bio: str
    company: str


class SessionIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    start_time: DT
    end_time: DT
    room_id: Optional[int] = None
    capacity: Optional[int] = Field(None, gt=0)
    speaker_ids: list[int] = []


class SessionUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    start_time: Optional[DT] = None
    end_time: Optional[DT] = None
    room_id: Optional[int] = None
    capacity: Optional[int] = Field(None, gt=0)
    speaker_ids: Optional[list[int]] = None


class SessionOut(ORM):
    id: int
    event_id: int
    title: str
    description: str
    start_time: datetime
    end_time: datetime
    room_id: Optional[int]
    capacity: Optional[int]
    speakers: list[SpeakerOut]


# ------------------------------------------------------------------ attendance / files / comments / notifications
class AttendanceIn(BaseModel):
    registration_id: int
    status: AttendanceStatus = AttendanceStatus.attended


class AttendanceUpdate(BaseModel):
    status: AttendanceStatus


class AttendanceOut(ORM):
    id: int
    event_id: int
    registration_id: int
    user_id: int
    status: AttendanceStatus
    checked_in_at: Optional[datetime]


class AttachmentOut(ORM):
    id: int
    event_id: int
    entity_type: str
    entity_id: int
    file_name: str
    mime_type: str
    file_size: int
    uploaded_by: Optional[int]
    created_at: datetime


class CommentIn(BaseModel):
    event_id: int
    session_id: Optional[int] = None
    body: str = Field(min_length=1, max_length=5000)


class CommentUpdate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class CommentOut(ORM):
    id: int
    event_id: int
    session_id: Optional[int]
    user_id: int
    author_name: str
    body: str
    created_at: datetime
    updated_at: datetime


class NotificationOut(ORM):
    id: int
    type: NotificationType
    title: str
    message: str
    data: Optional[dict]
    is_read: bool
    created_at: datetime
