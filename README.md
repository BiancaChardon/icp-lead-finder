# ICP Lead Finder

Internal B2B prospecting tool for authorized team members. Define an ideal customer profile (ICP),
search for matching companies and decision-makers, review results, save leads, revisit past
searches, and export to CSV.

**Current data source: demonstration data only.** Searches use a clearly labeled mock provider
(every result shows a **DEMO** badge). No real contact-data provider is connected yet; see
[docs/PROVIDERS.md](docs/PROVIDERS.md).

| Service    | Tech                              | Local address                        |
|------------|-----------------------------------|--------------------------------------|
| `frontend` | Next.js 16, TypeScript            | http://localhost:3000                |
| `backend`  | FastAPI, SQLAlchemy 2, Alembic    | http://localhost:8000                |
| `db`       | PostgreSQL 17                     | not published (Docker network only)  |
| `caddy`    | Caddy 2 (production only)         | ports 80/443 on the server           |

## Features

- Optional team sign-in (`AUTH_REQUIRED`; off by default), no public registration, session cookies,
  CSRF protection, rate limiting.
- ICP search: industry, job titles, locations, company size, keywords, company name, provider filters.
- Contact search by full name, first name, last name, email, and phone. A full name in one field matches both name columns.
- Results table with pagination, sorting, selection, and clear verified / unverified / not-available labels.
- Save leads, view/remove saved leads, and search history with "Run again".
- Excel `.xlsx` import with preview, column mapping, duplicate detection, and an error CSV.
- CSV export of selected results or all saved leads, with spreadsheet formula-injection protection.
- Administrator user management in Settings; audit log of security and admin events.

## Prerequisites

- Docker with Docker Compose v2 (`docker compose version`)
- Git

Node and Python are **not** required on the host; everything builds and runs in containers.

## First-time setup

```bash
cp .env.example .env
sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 24)/" .env
docker compose up -d --build
```

If port 3000 or 8000 is already in use, start with `docker-compose.demo.yml` as well. See [DEMO-START.md](DEMO-START.md).

Open http://localhost:3000. Sign-in is **off by default** (`AUTH_REQUIRED=false`): the dashboard opens
directly and everyone shares one workspace (saved leads and search history).

