# Deployment

ICP Lead Finder runs as Docker Compose services. This guide is hosting-platform neutral.
No cloud provider, Kubernetes cluster, or platform-as-a-service target has been verified
for this backup. Use the Compose files in this repository.

The mock provider returns fictional demonstration prospects. It does not return verified
real leads. Apollo.io and Hunter.io are not implemented. Setting `CONTACT_PROVIDER` to
either name makes the backend refuse to start.

## Prerequisites

- Docker Engine with Docker Compose v2
- Git
- A copy of `.env` created from `.env.example`

Node.js and Python are not required on the host. Images install their own toolchains.

## Environment

```bash
cp .env.example .env
chmod 600 .env
```

Replace `POSTGRES_PASSWORD` with a long random value, for example the output of
`openssl rand -hex 24`. Use letters and digits only. Never commit `.env`.

The variables are documented in `.env.example` and
[docs/ENVIRONMENT_CONFIGURATION.md](docs/ENVIRONMENT_CONFIGURATION.md). Compose reads `.env`
and passes values into the containers. The backend does not load `.env` by itself.

For the local demo overlay, set:

```ini
APP_ENV=development
AUTH_REQUIRED=false
COOKIE_SECURE=false
CONTACT_PROVIDER=
CORS_ALLOWED_ORIGINS=http://localhost:3012,http://127.0.0.1:3012
```

Leave `CONTACT_PROVIDER` empty in development. That selects the mock provider.

## Choose a Compose file

| Situation | Command | Published ports |
| --- | --- | --- |
| Clean machine | `docker compose up -d --build` | Frontend `127.0.0.1:3000`, backend `127.0.0.1:8000` |
| Local demo, when 3000 and 8000 are already used | `docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d --build` | Frontend `127.0.0.1:3012`, backend `127.0.0.1:8012` |
| Production-style overlay | `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build` | Caddy `80` and `443` only |

PostgreSQL 17 is stored in the Docker volume `postgres_data`. It is not published to the
host in any of these files. Do not add a host port for it.

The production overlay removes the frontend and backend host ports and adds Caddy
(`deploy/Caddyfile`). It requires `APP_ENV=production`, `COOKIE_SECURE=true`, an `https://`
value in `CORS_ALLOWED_ORIGINS`, an explicit `CONTACT_PROVIDER` (use `mock` until a real
provider exists), and `SITE_ADDRESS`. That overlay has not been deployed to a public host
as part of this backup.

## Local demo

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.demo.yml ps
```

`db`, `backend`, and `frontend` should become `healthy`.

| Check | URL or command | Expected |
| --- | --- | --- |
| Dashboard | http://127.0.0.1:3012 | Search form, no sign-in page |
| Frontend health | http://127.0.0.1:3012/api/health | `{"status":"ok","service":"backend"}` |
| Database health | http://127.0.0.1:8012/health/ready | `{"status":"ok","database":"ok"}` |
| API docs | http://127.0.0.1:8012/docs | Swagger UI |

Authentication is off for this demo. Anyone who can open the site can search, import,
export, and delete saved leads. Keep the demo bound to `127.0.0.1`.

Stop without deleting saved leads:

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml down
```

Do not add `-v`. That deletes the `postgres_data` volume.

## Database and migrations

The first backend start creates the volume and applies Alembic migrations
(`RUN_MIGRATIONS_ON_START=true`). The only committed revision is
`backend/alembic/versions/0001_initial_schema.py`.

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml exec backend alembic current
docker compose -f docker-compose.yml -f docker-compose.demo.yml exec backend alembic upgrade head
```

Backup and restore commands are in [docs/BACKUP_AND_RESTORE.md](docs/BACKUP_AND_RESTORE.md).
Database dumps contain saved leads and are not part of the Git backup.

## Tests

```bash
docker compose run --rm --build backend-test
docker compose run --rm --build frontend-test
```

`backend-test` uses a separate database named `${POSTGRES_DB}_test`. `frontend-test` runs
the TypeScript check and Vitest. The frontend production image runs `npm run typecheck`
and `npm run build` while it builds (`docker compose build frontend`).

## Production considerations

- Put a real password in `POSTGRES_PASSWORD` and keep a copy with the backups. Without it,
  a dump cannot be restored.
- Turn on `AUTH_REQUIRED` or restrict the network before the site is reachable beyond
  localhost. Read [docs/ENVIRONMENT_CONFIGURATION.md](docs/ENVIRONMENT_CONFIGURATION.md)
  before changing that flag on a database that already has leads. Existing rows belong to
  the user who saved them.
- Set `COOKIE_SECURE=true` only behind HTTPS. The production Compose file forces it.
- Leave PostgreSQL unpublished. Publish only the reverse proxy.
- Rate limits are stored in memory in one backend process.
- Interactive API docs are disabled when `APP_ENV=production`.
- `docker compose down -v` deletes the database volume. Do not use it on a database you
  need to keep.
