# API Reference

Interactive docs (OpenAPI/Swagger) are served by the backend at **`/docs`** (ReDoc at `/redoc`). A Postman collection is in `docs/EventHub.postman_collection.json`.

All endpoints except `register`, `login`, `refresh`, `logout`, `/api/health` need `Authorization: Bearer <access_token>`.

## Conventions

* Lists: `GET …?page=1&page_size=20&sort=-start_time` → `{ "items": [...], "total": 42, "page": 1, "page_size": 20, "pages": 3 }`
* Datetimes: ISO-8601; naive values are interpreted as UTC; responses are UTC.
* Errors (all handlers share one envelope):
```json
{ "success": false, "error": { "code": "RESOURCE_ALREADY_BOOKED", "message": "The selected resource is already booked for this time period." } }
```
`422 VALIDATION_ERROR` additionally carries `error.details: [{field, message}]`.

| HTTP | Typical codes |
|---|---|
| 400 | `LAST_ADMIN`, `FILE_CONTENT_MISMATCH`, `EMPTY_FILE`, `INVALID_ENTITY_TYPE` |
| 401 | `NOT_AUTHENTICATED`, `INVALID_TOKEN`, `TOKEN_EXPIRED`, `TOKEN_REUSED`, `INVALID_CREDENTIALS`, `ACCOUNT_INACTIVE` |
| 403 | `ORGANIZATION_ACCESS_DENIED`, `INSUFFICIENT_PERMISSIONS`, `EVENT_ACCESS_DENIED`, `FORBIDDEN` |
| 404 | `NOT_FOUND` |
| 409 | `EVENT_CAPACITY_EXCEEDED`, `DUPLICATE_REGISTRATION`, `RESOURCE_ALREADY_BOOKED`, `INVALID_EVENT_STATUS`, `SESSION_TIME_CONFLICT`, `SPEAKER_TIME_CONFLICT`, `REGISTRATION_CLOSED`, `EVENT_CANCELLED`, `INVALID_REGISTRATION_STATUS`, `INVALID_BOOKING_STATUS`, `RESOURCE_INACTIVE`, `EMAIL_TAKEN`, `USERNAME_TAKEN`, `ALREADY_MEMBER` |
| 413 / 415 | `FILE_TOO_LARGE`, `INVALID_MIME_TYPE`, `INVALID_FILE_EXTENSION` |
| 422 | `VALIDATION_ERROR`, `INVALID_EVENT_TIME`, `INVALID_SESSION_TIME`, `SESSION_OUTSIDE_EVENT`, `SESSION_CAPACITY_EXCEEDED`, `INVALID_BOOKING_TIME` |
| 500 | `INTERNAL_ERROR` |

## Endpoints

**Auth** — `POST /api/auth/register` · `login` · `refresh` · `logout` · `GET /api/auth/me` · `PATCH /api/auth/me` · `POST /api/auth/change-password`

**Organizations** — `POST/GET /api/organizations` · `GET/PATCH /api/organizations/{id}` · `GET/POST /{id}/members` · `PATCH /{id}/members/{mid}/role` · `POST /{id}/members/{mid}/activate|deactivate` · `DELETE /{id}/members/{mid}` · `GET /{id}/audit-logs`

**Events** — `POST/GET /api/events` (filters: `organization_id, status, organizer_id, location, date_from, date_to, search, sort`) · `GET/PATCH/DELETE /api/events/{id}` · `POST /{id}/publish|cancel|archive` · `POST /{id}/transition {status}`

**Registrations** — `POST /api/events/{id}/register` · `GET /api/events/{id}/registrations` (staff) · `GET /api/registrations` (filters: `organization_id, event_id, status, participant_id, date_from, date_to`) · `GET /api/registrations/{id}` · `POST /api/registrations/{id}/cancel|approve|reject`

**Resources** — `POST/GET /api/resources` · `GET/PATCH /api/resources/{id}` · `POST /{id}/activate|deactivate`

**Bookings** — `POST/GET /api/bookings` (filters: `resource_id, status, date_from, date_to, requested_by, event_id`) · `GET/PATCH /api/bookings/{id}` · `POST /{id}/cancel|approve|reject`

**Sessions** — `POST/GET /api/events/{id}/sessions` · `GET/PATCH/DELETE /api/sessions/{id}`
**Speakers** — `POST/GET /api/speakers` · `GET/PATCH/DELETE /api/speakers/{id}`

**Attendance** — `POST/GET /api/events/{id}/attendance` · `PATCH /api/attendance/{id}` · `GET /api/events/{id}/attendance-report` (CSV)

**Files** — `POST /api/events/{id}/attachments` (multipart: `file`, `entity_type` = event|session|speaker|registration, `entity_id`) · `GET /api/events/{id}/attachments` · `GET /api/attachments/{id}/download` · `DELETE /api/attachments/{id}`

**Comments** — `POST /api/comments` · `GET /api/comments?event_id=&session_id=` · `PATCH/DELETE /api/comments/{id}` (own only; `@username` mentions notify)

**Notifications** — `GET /api/notifications` · `GET /unread-count` · `PATCH /{id}/read` · `PATCH /read-all`

**Dashboard / Calendar** — `GET /api/dashboard?organization_id=` (shape depends on your role) · `GET /api/calendar?organization_id=&start=&end=`

**WebSocket** — `ws://host/ws?token=<access_token>`

## Permission matrix (per organization)

| Action | Participant | Staff | Event manager | Org admin |
|---|:-:|:-:|:-:|:-:|
| View published events, schedule, own registrations | ✓ | ✓ | ✓ | ✓ |
| Register / cancel own registration | ✓ | ✓ | ✓ | ✓ |
| View drafts, all registrations, attendance, bookings | | ✓ | ✓ | ✓ |
| Approve/reject registrations, record attendance | | ✓ | ✓ | ✓ |
| Create events, sessions, speakers, bookings | | | ✓ | ✓ |
| Edit/publish/cancel an event | | | own events | all |
| Create/edit resources, approve bookings, manage members, audit log | | | | ✓ |
