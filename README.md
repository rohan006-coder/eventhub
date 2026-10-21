# EventHub — Collaborative Event & Resource Booking Platform

Full-stack platform for organizations to run events, manage registrations (with capacity + automatic waitlist), schedule sessions and speakers, and book rooms/equipment without double-booking.

**Stack:** React 18 (Vite, React Router, Axios, Context API) · FastAPI · SQLAlchemy 2 · PostgreSQL · Alembic · Pydantic v2 · JWT · WebSockets · Docker Compose

## Quick start (Docker)

```bash
cp .env.example .env          # set SECRET_KEY (and optionally SUPERADMIN_*)
docker compose up --build
```

* Frontend: http://localhost:8080  ·  API: http://localhost:8000  ·  Swagger: http://localhost:8000/docs
* Migrations run automatically (`alembic upgrade head`) when the backend container starts.

## Local development

**Backend** (Python 3.11+, PostgreSQL running locally)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then export the variables, or: export DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/eventhub
createdb eventhub
alembic upgrade head
uvicorn app.main:app --reload
```
**Frontend** (Node 18+)
```bash
cd frontend
npm install
VITE_API_URL=http://localhost:8000 npm run dev    # http://localhost:5173
```

**Tests** (SQLite, no database setup needed)
```bash
cd backend && pytest
```

## First steps in the UI

1. Register an account → you land on *Organizations* → **New organization** (you become its admin).
2. Register more accounts, then **Members → Add member** by email and choose their role.
3. As event manager/admin: **Events → New event → Publish**. Add **Sessions**, **Resources**, **Bookings**.
4. As a participant: open a published event → **Register** (or **Join the waitlist** when full).

## What's implemented

| Area | Highlights |
|---|---|
| Auth | register/login/refresh/logout/me/change-password, scrypt hashing, access + refresh JWT, **refresh rotation with reuse detection**, inactive users blocked everywhere |
| Authorization | 5 roles, enforced in the backend at organization, role and object level (see `docs/ARCHITECTURE.md`) |
| Organizations | CRUD, member add/remove/role/activate/deactivate, "last admin" protection, audit log |
| Events | full lifecycle with a validated status machine, delete only draft/cancelled, server-side search/filter/sort/pagination |
| Registrations | duplicate prevention, deadline, capacity, optional approval, **FIFO waitlist with automatic promotion**, concurrency-safe |
| Resources & bookings | overlap detection (app lock **and** PostgreSQL exclusion constraint), approval flow, reschedule re-validation, auto-completion |
| Sessions & speakers | within-event, room clash, speaker clash, room capacity checks; participant notifications on change |
| Attendance | check-in/no-show, syncs registration status, CSV report, live updates |
| Files | extension + MIME + **magic-byte content** validation, size cap, random storage names, access-controlled download |
| Comments | threads on events and sessions, own-edit/delete, `@username` mentions → notifications (members only) |
| Notifications | all 11 required types (+ new-registration for staff), REST + WebSocket push |
| Dashboards | role-specific stats, tables, bar charts |
| Calendar | month / week / day views of events, sessions and bookings; click to open |
| UI | protected routes, role-based navigation/actions, loading/empty/error states, form validation, responsive layout, dark mode |

## Project layout

```
backend/app/{api,services,repositories,models,schemas,core}   routes → services → repositories → models
backend/alembic/                                              migrations
backend/tests/                                                pytest suite
frontend/src/{pages,panels.jsx,ui.jsx,auth.jsx,api.js}
docs/                                                         ER diagram, architecture, API reference, Postman collection
```

## Documentation

* `docs/ER_DIAGRAM.md` – ER diagram + database design explanation
* `docs/ARCHITECTURE.md` – architecture diagram, layering, authorization, concurrency, real-time
* `docs/API.md` – conventions, error codes, endpoint list, permission matrix
* `docs/EventHub.postman_collection.json` – 70+ requests; Login stores the tokens automatically
* `/docs` on the running backend – Swagger UI

## Test coverage

`backend/tests` covers: registration/login/invalid credentials/expired token/refresh rotation & reuse/logout/inactive user/password change; role permissions, organization isolation, event-level and resource-level authorization; event CRUD, status transitions, capacity, cancellation; duplicate registration, capacity limit, waitlist, cancellation, automatic promotion, approval flow, **concurrent registrations**; booking creation/approval/cancellation, overlap prevention (partial, containing, contained, adjacent), **concurrent bookings**; sessions (timing, room conflict, speaker conflict, capacity, cancelled event); files (valid, bad MIME, bad extension, forged content, oversized); notifications (creation, mark read, mentions, reminders); attendance, comments, dashboards, calendar, error envelope, audit log.

## Design decisions & known limits

* **Tests run on SQLite**, production targets PostgreSQL. The application code is dialect-neutral; the PostgreSQL-only extras (advisory locks, exclusion constraints) are applied through `locked()` / migration `0001`. Run the suite once against Postgres (`DATABASE_URL=postgresql+psycopg2://… pytest`) before relying on the concurrency guarantees.
* Migration `0001` builds the schema from the model metadata (baseline); evolve with `alembic revision --autogenerate`.
* Registration requires org membership (admins add members by email) — a deliberate tenant-isolation choice. Open self-join / invitations would be a natural extension.
* Email delivery is a logging stub (`services/notifications.send_email`); the WebSocket manager and scheduler are in-process (single worker). Redis pub/sub + Celery beat are the scale-out path.
* Sessions do not auto-create resource bookings for their room; the two schedules are checked independently.
* Uploaded files are stored on local disk (`UPLOAD_DIR`); use object storage for multi-node deployments.
* Not included from the optional list: Redis caching, rate limiting, QR check-in, drag-and-drop calendar.
