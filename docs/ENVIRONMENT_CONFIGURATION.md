# Environment configuration

Settings come from the process environment. Docker Compose reads `.env` and passes the variables into the containers. The backend does not read `.env` itself (`env_file` is unset in application settings). `.env` is mode `0600`, listed in `.gitignore`, and was not changed in Phase 0.

`.env.example` is the committed template. It contains placeholders, not the local password.

## Current local values

| Variable | Local value | Effect |
| --- | --- | --- |
| `APP_ENV` | `development` | Demo provider is allowed. OpenAPI docs stay available on the backend port. |
| `POSTGRES_DB` | `icp_lead_finder` | Active database. Do not drop or recreate it. |
| `POSTGRES_USER` | `icp_app` | Database role inside the container. |
| `POSTGRES_PASSWORD` | set, 48 hex characters | Required. Not printed and not committed. |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3012`, `http://127.0.0.1:3012` | Browser origins allowed to call the API. Port 3000 is a different application. |
| `AUTH_REQUIRED` | `false` | Dashboard opens with no sign-in. See the authentication section before changing this. |
| `COOKIE_SECURE` | `false` | Correct for HTTP on localhost. Production refuses to start unless this is `true`. |
| `SESSION_TTL_HOURS` | `12` | Session lifetime when sign-in is on. |
| `CONTACT_PROVIDER` | empty | Development uses `mock`. Production requires an explicit value. |
| `LOGIN_RATE_LIMIT_PER_MINUTE` | `5` | Applies when sign-in is on. The limiter is in memory in one process. |
| `SEARCH_RATE_LIMIT_PER_MINUTE` | `20` | Search requests per client. |
| `SITE_ADDRESS` | unset | Used by the production Caddy overlay only. |

`APOLLO_API_KEY` is a commented placeholder. No provider key is configured. Setting `CONTACT_PROVIDER` to `apollo` or `hunter` makes the backend refuse to start, because those adapters are not implemented.

## Which Compose file to use

| Situation | Command files | Published ports |
| --- | --- | --- |
| This machine | `docker-compose.yml` and `docker-compose.demo.yml` | `127.0.0.1:3012` and `127.0.0.1:8012` |
| A clean machine | `docker-compose.yml` | `127.0.0.1:3000` and `127.0.0.1:8000` |
| Production | `docker-compose.yml` and `docker-compose.prod.yml` | Caddy `80` and `443` only |

PostgreSQL is never published to the host. Do not add a host port for it.

Local start, check, and stop:

```bash
cd /home/rootx/projects/icp-lead-finder
docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d
docker compose -f docker-compose.yml -f docker-compose.demo.yml ps
curl -s http://127.0.0.1:3012/api/health
curl -s http://127.0.0.1:8012/health/ready
docker compose -f docker-compose.yml -f docker-compose.demo.yml down
```

`down` without `-v` keeps the database. Backup commands are in [BACKUP_AND_RESTORE.md](BACKUP_AND_RESTORE.md).

## Authentication readiness

Sign-in code is implemented and is **left off**. Changing it now would hide the existing prospects.

What is running:

- `AUTH_REQUIRED=false`.
- The site is bound to `127.0.0.1`. It is not exposed on a public interface by the demo overlay.
- One user exists: `workspace@icp-lead-finder.local`, role `member`, active.
- That account's password is a random value hashed at creation. The plaintext was never stored, so the account cannot sign in.
- All 63 saved leads, the search history, and the audit events belong to that user. There are no sessions.
- Saved leads and history are filtered by the signed-in user. A different user sees a different list.

What the CLI can do, inside the backend container:

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml exec backend \
  python -m app.cli reset-password --email workspace@icp-lead-finder.local

docker compose -f docker-compose.yml -f docker-compose.demo.yml exec backend \
  python -m app.cli create-admin --email you@yourcompany.com --name "Your Name"
```

The password prompt accepts 12 to 128 characters and does not log the password. `reset-password` also deletes that user's sessions. `create-admin` refuses an email that already exists.

Those commands were not run. Either one changes the database, and neither one by itself makes the current demo safe to put on the internet:

- Resetting the shared account lets that same user sign in and see the 63 leads. The role stays `member`, so Settings does not gain team administration. There is no CLI command to change a role.
- Creating an administrator adds a second user. That administrator does not own the 63 leads and will see an empty saved-lead list.
- There is no command to move `saved_leads.user_id` from one user to another. Doing that is a data change and needs approval.

## Enabling sign-in later

Do this only after an approved choice about who should own the existing leads. Keep the demo on `127.0.0.1` while doing it.

1. Take a backup with the command in [BACKUP_AND_RESTORE.md](BACKUP_AND_RESTORE.md).
2. Either reset the shared user's password, or create an administrator and explicitly reassign the existing rows. Do not invent a third option during the restart.
3. Set `AUTH_REQUIRED=true` in `.env`. Leave `COOKIE_SECURE=false` while the site is HTTP on localhost. Leave the CORS origins on port 3012.
4. Recreate the backend process so it reads the new value: `docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d`. Do not add `-v` and do not change the published ports.
5. Sign in and confirm the saved-lead count is still 63 before anyone else uses the app.

Production additionally requires `APP_ENV=production`, `COOKIE_SECURE=true`, an `https://` origin, an explicit `CONTACT_PROVIDER`, and `SITE_ADDRESS`. Those checks do not force `AUTH_REQUIRED=true`. A public site with sign-in left off is an open workspace.

## Files that must stay uncommitted

- `.env`
- `backups/*.dump`
- the Docker volume `postgres_data`
