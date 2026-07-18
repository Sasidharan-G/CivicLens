# CivicLens operations runbook

## Environments

Use separate Render services and databases for staging and production. Staging deploys from `develop`; production deploys from `main`. Never copy production secrets into staging. Set `ENVIRONMENT`, `DATABASE_URL`, `JWT_SECRET_KEY`, `CORS_ORIGINS`, `APP_BASE_URL`, Cloudinary credentials, email credentials, `SENTRY_DSN`, and `INTERNAL_JOBS_SECRET` independently.

Before promotion, run backend tests, frontend unit/E2E tests, `alembic upgrade head`, a database backup, and the k6 smoke profile against staging. Production health is `/api/health`; a healthy response must report `database: connected`.

`/api/ready` is the deployment readiness gate. In production it returns HTTP 503 until PostgreSQL, secure JWT/CORS/base URL settings, Cloudinary, SMTP, and the internal jobs secret are configured. After deployment run `API_BASE_URL=https://api.example.com python scripts/release-smoke.py`. Demo seeding is intentionally not part of the production start command; seed only an explicitly disposable demo or staging database.

## PostgreSQL backup

Render-managed backups should be enabled according to the selected database plan. Before a migration or release, also create an encrypted logical backup from a trusted operator machine:

```bash
pg_dump --format=custom --no-owner --no-acl "$DATABASE_URL" --file "civiclens-$(date +%Y%m%d-%H%M%S).dump"
pg_restore --list civiclens-YYYYMMDD-HHMMSS.dump
```

Store backups in a private, encrypted bucket with retention of 7 daily, 4 weekly, and 12 monthly copies. Never commit dumps to Git or place them in a public upload bucket.

## Recovery drill

1. Create an empty recovery database in an isolated environment.
2. Restore with `pg_restore --clean --if-exists --no-owner --no-acl --dbname "$RECOVERY_DATABASE_URL" backup.dump`.
3. Point a temporary backend at the recovery database and run `alembic current`.
4. Check `/api/health`, authentication, complaint counts, media links, and a sample complaint timeline.
5. Record restore duration and data timestamp. Target RPO is 24 hours and initial RTO is 4 hours.
6. Delete the temporary recovery environment after sign-off. Run this drill quarterly.

## Monitoring and alerts

GitHub Actions calls production `/api/ready` every 15 minutes. Configure repository variable `PRODUCTION_HEALTH_URL` with the full readiness URL. Workflow failures create a visible Actions alert; production should additionally use Render health checks and Sentry error alerts. Alert after two consecutive failures, confirm database connectivity, inspect Render logs and Sentry, and post incident updates without exposing citizen data.

## Load test

Run only against local or staging systems unless a production test window is approved:

```bash
k6 run -e BASE_URL=https://staging-api.example.com -e VUS=25 -e DURATION=2m load/k6-smoke.js
```

The profile fails above 1% request errors, below 99% checks, or when p95 latency exceeds 750 ms.
