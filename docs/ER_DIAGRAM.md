# ER Diagram & Database Design

```mermaid
erDiagram
    users ||--o{ organization_members : "belongs to"
    organizations ||--o{ organization_members : has
    roles ||--o{ organization_members : "role"
    users ||--o{ refresh_tokens : owns
    organizations ||--o{ events : hosts
    organizations ||--o{ resources : owns
    organizations ||--o{ speakers : owns
    users ||--o{ events : organizes
    events ||--o{ event_sessions : contains
    resources ||--o{ event_sessions : "room"
    event_sessions }o--o{ speakers : "speaker_sessions"
    events ||--o{ registrations : receives
    users ||--o{ registrations : makes
    registrations ||--o| waitlist_entries : "queued as"
    registrations ||--o| attendance : "checked in as"
    resources ||--o{ resource_bookings : "booked via"
    events ||--o{ resource_bookings : "for"
    users ||--o{ resource_bookings : requests
    events ||--o{ comments : has
    event_sessions ||--o{ comments : has
    events ||--o{ attachments : has
    users ||--o{ notifications : receives
    organizations ||--o{ audit_logs : records

    users { int id PK  string email UK  string username UK  string password_hash  bool is_active  bool is_super_admin }
    roles { string name PK  string description }
    organizations { int id PK  string name UK  bool is_active }
    organization_members { int id PK  int organization_id FK  int user_id FK  string role FK  bool is_active }
    events { int id PK  int organization_id FK  int organizer_id FK  string name  datetime start_time  datetime end_time  datetime registration_deadline  int capacity  bool requires_approval  string status }
    event_sessions { int id PK  int event_id FK  int room_id FK  string title  datetime start_time  datetime end_time  int capacity }
    speakers { int id PK  int organization_id FK  string name  string email }
    resources { int id PK  int organization_id FK  string name  string type  int capacity  string status }
    resource_bookings { int id PK  int resource_id FK  int event_id FK  int requested_by FK  datetime start_time  datetime end_time  string status }
    registrations { int id PK  int event_id FK  int user_id FK  string status }
    waitlist_entries { int id PK  int event_id FK  int registration_id FK_UK  datetime created_at }
    attendance { int id PK  int event_id FK  int registration_id FK_UK  int user_id FK  string status  datetime checked_in_at }
    comments { int id PK  int event_id FK  int session_id FK  int user_id FK  text body }
    attachments { int id PK  int event_id FK  string entity_type  int entity_id  string file_name  string mime_type  int file_size  string storage_path  int uploaded_by FK }
    notifications { int id PK  int user_id FK  string type  string title  bool is_read  json data }
    audit_logs { int id PK  int organization_id FK  int user_id FK  string action  string entity_type  json details }
    refresh_tokens { int id PK  int user_id FK  string jti UK  string token_hash UK  datetime expires_at  datetime revoked_at }
```

## Design explanation

**Multi-tenancy.** Every business table is reachable from exactly one `organization_id` (directly, or through its event/resource). Authorization always resolves that organization first, so one tenant can never address another tenant's rows, even by guessing IDs.

**Roles.** `roles` is a lookup table; `organization_members.role` has a foreign key to it, so a member's role is per organization (the same user can be admin in one org and participant in another). `users.is_super_admin` is the only global privilege.

**Integrity rules enforced by the database**

| Rule | Mechanism |
|---|---|
| One account per email / username | unique indexes on `users` |
| One membership per user per org | `UNIQUE(organization_id, user_id)` |
| No duplicate active registration | partial unique index `(event_id, user_id) WHERE status NOT IN ('cancelled','rejected')` — a cancelled user may register again |
| A registration sits in the waitlist at most once | `UNIQUE(waitlist_entries.registration_id)` |
| One attendance record per registration | `UNIQUE(attendance.registration_id)` |
| Valid time ranges / capacities | `CHECK(end_time > start_time)`, `CHECK(capacity > 0)` on events, sessions, bookings, resources |
| Valid enums | non-native enums with `CHECK` constraints (portable, easy to migrate) |
| **No overlapping bookings / room clashes (PostgreSQL)** | `EXCLUDE USING gist (resource_id WITH =, tstzrange(start,end,'[)') WITH &&) WHERE status IN ('requested','approved')` and the same for `event_sessions.room_id` (created in migration `0001`) |
| Refresh tokens are single-use | `token_hash` unique + `revoked_at` |

**Cascading.** Deleting an organization removes its members, events, resources and speakers; deleting an event removes its sessions, registrations, waitlist, attendance, comments and attachment rows; deleting a user removes their tokens/memberships/registrations. Optional links (`events.organizer_id`, `attachments.uploaded_by`, `resource_bookings.event_id`, `event_sessions.room_id`) use `SET NULL` so history survives.

**Indexes.** Foreign keys that are filtered on are indexed, plus composites for the hot queries: `(organization_id, status)` and `(organization_id, start_time)` on events, `(event_id, status)` on registrations, `(resource_id, start_time, end_time)` on bookings, `(room_id, start_time, end_time)` on sessions, `(user_id, is_read)` on notifications.

**Timestamps.** `created_at` / `updated_at` on all mutable tables, stored in UTC (`timestamptz`); a custom column type guarantees timezone-aware values on every database.

**Waitlist model.** A waitlisted registration has status `waitlisted` *and* a `waitlist_entries` row; its position is `created_at` order (FIFO). Seats taken = registrations in `pending, confirmed, attended, no_show`.
