# CivicLens

CivicLens is an AI-assisted civic issue reporting and tracking platform. A citizen can turn a photo and map location into a structured complaint, detect nearby duplicates, generate a professional letter, gather community support, and follow authority updates through a transparent timeline.

> All seeded complaints and landing-page impact numbers are demo data; they do not represent real Chennai complaints.

## Why CivicLens

Civic complaints are often incomplete, duplicated, sent to the wrong department, or impossible to track. CivicLens creates consistently structured reports and gives citizens, communities, and authorities one shared view of progress.

## Features

- Citizen registration, JWT login, demo quick-login, and role-based access
- Safe JPEG/PNG/WebP upload with an OpenAI-compatible vision provider and deterministic offline fallback
- Seven-step reporting wizard with editable AI output, browser geolocation, draggable Leaflet map pin, duplicate check, complaint letter, and review
- Deterministic similarity scoring using distance, category, text overlap, and recency
- Human-readable `CIV-YYYY-000001` references
- Public issue map, complaint details, timeline, comments, and one-support-per-user enforcement
- Citizen dashboard and authority queue with status management
- Public and admin analytics with clearly labelled demo data
- Responsive light/dark civic-tech UI
- Up to five sanitized issue photos, before/after resolution evidence, and public identity/location privacy controls
- Tamil/English UI foundation and browser Tamil/English voice dictation
- Category-aware reporting questions and safety guidance
- Installable PWA shell with offline navigation fallback and connection-aware reporting
- Controlled authority status transitions, officer/department assignment, SLA deadlines and overdue queues
- Bulk authority operations, private internal notes, resolution summary/evidence gates, and citizen resolution confirmation/reopen
- Rotating refresh sessions, email verification and password-reset token flows
- Cloudinary/local storage adapter, cached reverse geocoding, audit trail, rate limiting and security headers
- Optional Sentry monitoring and GitHub Actions CI
- Idempotent Chennai demo seed, Alembic migration, Docker Compose, Render and Vercel configuration

## Architecture

`React/Vite → FastAPI REST API → SQLAlchemy → PostgreSQL (SQLite local fallback)`

Images use local storage in development. The AI service is isolated behind `AIProvider`; no key is ever sent to the browser. OpenStreetMap/Leaflet provides maps without a paid map key.

## Stack

React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, React Router, Framer Motion, Leaflet, Recharts, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, JWT, pytest, Docker.

## Quick start without Docker

Prerequisites: Python 3.11+ and Node 20+.

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env  # use `cp` on macOS/Linux
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```

In a second terminal:

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- OpenAPI: http://localhost:8000/docs
- Health: http://localhost:8000/api/health

## Docker

```bash
docker compose up --build
```

This starts PostgreSQL, migrates and seeds the API, and starts the Vite frontend at the URLs above. Volumes preserve database records and uploads.

## Demo accounts

| Role | Email | Password |
|---|---|---|
| Citizen | `citizen@civiclens.demo` | `Citizen@123` |
| Authority/Admin | `admin@civiclens.demo` | `Admin@123` |
| Citizen 2 | `meena@civiclens.demo` | `Citizen@123` |

These credentials are development seed data only.

## Environment variables

Backend: `DATABASE_URL`, `JWT_SECRET_KEY`, `JWT_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `CORS_ORIGINS`, `APP_BASE_URL`, `AI_API_KEY`, `AI_BASE_URL`, `AI_MODEL`, `AI_VISION_MODEL`, `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`, `SENTRY_DSN`, `GEOCODING_ENABLED`, `GEOCODING_USER_AGENT`, `SIMILARITY_RADIUS_M`, and `SIMILARITY_THRESHOLD`.

Frontend: `VITE_API_BASE_URL`. Never put an AI, database, JWT, or Cloudinary secret in a `VITE_` variable.

Without `AI_API_KEY`, image analysis is deterministically inferred from the filename and labelled “Demo AI analysis”; letter generation uses a complete local template. Without Cloudinary credentials, the same storage interface safely uses local uploads. Development password-reset and verification responses expose one-time tokens for local testing; production responses never expose them and should be connected to an email worker.

## Database and seed

```bash
cd backend
alembic upgrade head
python -m app.seed
```

The seed is idempotent and creates 3 users, 20 complaints around Chennai, status events, comments, and clustered coordinates. Run all migrations through `0004` before starting the current application.

## Tests and quality checks

```bash
cd backend && pytest -q
cd frontend && npm run build
cd frontend && npm run lint
```

Backend tests cover health, registration/login, protected routes, complaint creation, similarity, support uniqueness, citizen/admin authorization, status transitions, and offline letter generation.

## API

Interactive OpenAPI documentation is available at `/docs`. API groups include `/api/auth`, `/api/complaints`, `/api/admin`, `/api/public`, and `/api/health`. Complaint listing supports pagination, search, status, category, severity, and ownership filters.

## Deployment

### Render backend

1. Create a Render Blueprint using `render.yaml`, or create a Python web service with root directory `backend`.
2. Build: `pip install -r requirements.txt`.
3. Start: `alembic upgrade head && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
4. Attach PostgreSQL and set `DATABASE_URL`, `JWT_SECRET_KEY`, `CORS_ORIGINS` (your Vercel URL), and optional AI/Cloudinary values.
5. Confirm `/api/health` and `/docs`.

### Vercel frontend

1. Import the repository and set root directory to `frontend`.
2. Framework preset: Vite; build command: `npm run build`; output: `dist`.
3. Set `VITE_API_BASE_URL` to the Render backend origin (without a trailing slash).
4. Deploy. `vercel.json` provides SPA route fallback.

## Screenshots

Add portfolio screenshots here after deployment: landing page, report wizard, public map, complaint timeline, citizen dashboard, and authority analytics.

## Known limitations

- Reverse geocoding uses OpenStreetMap Nominatim with a persistent rounded-coordinate cache and coordinate fallback. Production deployments must set a valid identifying user-agent and respect Nominatim usage policy.
- MVP clustering uses numeric latitude/longitude rather than PostGIS and scans open records; add a geospatial index for city-scale workloads.
- Voice dictation depends on browser Web Speech support; unsupported browsers retain normal text input.
- PWA offline mode caches the application shell and preserves the current in-memory form, but queued offline complaint submission is not enabled yet.
- Outbound email delivery uses FastAPI background tasks for the current scale; move to a durable Redis-backed worker before high-volume production use.
- Notification records are modelled, but outbound email/push delivery is not enabled.

## Roadmap

- Tamil voice complaints and full multilingual support
- WhatsApp reporting integration
- Ward-wise civic score and authority escalation
- SLA reminders and government portal integration
- Native mobile application

## Security notes

Passwords are bcrypt-hashed, JWTs expire, admin and ownership checks are enforced server-side, ORM queries are used, CORS is configurable, uploads are type/size restricted, and secrets are excluded by `.gitignore`. Use a long random production JWT secret and HTTPS.

Testing, backup/recovery, load testing, environment promotion, and uptime procedures are documented in [`docs/operations.md`](docs/operations.md).
