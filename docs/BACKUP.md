# Backup and recovery

All application data (users, search history, saved leads, audit events) lives in PostgreSQL,
in the `postgres_data` Docker volume. Backups contain business contact details and password
hashes: store them encrypted and restrict who can read them.

Commands below assume the production alias from docs/DEPLOYMENT.md:

```bash
alias dcp='docker compose -f docker-compose.yml -f docker-compose.prod.yml'
```

(In development, use plain `docker compose`.)

## Manual backup

```bash
./scripts/backup-db.sh
```

This writes a compressed, PostgreSQL custom-format dump to `backups/icp-lead-finder-<timestamp>.dump`
(the `backups/` folder is git-ignored) and deletes local dumps older than 14 days. It is equivalent to:

```bash
mkdir -p backups
dcp exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
  > "backups/icp-lead-finder-$(date +%Y%m%d-%H%M%S).dump"
```

## Scheduled backups

Run a nightly backup at 02:15 with cron (`crontab -e` on the server):

```cron
15 2 * * * cd /opt/icp-lead-finder && COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml" ./scripts/backup-db.sh >> backups/backup.log 2>&1
```

## Off-server copies

A backup on the same VM does not protect against losing the VM. Copy dumps elsewhere, for example:

- DigitalOcean Spaces or another S3-compatible bucket (with `s3cmd`/`rclone`), with access restricted
  and server-side encryption enabled; or
- `scp`/`rsync` to another machine you control.

Encrypt before copying if the destination is not already encrypted, e.g.
`gpg --symmetric --cipher-algo AES256 backups/<file>.dump`.

Also enable **DigitalOcean droplet backups or snapshots** as an extra layer (they capture the whole VM).

Keep a copy of `.env` (in a password manager), since it contains the database password.

## Restore

1. Stop the services that write to the database:

   ```bash
   dcp stop backend frontend
   ```

2. Restore the dump (this replaces existing tables):

   ```bash
   dcp exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' \
     < backups/<file>.dump
   ```

3. Start the services again (migrations run automatically if the code is newer than the backup):

   ```bash
   dcp start backend frontend
   dcp ps
   ```

4. Sign in and spot-check saved leads and search history.

## Test your backups

At least monthly, restore the latest dump into a scratch database and check it:

```bash
dcp exec -T db sh -c 'createdb -U "$POSTGRES_USER" restore_check'
dcp exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d restore_check --no-owner' < backups/<file>.dump
dcp exec -T db sh -c 'psql -U "$POSTGRES_USER" -d restore_check -c "select count(*) from users; select count(*) from saved_leads;"'
dcp exec -T db sh -c 'dropdb -U "$POSTGRES_USER" restore_check'
```

## Data retention

- Search history stores only the search criteria, not the returned contact records.
- Saved leads are stored only when a team member explicitly saves them.
- Review your contact-data provider's terms for how long saved contact data may be retained, and
  delete saved leads that are no longer needed (Saved Leads → Remove).
