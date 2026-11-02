# ICP Lead Finder

B2B prospecting web app for authorized team members: define an ideal customer profile (ICP),
search for matching companies and decision-makers, save leads, and export to CSV.

**Status: Milestone 1 (skeleton).** The stack runs, but there is no search, login, or database
schema yet. Do not expose this to the internet.

| Service    | Tech                         | Local address                      |
|------------|------------------------------|------------------------------------|
| `frontend` | Next.js 16, TypeScript       | http://localhost:3000              |
| `backend`  | FastAPI (Python 3.12)        | http://localhost:8000              |
| `db`       | PostgreSQL 17                | not published (Docker network only)|

Both published ports are bound to `127.0.0.1`, so they are reachable only from this machine.
The frontend forwards `/api/*` to the backend, so the browser only ever talks to one origin.
The frontend container has no network route to the database.

## Prerequisites

- Docker with Docker Compose v2 (`docker compose version`)
- Git

Node and Python are **not** required on the host; everything builds inside containers.

## First-time setup

```bash
cp .env.example .env
# Replace the placeholder database password with a random one:
sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 24)/" .env
```

`.env` is git-ignored. Never commit it.

## Start / stop

```bash
docker compose up -d --build     # build and start all three services
docker compose ps                # all three should show "(healthy)"
docker compose logs -f backend   # follow logs (or: frontend, db)
docker compose down              # stop (database data is kept)
```

`docker compose down -v` also **deletes the database volume**. Only use it when you
intentionally want to wipe local data.

## URLs to check

| URL                                  | Expected                                        |
|--------------------------------------|-------------------------------------------------|
| http://localhost:3000                | Dashboard; "Backend API: Connected and healthy" |
| http://localhost:3000/api/health     | `{"status":"ok","service":"backend"}` (via proxy)|
| http://localhost:8000/health         | `{"status":"ok","service":"backend"}`           |
| http://localhost:8000/docs           | Interactive API docs (disabled when `APP_ENV=production`) |

Database check:

```bash
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select version();"'
```

## Tests

Backend (pytest, runs in a container):

```bash
docker build --target test -t icp-lead-finder-backend-test ./backend
docker run --rm icp-lead-finder-backend-test
```

Frontend type-checking runs automatically during `docker compose build`.

## Repository layout

```text
backend/    FastAPI app (app/), tests (tests/), Dockerfile with `test` and `runtime` targets
frontend/   Next.js App Router app (src/app/), standalone production Dockerfile
docker-compose.yml
.env.example
```

## Configuration

All configuration comes from environment variables (see `.env.example`):

| Variable               | Purpose                                                        |
|------------------------|----------------------------------------------------------------|
| `APP_ENV`              | `development` or `production` (production disables API docs)   |
| `POSTGRES_DB`          | Database name                                                  |
| `POSTGRES_USER`        | Database user                                                  |
| `POSTGRES_PASSWORD`    | Database password (required; Compose refuses to start without it) |
| `CORS_ALLOWED_ORIGINS` | Comma-separated allowed origins; `*` is rejected in production |

## Troubleshooting

- **`Set POSTGRES_PASSWORD in .env`**: you skipped the first-time setup step.
- **Port already in use**: something else is on 3000 or 8000. Stop it, or change the left-hand
  side of the `ports:` mapping in `docker-compose.yml`.
- **Dashboard shows "Backend is unreachable"**: run `docker compose ps` and
  `docker compose logs backend`.
