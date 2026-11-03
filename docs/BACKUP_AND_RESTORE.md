# Backup and restore

All application data lives in the PostgreSQL database `icp_lead_finder`, inside the Docker volume `postgres_data`. A dump contains saved prospects, search criteria, audit events, and password hashes. `backups/` is gitignored. Do not commit a dump.

The backup does not modify the live database. A test restore goes into a different database name. `pg_restore --clean` into `icp_lead_finder` replaces the live tables and is only for a planned recovery.

## Local commands

From `/home/rootx/projects/icp-lead-finder`. These commands use the running demo stack. They do not delete containers or the volume.

Start, check, and stop:

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d
docker compose -f docker-compose.yml -f docker-compose.demo.yml ps
docker compose -f docker-compose.yml -f docker-compose.demo.yml down
```

`down` keeps the volume. `down -v` deletes it.

Backup:

```bash
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.demo.yml" ./scripts/backup-db.sh
```

The script runs `pg_dump --format=custom` inside the `db` container, writes `backups/icp-lead-finder-<timestamp>.dump`, sets the file mode to `0600`, and deletes dumps older than 14 days (`RETENTION_DAYS`).

Confirm the dump lists the application tables:

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml exec -T db pg_restore -l \
  < backups/icp-lead-finder-<timestamp>.dump
```

Expect `TABLE DATA` entries for `users`, `auth_sessions`, `saved_leads`, `search_history`, and `audit_events`.

## Verified backup, 2026-11-02

| Item | Result |
| --- | --- |
| File | `backups/icp-lead-finder-20261102-215016.dump` |
| Size | 27,116 bytes |
| Saved leads | 63 |
| Breakdown | 50 `excel_import` / Excel import; 12 `excel_import` / Sample spreadsheet (fictional); 1 `mock` / Demo data |
| Search history | 7 |
| Audit events | 9 |
| Users | 1 (`workspace@icp-lead-finder.local`) |
| Sessions | 0 |
| Lead identity | `d970d52ea005441960656997c41b7e41` |

The identity is an MD5 of `id|provider|provider_record_id` for every saved lead, ordered by id. It matches the live database. The live row counts were the same after the restore.

## Restore test

This creates `icp_lead_finder_restore_check` and leaves `icp_lead_finder` untouched. The scratch database from the 2026-11-02 test is still present. Create it again only when that name does not already exist.

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml exec -T db \
  sh -c 'psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE icp_lead_finder_restore_check;"'

docker compose -f docker-compose.yml -f docker-compose.demo.yml exec -T db \
  sh -c 'pg_restore -U "$POSTGRES_USER" -d icp_lead_finder_restore_check --no-owner --no-acl --exit-on-error' \
  < backups/icp-lead-finder-<timestamp>.dump
```

Compare counts. Both queries should return 63 saved leads and the same identity hash.

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml exec -T db \
  sh -c 'psql -U "$POSTGRES_USER" -d icp_lead_finder -c "SELECT count(*) FROM saved_leads;"'

docker compose -f docker-compose.yml -f docker-compose.demo.yml exec -T db \
  sh -c 'psql -U "$POSTGRES_USER" -d icp_lead_finder_restore_check -c "SELECT count(*) FROM saved_leads;"'
```

Drop the scratch database only when you no longer need the test copy:

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml exec -T db \
  sh -c 'dropdb -U "$POSTGRES_USER" icp_lead_finder_restore_check'
```

Do not pass `icp_lead_finder` to `dropdb`. The test suite uses `icp_lead_finder_test` and may drop that database itself. Do not use it as the restore target.

## Production backup

On the server, after the production alias from [DEPLOYMENT.md](DEPLOYMENT.md):

```bash
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml" ./scripts/backup-db.sh
```

A nightly cron entry, once a server path exists:

```cron
15 2 * * * cd /opt/icp-lead-finder && COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml" ./scripts/backup-db.sh >> backups/backup.log 2>&1
```

No cron job is installed on the development machine. A copy of the dump has not been sent off this machine. Copy it to storage you control, and encrypt it when the destination is not already encrypted. Keep `.env` in a password manager. The dump cannot be used without `POSTGRES_PASSWORD`.

## Planned recovery of the live database

Use this only when the live database must be replaced. Take a fresh dump first. Stop the writers, restore that one database, then start the app again. On the local demo, substitute the two demo Compose files for `dcp` and do not publish any new port.

```bash
dcp stop backend frontend
dcp exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' \
  < backups/<file>.dump
dcp start backend frontend
dcp ps
```

Then confirm http://127.0.0.1:3012 still lists the saved leads. Migrations run on backend startup when the code is newer than the dump.