To require sign-in, set `AUTH_REQUIRED=true` in `.env`, run `docker compose up -d`, and create an
administrator (you'll be prompted for a password of 12+ characters):

```bash
docker compose exec backend python -m app.cli create-admin --email you@yourcompany.com --name "Your Name"
```

Administrators add team members under **Settings → Team members**.

## Everyday commands

```bash
docker compose up -d --build     # build and start (migrations run automatically)
docker compose ps                # db, backend, frontend should show "(healthy)"
docker compose logs -f backend   # follow logs (or: frontend, db)
docker compose down              # stop (database data is kept)
```

`docker compose down -v` also **deletes the database volume**. Only use it to wipe local data on purpose.

## URLs to check

| URL                                  | Expected                                                 |
|--------------------------------------|----------------------------------------------------------|
| http://localhost:3000                | Dashboard (or the sign-in page if `AUTH_REQUIRED=true`)  |
| http://localhost:3000/api/health     | `{"status":"ok","service":"backend"}`                    |
| http://localhost:8000/health/ready   | `{"status":"ok","database":"ok"}`                        |
| http://localhost:8000/docs           | Interactive API docs (disabled in production)            |

## Tests

```bash
docker compose run --rm --build backend-test    # pytest against a separate *_test database
docker compose run --rm --build frontend-test   # TypeScript type-check + Vitest
```

Backend tests cover search validation, the mock provider, provider error handling, pagination and
result formatting, authentication and authorization, saved-lead access control, CSV export,
models and migrations, the admin CLI, and health checks.

## Database migrations

Migrations run automatically when the backend starts. Manual commands:

```bash
docker compose exec backend alembic upgrade head          # apply
docker compose exec backend alembic current               # show current revision
docker compose exec backend alembic downgrade -1          # roll back one step
```

After changing `backend/app/models.py`, generate a migration and review it before committing:

```bash
docker compose run --rm --no-deps --entrypoint alembic --user "$(id -u):$(id -g)" \
  -v "$PWD/backend/alembic/versions:/app/alembic/versions" \
  backend revision --autogenerate -m "describe the change"
```

## Configuration

All configuration comes from environment variables in `.env` (see `.env.example`):

| Variable                       | Purpose                                                                  |
|--------------------------------|--------------------------------------------------------------------------|
| `APP_ENV`                      | `development` or `production`                                            |
| `POSTGRES_DB` / `POSTGRES_USER`| Database name and user                                                   |
| `POSTGRES_PASSWORD`            | Database password (required)                                             |
| `CORS_ALLOWED_ORIGINS`         | Comma-separated trusted browser origins; also used for CSRF origin checks |
| `AUTH_REQUIRED`                | `false` (default) = no sign-in, shared workspace; `true` = team sign-in  |
| `COOKIE_SECURE`                | `true` in production (HTTPS-only cookies)                                |
| `SESSION_TTL_HOURS`            | Session lifetime (default 12)                                            |
| `CONTACT_PROVIDER`             | Empty = `mock` in development; must be set explicitly in production      |
| `LOGIN_RATE_LIMIT_PER_MINUTE`  | Per-account sign-in attempts per minute (default 5)                      |
| `SEARCH_RATE_LIMIT_PER_MINUTE` | Searches per user per minute (default 20)                                |
| `SITE_ADDRESS`                 | Production only: domain or public IP served by Caddy                     |

Production refuses to start with insecure or missing settings (wildcard or non-HTTPS origins,
`COOKIE_SECURE=false`, unset `CONTACT_PROVIDER`).

## Security notes

- **With `AUTH_REQUIRED=false` there is no access control:** anyone who can reach the site can run
  searches (and use provider credits once a real provider is connected) and view or export all saved
  leads. Untrusted-origin requests are still rejected and searches are rate-limited per client address.
- Passwords are hashed with Argon2id. Sessions are random tokens stored hashed in the database,
  sent as `HttpOnly`, `SameSite=Lax` cookies (`Secure` in production) and expire after `SESSION_TTL_HOURS`.
- State-changing requests require a CSRF token header and a trusted `Origin`.
- Every data endpoint checks the session server-side; users can only see their own saved leads and history.
- Provider credentials stay on the server; the frontend only calls this app's API.
- Health checks expose no configuration. Logs never include passwords, session tokens, or API keys.
- CSV exports prefix cells starting with `=`, `+`, `-`, `@`, tab, or carriage return with `'`, so
  phone numbers such as `+1 410-555-0100` appear as `'+1 410-555-0100` in the raw file.
- Rate limits are kept in memory per backend process (the default single-process setup).

## Documentation

- [DEMO-START.md](DEMO-START.md): local demo on ports 3012 and 8012
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md): local startup and DigitalOcean deployment with Caddy HTTPS
- [docs/ENVIRONMENT_CONFIGURATION.md](docs/ENVIRONMENT_CONFIGURATION.md): environment variables and sign-in readiness
- [docs/BACKUP_AND_RESTORE.md](docs/BACKUP_AND_RESTORE.md): backup, scratch restore, and live restore
- [docs/PROVIDERS.md](docs/PROVIDERS.md): provider interface and adding Apollo.io or others

## Repository layout

```text
backend/
  app/            FastAPI app: config, models, auth, providers/, routers/, CSV export, admin CLI
  alembic/        database migrations
  tests/          pytest suite
frontend/
  src/app/        Next.js pages: login, dashboard, history, saved leads, settings
  src/components/ UI components; src/lib/ API client, criteria parsing, types
deploy/Caddyfile  production reverse proxy and security headers
docs/             deployment, backup, provider guides
scripts/          backup-db.sh
docker-compose.yml        development stack (+ test runners)
docker-compose.prod.yml   production overrides (adds Caddy, removes host ports)
```

## Troubleshooting

- **`Set POSTGRES_PASSWORD in .env`**: you skipped the first-time setup step.
- **Port already in use**: something else is on 3000 or 8000. Stop it or change the host side of `ports:`.
- **"Origin not allowed" when signing in**: open the app at an address listed in `CORS_ALLOWED_ORIGINS`
  (by default `http://localhost:3000` or `http://127.0.0.1:3000`).
- **"Service unavailable" page**: run `docker compose ps` and `docker compose logs backend`.
- **WSL cannot reach GitHub or PyPI while a VPN is connected**: disconnect the VPN, or set
  `networkingMode=mirrored` under `[wsl2]` in `%UserProfile%\.wslconfig` and run `wsl --shutdown`.
