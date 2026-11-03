# Deploying ICP Lead Finder

The current handoff guide is [../DEPLOYMENT.md](../DEPLOYMENT.md). It stays with Docker Compose
and does not treat any hosting company as a verified target.

The DigitalOcean section below is an example that was not executed for this backup. Do not treat
it as a completed or verified deployment.

This file also covers the local demo. Replace every `<placeholder>`.
The contact provider remains the built-in mock provider. Apollo.io and Hunter.io are not connected.

Production refuses to start unless the site address, allowed origin, database
password, and contact-data provider are all set explicitly.

## Local demo

On a machine where ports 3000 and 8000 are already used, start with both Compose files.
The overlay binds the app to localhost only: frontend `127.0.0.1:3012`, backend `127.0.0.1:8012`.
PostgreSQL is not published.

```bash
cd /home/rootx/projects/icp-lead-finder
docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d
docker compose -f docker-compose.yml -f docker-compose.demo.yml ps
```

`db`, `backend`, and `frontend` should be `healthy`.

| Check | Command or URL |
| --- | --- |
| Dashboard | http://127.0.0.1:3012 |
| API health | `curl -s http://127.0.0.1:3012/api/health` |
| Database health | `curl -s http://127.0.0.1:8012/health/ready` |

Stop without deleting saved leads:

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml down
```

Do not add `-v`. That deletes the `postgres_data` volume. Rebuild with `up -d --build` only when the image is missing or the code changed.

Sign-in stays off for this demo. The reason, and the recovery steps required before `AUTH_REQUIRED=true`, are in [ENVIRONMENT_CONFIGURATION.md](ENVIRONMENT_CONFIGURATION.md). Backup and restore commands are in [BACKUP_AND_RESTORE.md](BACKUP_AND_RESTORE.md).

## Production: DigitalOcean Ubuntu VM

### 1. Before you start

- **VM size:** at least 2 GB RAM (the frontend build needs it). On a 1 GB droplet, add swap
  first (`sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile`).
- **Ubuntu** 22.04 or 24.04 LTS.
- **Domain (recommended):** create a DNS `A` record such as `leads.yourcompany.com` pointing at the VM's
  public IP. Caddy then obtains a publicly trusted certificate automatically.
  With only a bare IP address, browsers may show a certificate warning unless a trusted certificate can
  be issued for that IP; use a domain for team-facing access.
- **Existing apps on the VM (e.g. AURA):** check that nothing else is already using ports 80/443:

  ```bash
  sudo ss -ltnp '( sport = :80 or sport = :443 )'
  ```

  If another web server (such as nginx) owns those ports, either move that app behind this Caddy instance,
  or keep the existing server and point it at this app instead of running the `caddy` service. Do not stop
  existing services without planning for it.

### 2. Install Docker

Follow Docker's official instructions for Ubuntu ("Install using the apt repository"):
https://docs.docker.com/engine/install/ubuntu/ — then confirm:

```bash
docker --version
docker compose version
```

### 3. Firewall

Use a **DigitalOcean Cloud Firewall** (Networking → Firewalls) attached to the droplet:

| Port | Source | Purpose |
|------|--------|---------|
| 22/tcp | your office/home IP if possible | SSH |
| 80/tcp | all | HTTP → HTTPS redirect and certificate issuance |
| 443/tcp, 443/udp | all | HTTPS |

Note: ports published by Docker bypass `ufw` rules on the host, so rely on the cloud firewall and on
publishing only what is needed. This stack publishes only Caddy's 80/443; PostgreSQL, the backend,
and the frontend are never published in production.

### 4. Get the code

```bash
sudo mkdir -p /opt/icp-lead-finder && sudo chown "$USER" /opt/icp-lead-finder
git clone https://github.com/<owner>/icp-lead-finder.git /opt/icp-lead-finder
cd /opt/icp-lead-finder
```

For a private repository, use a read-only deploy key or a fine-grained access token.

### 5. Configure production secrets

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

Set at least:

```ini
APP_ENV=production
POSTGRES_PASSWORD=<output of: openssl rand -hex 24>
SITE_ADDRESS=<leads.yourcompany.com or the public IP>
CORS_ALLOWED_ORIGINS=https://<same value as SITE_ADDRESS>
COOKIE_SECURE=true
CONTACT_PROVIDER=mock        # "mock" = clearly labeled demo data until a real provider is implemented
```

Never commit `.env`. Keep a copy of it in your password manager: without `POSTGRES_PASSWORD` you
cannot use your database backups.

### 6. Start

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

All services should become `healthy` (Caddy has no health check). Database migrations run
automatically when the backend starts (`RUN_MIGRATIONS_ON_START=true`). To run them manually:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend alembic upgrade head
```

Tip: create an alias so you don't have to type both files:

```bash
echo "alias dcp='docker compose -f docker-compose.yml -f docker-compose.prod.yml'" >> ~/.bashrc && source ~/.bashrc
```

### 7. Sign-in (optional)

Sign-in is **off by default** (`AUTH_REQUIRED=false`). In that mode anyone who can reach the server's
address can search, view and export all saved leads, and (once a real provider is connected) spend
provider credits. A public production site needs either a firewall limited to the team's IP addresses
or `AUTH_REQUIRED=true`.

Do not flip that setting on a database that already has leads until you have read
[ENVIRONMENT_CONFIGURATION.md](ENVIRONMENT_CONFIGURATION.md). Existing leads belong to the user who
saved them. On the local demo that user is `workspace@icp-lead-finder.local`, and its password was
never stored. A newly created administrator is a different user and does not see those leads.

With sign-in on there is no public sign-up. On a new production database, create the first administrator on the server:

```bash
dcp exec backend python -m app.cli create-admin --email <you@yourcompany.com> --name "<Your Name>"
```

You'll be prompted for a password (12+ characters; it is never shown or logged). The administrator then
adds team members under **Settings → Team members**.

Forgotten administrator password:

```bash
dcp exec backend python -m app.cli reset-password --email <you@yourcompany.com>
```

### 8. Verify

- Open `https://<SITE_ADDRESS>` → the dashboard opens (or the sign-in page if `AUTH_REQUIRED=true`).
- `curl -s https://<SITE_ADDRESS>/api/health` → `{"status":"ok","service":"backend"}`
- Sign in, run a search, and confirm results are marked **DEMO** while `CONTACT_PROVIDER=mock`.
- `dcp logs caddy` shows the certificate was obtained.

### 9. Updating

```bash
cd /opt/icp-lead-finder
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml" ./scripts/backup-db.sh   # see docs/BACKUP_AND_RESTORE.md
git pull
dcp up -d --build
dcp ps
```

### 10. Operations

```bash
dcp logs -f backend          # application logs (no passwords, tokens, or API keys are logged)
dcp logs -f caddy            # access/TLS logs
dcp restart backend
dcp down                     # stop everything (data is kept in Docker volumes)
```

**Never** run `dcp down -v` in production; it deletes the database volume.

## Production security checklist

- [ ] `.env` has `APP_ENV=production`, a random `POSTGRES_PASSWORD`, `COOKIE_SECURE=true`, an `https://` origin.
- [ ] Only ports 22, 80, 443 are open in the cloud firewall; SSH uses keys, not passwords.
- [ ] HTTPS works and the browser shows a trusted certificate.
- [ ] Either `AUTH_REQUIRED=true` with the first administrator created via the CLI, or the cloud
      firewall limits ports 80/443 to your team's IP addresses.
- [ ] Automated, off-server backups are configured and a restore has been tested (docs/BACKUP_AND_RESTORE.md).
- [ ] Provider API keys (when added) are only in `.env` on the server.
